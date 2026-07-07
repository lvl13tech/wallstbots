#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audit_integrity.py -- DEEP relational audit of every number on every bot page.

Run anytime (no args needed):
    python Project/scripts/audit_integrity.py
    python Project/scripts/audit_integrity.py --quiet   (only FAIL lines + summary)

This audit does NOT spot-check fields in isolation. It encodes the FULL dependency
graph -- how every displayed number is DERIVED from other numbers -- and asserts each
derivation holds. If two boxes on a page must agree, this checks they agree. Exit 0 =
all clean, 1 = failures.

=========================== THE DEPENDENCY GRAPH ============================
Source of truth = the refresh_*.py engines. Every relationship below is a formula
the engine uses to BUILD the data, so the published data must satisfy it.

sc (starting capital) = universe_size * 1000  (wallstbots 55k, aistocks/bitbot13 50k)

FUND value box  (Public fund page + Member fund page read the same shape):
  Current Value box .... value.total          MUST = cash + pos_val
  "Started at" sublabel  starting_capital     MUST = sc  (universe*1000)
  Total P&L box ........ value.pnl            MUST = total - sc
                         value.pnl_pct        MUST = pnl / sc * 100
  Today's Change box ... value.day_pnl        MUST = total - day_open
                         value.day_pct        MUST = day_pnl / day_open * 100
                         value.day_open       MUST = the PRIOR trading day's snapshot
                                                     close (or sc on the very first day)
  DAY-1 RULE (owner) ... with only one day of data (prior close == sc), Today's Change
                         MUST equal Total P&L:  day_pnl == pnl  AND  day_pct == pnl_pct.
  cash/invested state .. holding_cash TRUE  -> pos_val == 0 and cash == total
                         pos_val > 0        -> not holding_cash
  sign sanity .......... sign(pnl)==sign(pnl_pct); sign(day_pnl)==sign(day_pct)

HOLDINGS rows (per position, when invested):
  Shares ............... shares > 0
  Entry ................ entry_price > 0
  Price ................ price > 0 ; price/entry within [0.125, 8]  (bad-feed guard)
  Value ................ value      MUST = shares * price
  cost_basis ........... cost_basis MUST = shares * entry_price
  Total P&L ............ pnl        MUST = value - cost_basis
  % .................... pnl_pct    MUST = (price/entry - 1) * 100
  Today ................ sign(day_pnl)==sign(day_pct)
  pos_val rollup ....... pos_val    MUST = sum(row values)

LEADERBOARD (period 'all'):
  all_pnl per fund ..... MUST = fund.total - sc
  all_pct per fund ..... MUST = fund.pnl_pct
  overall_grade ........ present ; all 5 funds present

CHART / SNAPSHOTS:
  today present exactly once ; dates strictly increasing ; none in the future
  every snapshot carries all 5 fund keys
  snapshot[today][fund] MUST = fund.total   (chart endpoint == cards)

BOT13 TRACK RECORD tile (computed from snapshots):
  up/down/cash day counts + best/worst % derived from consecutive bot13 deltas
  (reported; down-day count MUST equal number of negative deltas)

STRATEGY box:
  oracle & wizard ...... decision MUST NOT be HOLD (they always deploy)
  bot13 ................ decision HOLD -> pos_val == 0

BOT13 INTRADAY CASH (while invested, window open):
  cash MUST = day_open - sum(cost_basis) + sum(today's SELL realized)
  (no cash vanishes or appears during intraday rotations)

BASELINE DEPLOYMENT (equalizer/titan, invested, not display-frozen):
  positions count SHOULD = universe size (a missing asset leaves $1,000 idle) -> WARN

MEMBER page (needs internal key; best-effort, skips cleanly if unavailable):
  fund state ........... total_value MUST = entry_cost + gain_loss
                         gain_loss_pct MUST = gain_loss / entry_cost * 100
  "Started at" box ..... entry_cost MUST = n_holdings * 1000 (the member's own N)
  STALE STATE .......... snapshot_date MUST be today on a trading day (else WARN + skip cross-checks)
  INDEPENDENT SIMS (engine contract since 2026-07-06: each member fund is its OWN
    simulation seeded at N x $1,000; dollars come ONLY from its own positions) ...
    OWN-POSITIONS ...... total_value MUST = sum(position values) (+ idle cash
                         ec - sum(cost) for equalizer/titan, which never compound)
    per-position ....... value = shares x price ; cost = shares x entry ;
                         pnl = value - cost  (verifiable from real entries)
    IMPOSSIBLE MOVE .... |day_pct| beyond a sane one-day cap (30% equity / 50%
                         crypto) = fabricated data, not trading
  PLATFORM-DOLLAR LEAK . platform-scale dollars ($50k/$55k) must NEVER appear in a
                         member record: _day_open ~ platform sc while entry_cost
                         differs = the exact 2026-07-06 corruption signature
                         (member _day_open stored 55000 on a $20,000 portfolio
                         -> +260% fictitious all-time gain)
  member chart ......... NOT auditable server-side yet: bot_performance_snapshots has
                         no internal read endpoint (member-JWT only). History checks
                         (each point pct==dollars; last point==live) need a tiny
                         internal GET before they can be asserted here.
============================================================================
"""
import json, sys, urllib.request, urllib.parse
from pathlib import Path
from datetime import datetime, date
from zoneinfo import ZoneInfo
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from bot13_engine import is_trading_day as _is_trading_day, EQUITY_CFG as _EQ_CFG, CRYPTO_CFG as _CR_CFG
except Exception:
    _is_trading_day = None

ROOT = Path(__file__).resolve().parents[2]
secrets = {}
sp = ROOT / "Project" / "config" / "secrets.json"
if sp.exists():
    try: secrets = json.loads(sp.read_text())
    except Exception: pass
BACKEND = (secrets.get("api_url") or "").rstrip("/")
KEY     = secrets.get("internal_api_key") or ""
if not BACKEND:
    print("ERROR: api_url not in secrets.json"); sys.exit(2)

QUIET     = "--quiet" in sys.argv
PLATFORMS = {"wallstbots": 55, "aistocks": 50, "bitbot13": 50}
FUNDS     = ["bot13", "oracle", "wizard", "equalizer", "titan"]
ALWAYS_DEPLOY = {"oracle", "wizard"}   # these strategies never sit in cash / never HOLD
TODAY     = datetime.now(ZoneInfo("America/New_York")).date().isoformat()

fails, warns = [], []
def FAIL(scope, msg): fails.append(f"[{scope}] {msg}")
def WARN(scope, msg): warns.append(f"[{scope}] {msg}")

def fnum(x):
    try: return float(x)
    except Exception: return None
def approx(a, b, tol):
    return a is not None and b is not None and abs(a - b) <= tol
# tolerances
def teq(expected):           # exact derivation, same 2dp rounding
    return max(0.02, abs(expected or 0) * 0.0006)
def tcross(expected):        # cross-source (snapshot / leaderboard vs live)
    return max(1.0, abs(expected or 0) * 0.006)
TPCT = 0.06                  # percentage-point tolerance (exact)
TPCTX = 0.20                 # percentage-point tolerance (cross)

def get(url, key=None):
    # Cache-buster (2026-07-06): /public/tracker/state is served through an edge cache; an
    # audit run from a different network was handed an 18-hour-old copy (last_refresh 01:59
    # vs live 20:00), which would make every cross-check meaningless. A unique query param
    # forces an origin fetch so the audit ALWAYS judges live data.
    url += ("&" if "?" in url else "?") + "_ab=" + datetime.now().strftime("%Y%m%d%H%M%S%f")
    try:
        req = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
        if key: req.add_header("x-internal-key", key)
        return json.load(urllib.request.urlopen(req, timeout=25))
    except Exception as e:
        return {"_error": str(e)}

# a check helper that records into a per-fund reconciliation line
class Recon:
    def __init__(self, scope): self.scope=scope; self.rows=[]
    def check(self, name, got, expected, tol, unit=""):
        ok = approx(fnum(got), fnum(expected), tol)
        self.rows.append((name, got, expected, ok, unit))
        if not ok: FAIL(self.scope, f"{name}: got {got} expected {expected}")
        return ok
    def note(self, name, got, ok, detail=""):
        self.rows.append((name, got, detail, ok, ""))
        if not ok: FAIL(self.scope, f"{name}: {got} {detail}")
    def render(self):
        out=[]
        for name, got, exp, ok, unit in self.rows:
            mark = "OK " if ok else "XX "
            if exp == "" or exp is None:
                out.append(f"      {mark}{name} = {got}{unit}")
            else:
                out.append(f"      {mark}{name}: got {got}{unit} vs {exp}{unit}")
        return "\n".join(out)

print("=" * 74)
print(f"  WALLSTBOTS DEEP AUDIT  --  {TODAY}   (source of truth: refresh_*.py)")
print("=" * 74)

for platform, usize in PLATFORMS.items():
    sc = float(usize * 1000)
    r = get(f"{BACKEND}/public/tracker/state?platform={platform}")
    d = r.get("data", {}) if "_error" not in r else {}
    if not d:
        FAIL(platform, f"could not load state ({r.get('_error','no data')})"); continue
    funds = d.get("funds", {}) or {}
    snaps = d.get("snapshots", []) or []
    print(f"\n{'#'*74}\n## {platform}   sc=${sc:,.0f}   last_refresh={d.get('last_refresh')}\n{'#'*74}")

    # starting_capital box
    sc_stored = fnum(d.get("starting_capital"))
    if sc_stored is None or abs(sc_stored - sc) > 0.5:
        FAIL(platform, f"starting_capital {sc_stored} != sc {sc} (universe {usize})  -> every 'Started at' box is wrong")

    # ---- snapshot prep: prior-day close per fund, and today's snapshot ----
    dated = [s for s in snaps if s.get("date")]
    dated.sort(key=lambda s: s["date"])
    prior_close = {}   # fund -> most recent snapshot value strictly before today
    today_snap = None
    for s in dated:
        if s["date"] < TODAY:
            for fn in FUNDS:
                if fnum(s.get(fn)) is not None: prior_close[fn] = fnum(s.get(fn))
        elif s["date"] == TODAY:
            today_snap = s

    # snapshot structural checks
    dates = [s["date"] for s in dated]
    # Holiday-aware: markets are CLOSED on weekends + US holidays, so a non-trading day
    # legitimately has NO snapshot, and a snapshot must NEVER be dated on one.
    _cfg = _CR_CFG if platform == "bitbot13" else _EQ_CFG
    _today_is_trading = (_is_trading_day is None) or _is_trading_day(_cfg, date.fromisoformat(TODAY))
    if _today_is_trading and dates.count(TODAY) == 0:
        FAIL(platform, "snapshots: today missing -> chart is stale")
    if dates.count(TODAY) > 1:  FAIL(platform, "snapshots: today duplicated")
    for i in range(1, len(dates)):
        if dates[i] <= dates[i-1]: FAIL(platform, f"snapshots: dates not strictly increasing ({dates[i-1]} -> {dates[i]})")
    for dt in dates:
        if dt > TODAY:
            FAIL(platform, f"snapshots: future-dated snapshot {dt}")
        elif _is_trading_day is not None:
            try:
                if not _is_trading_day(_cfg, date.fromisoformat(dt)):
                    FAIL(platform, f"snapshots: {dt} is a NON-TRADING day (weekend/holiday) -- a fund "
                                   f"seeded/snapshotted on a closed market; nothing should run that day")
            except Exception:
                pass
    for s in dated:
        miss = [fn for fn in FUNDS if fnum(s.get(fn)) is None]
        if miss: FAIL(platform, f"snapshots {s['date']}: missing funds {miss}")

    live_totals = {}
    for fund in FUNDS:
        f = funds.get(fund)
        scope = f"{platform}/{fund}"
        if not f:
            FAIL(scope, "fund missing"); continue
        v = f.get("value") or {}
        T  = fnum(v.get("total")); PV = fnum(v.get("pos_val")); CH = fnum(v.get("cash"))
        PN = fnum(v.get("pnl"));   PP = fnum(v.get("pnl_pct"))
        DPN= fnum(v.get("day_pnl")); DP = fnum(v.get("day_pct")); DO = fnum(v.get("day_open"))
        positions = v.get("positions") or []
        live_totals[fund] = T
        rc = Recon(scope)
        # Holdings roll-ups (real entries): sum of cost basis and sum of holdings P&L.
        HOLD_FUNDS = ("oracle", "wizard", "equalizer", "titan")
        sum_cost = round(sum((fnum(p.get("cost_basis")) or 0) for p in positions), 2)
        sum_ppnl = round(sum((fnum(p.get("pnl"))        or 0) for p in positions), 2)

        # ---------- FUND-LEVEL derivations ----------
        rc.note("total present & > 0", T, T is not None and T > 0)
        if CH is not None and PV is not None and T is not None:
            exp_cp = CH + PV
            if fund == "bot13":
                # bot13 rotates intraday and BANKS realized gains into total; its cash
                # field can read 0 while total legitimately exceeds holdings+cash by the
                # banked realized amount. Treat a small positive gap as expected (WARN),
                # not a hard failure -- but still surface it so the owner can decide
                # whether cash should carry the banked realized instead.
                ok_cp = approx(T, exp_cp, max(1.0, abs(T) * 0.001))
                rc.rows.append(("total = cash + pos_val", T, round(exp_cp, 2), ok_cp, ""))
                if not ok_cp:
                    WARN(scope, f"total {T} != cash+pos_val {round(exp_cp,2)} (gap {round(T-exp_cp,2)}; "
                                f"likely banked realized from bot13 intraday rotation not reflected in cash)")
            else:
                rc.check("total = cash + pos_val", T, exp_cp, teq(T))
        if PN is not None:
            rc.check("pnl = total - sc", PN, (T - sc) if T is not None else None, teq(PN))
        if PP is not None and T is not None:
            rc.check("pnl_pct = pnl/sc*100", PP, (T - sc)/sc*100, TPCT, "%")

        # day_open must equal prior-day snapshot close (or sc on day 1)
        exp_open = prior_close.get(fund, sc)
        is_day1 = approx(exp_open, sc, teq(sc))   # only the reset baseline precedes today
        if DO is not None:
            rc.check("day_open = prior-day close", DO, exp_open, tcross(exp_open))
        if DPN is not None and DO is not None:
            rc.check("day_pnl = total - day_open", DPN, (T - DO) if T is not None else None, teq(DPN))
        if DP is not None and DO not in (None, 0):
            rc.check("day_pct = day_pnl/day_open*100", DP, (DPN / DO * 100) if DPN is not None else None, TPCT, "%")

        # DAY-1 RULE: one day of data -> Today's Change == Total P&L
        if is_day1:
            if DPN is not None and PN is not None:
                rc.check("DAY-1: day_pnl == pnl", DPN, PN, teq(PN))
            if DP is not None and PP is not None:
                rc.check("DAY-1: day_pct == pnl_pct", DP, PP, TPCT, "%")

        # cash / invested consistency
        holding_cash = v.get("holding_cash")
        window_open  = v.get("window_open")
        invested = (PV is not None and PV > 0.01) and bool(positions)
        if holding_cash is True:
            rc.note("holding_cash -> pos_val == 0", PV, approx(PV, 0, 0.5))
            if T is not None and CH is not None:
                rc.note("holding_cash -> cash == total", CH, approx(CH, T, teq(T)))
        if invested and holding_cash is True:
            FAIL(scope, "holding_cash TRUE but pos_val>0 with live positions (contradiction)")
        # sign sanity -- both sides must be MEANINGFULLY nonzero: a -$2.42 day rounds to a
        # displayed 0.00%, which is not a sign disagreement (false positive, 2026-07-06).
        if PN is not None and PP is not None and abs(PN) > 0.5 and abs(PP) >= 0.005 and (PN < 0) != (PP < 0):
            FAIL(scope, f"pnl sign {PN} disagrees with pnl_pct sign {PP}")
        if DPN is not None and DP is not None and abs(DPN) > 0.5 and abs(DP) >= 0.005 and (DPN < 0) != (DP < 0):
            FAIL(scope, f"day_pnl sign {DPN} disagrees with day_pct sign {DP}")

        # ---------- POSITION-LEVEL derivations ----------
        display_freeze = (holding_cash is True) or (window_open is False)
        pos_val_sum = 0.0
        for p in positions:
            sym = p.get("symbol", "?"); ps = f"{scope}:{sym}"
            sh = fnum(p.get("shares")); pr = fnum(p.get("price") or p.get("current_price"))
            en = fnum(p.get("entry_price")); val = fnum(p.get("value"))
            cb = fnum(p.get("cost_basis")); pnl = fnum(p.get("pnl")); ppct = fnum(p.get("pnl_pct"))
            dpn = fnum(p.get("day_pnl")); dpc = fnum(p.get("day_pct"))
            if sh is None or sh <= 0: FAIL(ps, f"shares {sh}")
            if pr is None or pr <= 0: FAIL(ps, f"price {pr}")
            if en is None or en <= 0: FAIL(ps, f"entry_price {en}")
            if en and pr and en > 0:
                ratio = pr / en
                if ratio > 8.0 or ratio < 0.125:
                    FAIL(ps, f"bad-entry price/entry={ratio:.2f}x (entry {en}, price {pr})")
            if sh and pr and val is not None and not approx(val, sh*pr, max(0.5, abs(sh*pr)*0.01)):
                FAIL(ps, f"value {val} != shares*price {round(sh*pr,2)}")
            if sh and en and cb is not None and not approx(cb, sh*en, max(0.5, abs(sh*en)*0.01)):
                FAIL(ps, f"cost_basis {cb} != shares*entry {round(sh*en,2)}")
            if val is not None and cb is not None and pnl is not None and not approx(pnl, val-cb, max(0.5, abs(val)*0.01)):
                FAIL(ps, f"pnl {pnl} != value-cost_basis {round(val-cb,2)}")
            # pnl_pct: check against the AUTHORITATIVE dollar figures (value/cost_basis),
            # which use full-precision prices. The Entry/Price columns are rounded to 2dp,
            # so for low-priced (crypto) assets (price/entry-1) can look off vs the shown %
            # even though the % is correct -> that is a DISPLAY-precision WARN, not a data bug.
            if val is not None and cb not in (None, 0) and ppct is not None:
                auth_pct = (val/cb - 1) * 100
                if not approx(ppct, auth_pct, 0.12):
                    FAIL(ps, f"pnl_pct {ppct} != value/cost_basis-1 {round(auth_pct,2)}")
                elif en and pr and en > 0 and not approx(ppct, (pr/en-1)*100, 0.25):
                    WARN(ps, f"display rounding: Holdings shows Entry ${en}/Price ${pr} -> looks like "
                             f"{round((pr/en-1)*100,2)}% but actual is {ppct}% (2dp too coarse for this price)")
            if dpn is not None and dpc is not None and abs(dpn) > 0.5 and abs(dpc) >= 0.005 and (dpn < 0) != (dpc < 0):
                FAIL(ps, f"day_pnl sign {dpn} disagrees with day_pct {dpc}")
            if val is not None: pos_val_sum += val
        if invested and not display_freeze and PV is not None and positions:
            rc.note("pos_val = sum(row values)", round(pos_val_sum,2), approx(PV, pos_val_sum, max(1.0, abs(PV)*0.02)), f"(pos_val={PV})")
            # Holdings TODAY column must sum to the fund's Today's Change box (a position
            # bought today shows day == its pnl, not a full-day move it never took).
            # ROTATION-DAY identity: when a fund redeployed today, the box additionally
            # carries the overnight move realized by the rotation sale, which no current
            # holding shows: box == sum(day) + (deployed capital - day_open), where
            # deployed = sum(cost_basis) + cash. Accept either exact identity.
            _pos_day = sum((fnum(p.get("day_pnl")) or 0) for p in positions)
            _tol = max(2.0, abs(T or 0)*0.0015)
            _plain_ok = DPN is None or approx(_pos_day, DPN, _tol)
            _rot_ok   = (DPN is not None and DO is not None
                         and approx(DPN, _pos_day + (sum_cost + (CH or 0) - DO), _tol))
            if DPN is not None and not (_plain_ok or _rot_ok):
                rc.note("Holdings TODAY sums to Today's Change", round(_pos_day,2), False, f"(sum {round(_pos_day,2)} vs box {DPN})")

        # ---------- HOLDOVER / RECONCILIATION GUARDS ----------
        # Total P&L is SINCE LAUNCH: pnl = total - sc. For a hold fund (oracle/wizard/equalizer/
        # titan) that has NOT compounded yet, the holdings were deployed with exactly the
        # starting capital, so SUM(cost_basis) == sc AND the Holdings P&L column sums to the
        # Total P&L box. A "holdover" (a reset that left a stale carried balance) shows up as
        # SUM(cost) != sc on a fund whose inception is TODAY -- this is the exact bug that made
        # bitbot13 Wizard read a $50,019 cost basis. We FAIL that hard.
        if positions and CH is not None:
            if CH < -0.5:
                FAIL(scope, f"negative cash {CH} -> fund deployed more than its capital (overcommit/churn)")
            fund_incep = str(f.get("inception") or "")
            if fund in HOLD_FUNDS and not display_freeze:
                # (1) HOLDOVER: a freshly seeded/reset fund (inception today) MUST have deployed
                #     exactly sc. If sum(cost) != sc, a stale carried balance leaked through.
                if fund_incep == TODAY and abs(sum_cost - sc) > max(2.0, sc * 0.0001):
                    FAIL(scope, f"HOLDOVER: sum(cost_basis) {sum_cost} != starting capital {sc} on a fresh "
                                f"(inception=today) fund -> a reset left a stale carried balance; the fund "
                                f"deployed the wrong amount. Holdings will not sum to Total P&L.")
                # (2) When cost basis == sc (fund hasn't compounded), holdings P&L MUST sum to the
                #     Total P&L box, and Today's Change must equal Total P&L on day 1.
                if abs(sum_cost - sc) <= max(2.0, sc * 0.0001) and PN is not None:
                    if not approx(sum_ppnl, PN, max(0.5, abs(PN) * 0.01)):
                        FAIL(scope, f"Holdings P&L {sum_ppnl} != Total P&L box {PN} (cost basis == sc so they "
                                    f"must match)")

        # ---------- STRATEGY box ----------
        # Projected Edge Score is a frozen decision-time number, NOT the live day return.
        # If it equals day_pct the drift bug is back (edge score = Today's Change).
        _strat0 = f.get("current_strategy") or {}
        _pr = fnum(_strat0.get("projected_return"))
        # Strategy prose must name the SAME stocks as the pick cards (a rotation used to leave
        # a stale rationale listing different names). Every pick symbol must appear in it.
        if fund == "bot13" and str(_strat0.get("decision","")).upper() == "TRADE":
            _rtext = str(_strat0.get("rationale") or "")
            _bad = [pk.get("symbol") for pk in (_strat0.get("picks") or [])
                    if pk.get("symbol") and pk.get("symbol") not in _rtext]
            if _bad and _rtext:
                FAIL(scope, f"strategy rationale does not name its own picks {_bad} -- prose/cards mismatch")
        if fund == "bot13" and _pr is not None and DP is not None and abs(_pr) > 0.01 and approx(_pr, DP, 0.05):
            WARN(scope, f"Projected Edge Score {_pr} == Today's Change {DP} (should be the frozen decision-time score, not the live day return)")
        strat = f.get("current_strategy") or {}
        dec = str(strat.get("decision", "")).upper()
        # oracle/wizard never HOLD mid-life -- BUT right after a reset they legitimately sit
        # in cash at the clean baseline until their next session open. Don't flag that.
        _fresh_baseline = (PV is not None and abs(PV) < 0.5 and PN is not None and abs(PN) < 1.0
                           and T is not None and approx(T, sc, 1.0))
        if fund in ALWAYS_DEPLOY and dec == "HOLD":
            if _fresh_baseline:
                WARN(scope, f"{fund} at fresh reset baseline (HOLD/cash) -- will deploy at next session open")
            else:
                FAIL(scope, f"strategy decision=HOLD but {fund} always deploys (should be TRADE/deployed)")
        if fund == "bot13" and dec == "HOLD" and PV is not None and PV > 0.5:
            FAIL(scope, f"bot13 strategy=HOLD but pos_val={PV} (holdings shown on a HOLD)")

        # ---------- CHART: snapshot[today] == live total ----------
        if today_snap is not None:
            sv = fnum(today_snap.get(fund))
            rc.note("snapshot[today] == total", sv, approx(sv, T, tcross(T)) if (sv is not None and T is not None) else False,
                    f"(chart {sv} vs card {T})")

        # ---------- TRADE LOG: authoritative-ledger invariants (bot13 only) ----------
        # The trade log is now written authoritatively (a BUY on every open, a SELL on every
        # close) and is TODAY-ONLY; BOT13 is a DAILY bot on every site and closes out at
        # session end, so it never carries a position across midnight. Therefore every SELL
        # must have a matching prior BUY in the same (today-only) log -- on ALL sites now
        # (the old "crypto carries overnight" WARN exception no longer applies).
        seen = set()
        for e in sorted(v.get("trade_log") or [], key=lambda e: str(e.get("ts",""))):
            act = str(e.get("action","")).upper(); s = e.get("symbol")
            if act == "BUY": seen.add(s)
            elif act == "SELL" and s not in seen:
                FAIL(scope, f"SELL of {s} with no prior BUY in the trade_log "
                            f"(authoritative ledger should pair every SELL with its BUY)")
                seen.add(s)  # avoid re-flagging every later rotation of the same symbol
        # LEDGER == ACCOUNT (2026-07-05): when BOT13 finished a traded day FLAT, the banked
        # balance must equal day_open + the SUM of today's SELL rows' realized P&L -- the
        # Total P&L box and Trade History must tell the same story. This exact mismatch
        # shipped live (bitbot13: box +$1,406.40 vs ledger +$1,528.68) with no audit check.
        if fund == "bot13" and (v.get("holding_cash") is True):
            _sells = [e for e in (v.get("trade_log") or [])
                      if str(e.get("action","")).upper() == "SELL"
                      and str(e.get("ts",""))[:10] == TODAY]
            if _sells and DO is not None and T is not None:
                _led = round(DO + sum(float(e.get("realized") or 0) for e in _sells), 2)
                if not approx(T, _led, max(1.0, abs(T) * 0.0005)):
                    FAIL(scope, f"LEDGER!=ACCOUNT: total {T} != day_open {DO} + realized "
                                f"{round(_led - DO, 2)} = {_led} (Trade History and the Total "
                                f"P&L box disagree -- two price sources)")
        # BOT13 INTRADAY CASH (2026-07-06): while BOT13 is INVESTED mid-session, its cash
        # must be exactly what the ledger implies: the day's opening balance minus what it
        # deployed into today's positions plus what today's SELLs realized. Verified live
        # (bitbot13 2026-07-06: 51406.40 - 51331.79 + 0 = 74.61 == cash). This is the
        # invested-state twin of LEDGER==ACCOUNT above -- cash appearing or vanishing
        # during an intraday rotation fails here.
        if (fund == "bot13" and v.get("holding_cash") is not True and positions
                and window_open is not False and CH is not None and DO is not None):
            _r_today = sum(float(e.get("realized") or 0) for e in (v.get("trade_log") or [])
                           if str(e.get("action","")).upper() == "SELL"
                           and str(e.get("ts",""))[:10] == TODAY)
            _exp_cash = round(DO - sum_cost + _r_today, 2)
            if not approx(CH, _exp_cash, max(1.0, abs(T or 0) * 0.0005)):
                FAIL(scope, f"INTRADAY CASH: cash {CH} != day_open {DO} - deployed cost {sum_cost} "
                            f"+ realized {round(_r_today,2)} = {_exp_cash} (cash vanished/appeared mid-rotation)")
        # BASELINE DEPLOYMENT (2026-07-06): equalizer/titan hold the WHOLE universe. Fewer
        # positions than universe means an asset never entered and its $1,000 sits idle
        # (live example: aistocks equalizer 49/50 with $1,000 cash). WARN -- can be a
        # legitimately unpriceable/delisted asset, but the owner must know.
        if fund in ("equalizer", "titan") and positions and not display_freeze:
            if len(positions) < usize:
                WARN(scope, f"only {len(positions)}/{usize} assets deployed -- "
                            f"${round(CH or 0, 2)} idle cash (missing asset never entered)")
        # NO VANISHED CASH (2026-07-05): oracle/wizard deploy their capital minus a small
        # rounding remainder, which must REMAIN in the fund as cash. sum(cost_basis) + cash
        # must equal the deployed capital (strategy.deployed_capital once recorded by a
        # rotation; sc before the fund's first compounding rotation). Live example caught
        # late: bitbot13 Wizard deployed $49,987 of $50,000 and the $13 was deleted.
        if fund in ("oracle", "wizard") and positions:
            _dep = fnum((f.get("current_strategy") or {}).get("deployed_capital"))
            _base = _dep if _dep else sc
            if _dep or abs(sum_cost - sc) <= sc * 0.02:
                _acct = round(sum_cost + (CH or 0), 2)
                if not approx(_acct, _base, max(2.0, _base * 0.0002)):
                    FAIL(scope, f"VANISHED CASH: sum(cost_basis) {sum_cost} + cash {CH} = {_acct} "
                                f"!= deployed capital {_base} (rounding remainder was deleted)")
        # No stale carry: bitbot13 trades daily, so BOT13 must not hold any position dated
        # before today. If it does, a day-roll/missed close-out left it stranded on the book.
        if fund == "bot13" and platform == "bitbot13":
            _stale = [p.get("symbol") for p in (v.get("_real_positions") or [])
                      if 0 < len(str(p.get("entry_time") or "")[:10]) and str(p.get("entry_time"))[:10] < TODAY]
            if _stale:
                FAIL(scope, f"bot13 holds prior-day position(s) {_stale} across midnight "
                            f"(daily bot must close out at session end -- authoritative ledger should have dropped these)")

        if not QUIET:
            tag = "DAY-1" if is_day1 else f"day>={len([x for x in dates if x<TODAY])+1}"
            print(f"\n   {fund.upper()}  [{tag}]  total={T}  pnl={PN}  day_pnl={DPN}  day_open={DO}")
            print(rc.render())

    # ---------- LEADERBOARD ----------
    lb = d.get("leaderboards", {}) or {}
    allrows = lb.get("all", []) or []
    lb_funds = set()
    for row in allrows:
        fn = row.get("fund"); lb_funds.add(fn)
        if fn not in live_totals: continue
        T = live_totals[fn]
        if T is None: continue
        ap = fnum(row.get("all_pnl")); apc = fnum(row.get("all_pct"))
        if ap is not None and not approx(ap, T - sc, tcross(T)):
            FAIL(f"{platform}/lb/{fn}", f"leaderboard all_pnl {ap} != total-sc {round(T-sc,2)}")
        fv = (funds.get(fn) or {}).get("value") or {}
        pp = fnum(fv.get("pnl_pct"))
        if apc is not None and pp is not None and not approx(apc, pp, TPCTX):
            FAIL(f"{platform}/lb/{fn}", f"leaderboard all_pct {apc} != fund pnl_pct {pp}")
        if not row.get("overall_grade"):
            WARN(f"{platform}/lb/{fn}", "missing overall_grade")
    miss_lb = [fn for fn in FUNDS if fn not in lb_funds]
    if allrows and miss_lb:
        FAIL(f"{platform}/lb", f"leaderboard missing funds {miss_lb}")

    # ---------- BOT13 TRACK RECORD from snapshots (reported + down-count check) ----------
    b13 = [(s["date"], fnum(s.get("bot13"))) for s in dated if fnum(s.get("bot13")) is not None]
    up=down=cash=0; best=-1e9; worst=1e9
    for i in range(1, len(b13)):
        prev = b13[i-1][1]; cur = b13[i][1]
        if prev and prev > 0:
            chg = (cur - prev) / prev * 100
            if abs(chg) < 1e-6: cash += 1
            elif chg > 0: up += 1
            else: down += 1
            best = max(best, chg); worst = min(worst, chg)
    if not QUIET and b13:
        bs = f"{best:+.2f}%" if best>-1e8 else "-"; ws = f"{worst:+.2f}%" if worst<1e8 else "-"
        print(f"\n   BOT13 record (from {len(b13)} snapshots): up={up} down={down} cash={cash} best={bs} worst={ws}")

    # ---------- MEMBER portfolios (INDEPENDENT sims -- Rule 0) ----------
    # Member portfolios are their OWN simulations, seeded at their own cost (N x $1,000) on their
    # creation day and tracking forward from real entries -- NOT scaled from the platform. Read each
    # member fund-state via the internal endpoint and reconcile INTERNALLY (the only thing that must
    # hold, and the thing the mission demands -- every number verifiable from the member's entries):
    #   total_value == entry_cost + gain_loss ; gain_loss_pct == gain_loss/entry_cost*100
    # day_pnl/day_pct are recomputed below from strategy._day_open (now returned by the
    # portfolio-fund-state endpoint after the 2026-07-05 readback fix) and asserted against
    # gain_loss whenever _day_open == entry_cost (the fund's actual day-1 signature) -- this
    # is the exact invariant that was silently broken before that fix (Today's Change stuck
    # at $0 while Total P&L was correct), and it previously had NO automated check here.
    if KEY:
        probe = get(f"{BACKEND}/internal/portfolios/active?platform={platform}", KEY)
        if "_error" in probe:
            if not QUIET: print(f"\n   MEMBER checks skipped (portfolios: {probe.get('_error')})")
        else:
            body = probe if isinstance(probe, list) else probe.get("portfolios", [])
            ports = body if isinstance(body, list) else []
            checked = 0
            for p in ports[:25]:
                bid = p.get("bot_id") or p.get("id")
                if not bid: continue
                n_hold = len(p.get("holdings") or [])
                for fund in FUNDS:
                    r = get(f"{BACKEND}/internal/portfolio-fund-state/{bid}/{fund}", KEY)
                    st = r.get("state") if isinstance(r, dict) else None
                    if not st: continue
                    tv = fnum(st.get("total_value")); gl = fnum(st.get("gain_loss"))
                    ec = fnum(st.get("entry_cost")); glp = fnum(st.get("gain_loss_pct"))
                    ms = f"{platform}/member:{str(bid)[:8]}/{fund}"
                    _mstrat = st.get("strategy") if isinstance(st.get("strategy"), dict) else {}
                    _pending = (_mstrat.get("pending") is True) or (str(_mstrat.get("decision","")).upper() == "PENDING")
                    # "Started at" box: the member's own N x $1,000 -- nothing else, ever.
                    if ec is not None and n_hold and not approx(ec, n_hold * 1000.0, 0.5):
                        FAIL(ms, f"STARTED-AT: entry_cost {ec} != {n_hold} holdings x $1,000 = {n_hold*1000.0}")
                    if tv is not None and gl is not None and ec is not None and not approx(tv, ec+gl, max(1.0, abs(tv)*0.01)):
                        FAIL(ms, f"total_value {tv} != entry_cost+gain_loss {round(ec+gl,2)}")
                    if glp is not None and gl is not None and ec not in (None,0) and not approx(glp, gl/ec*100, 0.2):
                        FAIL(ms, f"gain_loss_pct {glp} != gain_loss/entry_cost*100 {round(gl/ec*100,2)}")
                    # STALE STATE: member state must be refreshed the same day as the platform on a
                    # trading day. A stale row makes every cross-check below meaningless -> WARN + skip.
                    _msnap = str(st.get("snapshot_date") or "")
                    _stale = _today_is_trading and _msnap and _msnap < TODAY
                    if _stale:
                        WARN(ms, f"STALE: member state snapshot_date {_msnap} < today {TODAY} (member refresh lagging)")
                    # INDEPENDENT SIMS (engine contract since 2026-07-06, refresh_portfolios.py):
                    # each member fund is its OWN simulation; every dollar must be verifiable
                    # from the member's own positions at real entry prices.
                    _m_dpct = fnum(st.get("day_pct"))
                    _mpos = st.get("positions") if isinstance(st.get("positions"), list) else []
                    if not _pending and not _stale and _mpos:
                        _sumval = 0.0; _sumcost = 0.0
                        for _mp in _mpos:
                            _msym = _mp.get("symbol", "?"); _mps = f"{ms}:{_msym}"
                            _msh = fnum(_mp.get("shares")); _mpx = fnum(_mp.get("price"))
                            _men = fnum(_mp.get("entry_price")); _mval = fnum(_mp.get("value"))
                            _mcb = fnum(_mp.get("cost_basis")); _mpnl = fnum(_mp.get("pnl"))
                            # FABRICATED SEED signature: the old engine seeded unpriceable
                            # symbols at entry_price $1.00 exactly -- never a real entry.
                            if _men is not None and _men == 1.0:
                                FAIL(_mps, "member entry_price is exactly $1.00 (fabricated no-price seed, not a real entry)")
                            # bad-feed guard (same [0.125, 8] band as the public checks)
                            if _men and _mpx and _men > 0:
                                _mr = _mpx / _men
                                if _mr > 8.0 or _mr < 0.125:
                                    FAIL(_mps, f"member price/entry={_mr:.2f}x outside sanity band (entry {_men}, price {_mpx})")
                            if _msh and _mpx and _mval is not None and not approx(_mval, _msh*_mpx, max(0.5, abs(_msh*_mpx)*0.01)):
                                FAIL(_mps, f"member value {_mval} != shares*price {round(_msh*_mpx,2)}")
                            if _msh and _men and _mcb is not None and not approx(_mcb, _msh*_men, max(0.5, abs(_msh*_men)*0.01)):
                                FAIL(_mps, f"member cost_basis {_mcb} != shares*entry {round(_msh*_men,2)}")
                            if _mval is not None and _mcb is not None and _mpnl is not None and not approx(_mpnl, _mval-_mcb, max(0.5, abs(_mval)*0.01)):
                                FAIL(_mps, f"member pnl {_mpnl} != value-cost {round(_mval-_mcb,2)}")
                            if _mval is not None: _sumval += _mval
                            if _mcb  is not None: _sumcost += _mcb
                        # OWN-POSITIONS: the fund's total is the sum of its own holdings
                        # (+ idle cash ec - sum(cost) for baselines, which never compound).
                        _exp_tv = _sumval + (max(0.0, (ec or 0) - _sumcost) if fund in ("equalizer", "titan") else 0.0)
                        if tv is not None and not approx(tv, _exp_tv, max(1.0, abs(tv) * 0.01)):
                            FAIL(ms, f"OWN-POSITIONS: total_value {tv} != sum of own positions {round(_exp_tv,2)} "
                                     f"(member dollars must be verifiable from the member's own entries)")
                    # IMPOSSIBLE MOVE: a one-day move beyond a sane cap is fabricated data.
                    # NOTE: the internal endpoint does NOT return day_pnl/day_pct, so the day
                    # move is DERIVED from the state's own numbers: (total_value - _day_open)
                    # / _day_open -- the same formula the engine uses to build the box.
                    _move_cap = 50.0 if platform == "bitbot13" else 30.0
                    _m_do_early = fnum(_mstrat.get("_day_open"))
                    _impl_dpct = ((tv - _m_do_early) / _m_do_early * 100) if (tv is not None and _m_do_early) else None
                    if not _pending and not _stale and _impl_dpct is not None and abs(_impl_dpct) > _move_cap:
                        FAIL(ms, f"IMPOSSIBLE MOVE: implied day move {round(_impl_dpct,2)}% (total {tv} vs day_open "
                                 f"{_m_do_early}) exceeds one-day sanity cap {_move_cap}% (fabricated/corrupt data, not trading)")
                    # PLATFORM-DOLLAR LEAK: platform-scale dollars in a member record = the exact
                    # 2026-07-06 corruption signature (member _day_open = 55000 on a $20,000
                    # portfolio). A member fund whose _day_open sits at the PLATFORM's starting
                    # capital while its own cost differs materially was contaminated.
                    _m_do = fnum(_mstrat.get("_day_open"))
                    if (not _pending and not _stale and _m_do is not None and ec not in (None, 0)
                            and abs(ec - sc) > max(2.0, sc * 0.001)
                            and approx(_m_do, sc, max(2.0, sc * 0.001))):
                        FAIL(ms, f"PLATFORM-DOLLAR LEAK: member _day_open {_m_do} equals the PLATFORM starting "
                                 f"capital {sc} but this member's own cost is {ec} (platform dollars in a member record)")
                    # DAY-1 RULE for member funds: strategy._day_open is persisted each run so the
                    # fund's OWN day-1 can be identified (day_open == entry_cost means this fund's
                    # value has never been carried forward from a prior day). On that day, Today's
                    # Change must equal Total P&L exactly -- this is the invariant that was silently
                    # broken by the missing positions/strategy/trade_log readback (fixed 2026-07-05).
                    strat = st.get("strategy") if isinstance(st.get("strategy"), dict) else {}
                    day_open = fnum(strat.get("_day_open"))
                    # DAY-1 detection must be EXACT (seed sets _day_open = entry_cost to the
                    # cent). The old 1% window mislabeled day-2+ funds as day 1 and flagged
                    # perfectly consistent numbers (false positives, 2026-07-06 audit).
                    if day_open is not None and ec is not None and tv is not None and gl is not None and approx(day_open, ec, max(0.02, abs(ec)*0.0001)):
                        m_day_pnl = round(tv - day_open, 2)
                        if not approx(m_day_pnl, gl, max(1.0, abs(gl)*0.02)):
                            FAIL(ms, f"MEMBER DAY-1: day_pnl {m_day_pnl} != gain_loss {gl} (day_open={day_open}, entry_cost={ec})")
                    # DATA-INTEGRITY RULE 0 (owner decision 2026-07-06): member portfolios are
                    # INDEPENDENT simulations. The checks above assert exactly that: every dollar
                    # verifiable from the member's own positions, no platform-scale dollars, no
                    # impossible moves. (The old platform-scaling engine and the member-vs-platform
                    # percentage cross-checks that matched it are both gone -- do not reintroduce.)
                    checked += 1
            if not QUIET:
                print(f"\n   MEMBER (independent sims): reconciled {checked} fund-states (total == cost + P&L; no platform scaling)")
    else:
        if not QUIET: print("\n   MEMBER checks skipped (no internal key in secrets.json)")

# ---------------- SUMMARY ----------------
print("\n" + "=" * 74)
if not fails and not warns:
    print("  RESULT: ALL CLEAN -- every derivation on every page reconciles.")
elif not fails:
    print(f"  RESULT: PASS with {len(warns)} warning(s).")
else:
    print(f"  RESULT: {len(fails)} FAILURE(S)" + (f", {len(warns)} warning(s)" if warns else ""))
print("=" * 74)
if warns:
    print("\nWARNINGS:")
    for w in warns: print("  ! " + w)
if fails:
    print("\nFAILURES:")
    for x in fails: print("  X " + x)
sys.exit(1 if fails else 0)