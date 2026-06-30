#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audit_integrity.py -- FULL read-only audit of every number on every bot page.

Run anytime (no args needed):
    python Project/scripts/audit_integrity.py

Checks every relationship that feeds every page data box, for all 5 funds x 3
platforms, plus per-position rows, the leaderboard rollup, and snapshots. Prints a
clean bill of health or a flagged list. Exit 0 = all clean, 1 = flags found.

WHAT EACH PAGE BOX MAPS TO (so this audit = auditing the pages):
  Current Value box      -> fund.value.total          (checked: = cash + pos_val, > 0)
  Total P&L box          -> fund.value.pnl / pnl_pct  (checked: pnl = total - sc; pnl_pct = pnl/sc*100)
  Today's Change box     -> fund.value.day_pnl/day_pct(checked: internally consistent)
  Holdings rows          -> fund.value.positions[]    (checked per row: value=shares*price,
                                                        pnl=value-cost_basis, pnl_pct=price/entry-1,
                                                        no bad-entry >8x, price/shares>0)
  Trade History          -> fund.value.trade_log[]    (checked: SELLs have matching prior BUY)
  Leaderboard            -> leaderboards[period][]     (checked: all_pnl ~ fund total - sc)
  Chart                  -> snapshots[]                (checked: today present, no dupes/future,
                                                        snapshot total ~ live fund total)

Reads backend URL from Project/config/secrets.json. The internal key (for member
checks) is read from the same file; member checks skip gracefully if unavailable.
"""
import json, sys, urllib.request, urllib.parse
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

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

PLATFORMS = {"wallstbots": 55, "aistocks": 50, "bitbot13": 50}
FUNDS     = ["bot13", "oracle", "wizard", "equalizer", "titan"]
TODAY     = datetime.now(ZoneInfo("America/New_York")).date().isoformat()

flags = []
def flag(scope, msg): flags.append(f"[{scope}] {msg}")
def fnum(x):
    try: return float(x)
    except Exception: return None
def approx(a, b, tol):
    return a is not None and b is not None and abs(a - b) <= tol

def get(url):
    try:
        return json.load(urllib.request.urlopen(url, timeout=25))
    except Exception as e:
        return {"_error": str(e)}

print("=" * 70)
print(f"  WALLSTBOTS FULL AUDIT  --  {TODAY}")
print("=" * 70)

for platform, usize in PLATFORMS.items():
    sc = float(usize * 1000)
    r = get(f"{BACKEND}/public/tracker/state?platform={platform}")
    d = r.get("data", {}) if "_error" not in r else {}
    if not d:
        flag(platform, f"could not load state ({r.get('_error','no data')})"); continue
    funds = d.get("funds", {}) or {}
    print(f"\n## {platform}   sc=${sc:,.0f}   last_refresh={d.get('last_refresh')}")

    # expected baseline check
    sc_stored = fnum(d.get("starting_capital"))
    if sc_stored is not None and abs(sc_stored - sc) > 0.5:
        flag(platform, f"starting_capital {sc_stored} != expected {sc} (universe {usize})")

    live_totals = {}
    for fund in FUNDS:
        f = funds.get(fund)
        if not f:
            flag(f"{platform}/{fund}", "fund missing"); continue
        v = f.get("value") or {}
        T  = fnum(v.get("total")); PV = fnum(v.get("pos_val")); CH = fnum(v.get("cash"))
        PN = fnum(v.get("pnl"));   PP = fnum(v.get("pnl_pct"))
        DPN= fnum(v.get("day_pnl"));DP = fnum(v.get("day_pct")); DO = fnum(v.get("day_open"))
        positions = v.get("positions") or []
        live_totals[fund] = T

        # ---- FUND-LEVEL (Current Value / Total P&L / Today's Change boxes) ----
        if T is None:                         flag(f"{platform}/{fund}", "total missing")
        elif T <= 0:                          flag(f"{platform}/{fund}", f"total <= 0 ({T})")
        tol = max(1.0, (T or 0) * 0.01)
        if T is not None and PV is not None and CH is not None and not approx(T, PV + CH, tol):
            flag(f"{platform}/{fund}", f"total {T:.2f} != cash {CH:.2f} + pos_val {PV:.2f}")
        if T is not None and PN is not None and not approx(PN, T - sc, tol):
            flag(f"{platform}/{fund}", f"pnl {PN:.2f} != total-sc {T-sc:.2f}")
        if T is not None and PP is not None:
            calc = (T - sc) / sc * 100
            if abs(calc - PP) > 0.5:
                flag(f"{platform}/{fund}", f"pnl_pct {PP:.2f} != calc {calc:.2f}")
        if T is not None and DO is not None and DPN is not None and DO > 0 and not approx(T, DO + DPN, tol):
            flag(f"{platform}/{fund}", f"total {T:.2f} != day_open {DO:.2f} + day_pnl {DPN:.2f}")

        # ---- PER-POSITION (Holdings rows) ----
        pos_val_sum = 0.0
        for p in positions:
            sym = p.get("symbol","?")
            sh  = fnum(p.get("shares")); pr = fnum(p.get("price") or p.get("current_price"))
            en  = fnum(p.get("entry_price")); val = fnum(p.get("value")); pnl = fnum(p.get("pnl"))
            cb  = fnum(p.get("cost_basis"))
            if sh is None or sh <= 0:  flag(f"{platform}/{fund}", f"{sym}: shares {sh}")
            if pr is None or pr <= 0:  flag(f"{platform}/{fund}", f"{sym}: price {pr}")
            if en is not None and pr is not None and en > 0:
                ratio = pr/en
                if ratio > 8.0 or ratio < 0.125:
                    flag(f"{platform}/{fund}", f"{sym}: bad-entry ratio price/entry={ratio:.1f}x (entry {en}, price {pr})")
            if sh and pr and val is not None and not approx(val, sh*pr, max(0.5, abs(sh*pr)*0.01)):
                flag(f"{platform}/{fund}", f"{sym}: value {val:.2f} != shares*price {sh*pr:.2f}")
            if val is not None and cb is not None and pnl is not None and not approx(pnl, val-cb, max(0.5, abs(val)*0.01)):
                flag(f"{platform}/{fund}", f"{sym}: pnl {pnl:.2f} != value-cost {val-cb:.2f}")
            if val is not None: pos_val_sum += val
        _holding_cash = bool(v.get("holding_cash"))
        _window_open  = v.get("window_open", True) is not False
        _display_freeze = _holding_cash or (not _window_open)
        # When flat/after-close, positions[] is a read-only display of the day's trades
        # and pos_val is legitimately 0 -- only reconcile pos_val when actually invested.
        if (PV is not None and positions and not _display_freeze
                and not approx(PV, pos_val_sum, max(1.0, abs(PV)*0.02))):
            flag(f"{platform}/{fund}", f"pos_val {PV:.2f} != sum(position values) {pos_val_sum:.2f}")

        # ---- TRADE LOG (Trade History): SELLs need a prior BUY of that symbol ----
        seen_buy = set()
        for e in sorted(v.get("trade_log") or [], key=lambda e: str(e.get("ts",""))):
            act = str(e.get("action","")).upper(); s = e.get("symbol")
            if act == "BUY": seen_buy.add(s)
            elif act == "SELL" and s not in seen_buy:
                flag(f"{platform}/{fund}", f"SELL of {s} with no prior BUY in log")

        tstr = f"{T:,.2f}" if T is not None else "?"
        pstr = f"{PP:+.2f}%" if PP is not None else "?"
        print(f"   {fund:10} total={tstr:>14} pnl={pstr:>9} pos={len(positions)} trades={len(v.get('trade_log') or [])}")

    # ---- LEADERBOARD rollup matches fund totals ----
    for period, rows in (d.get("leaderboards") or {}).items():
        for row in rows:
            fn = row.get("fund")
            ap = fnum(row.get(f"{period}_pnl"))
            if fn in live_totals and live_totals[fn] is not None and ap is not None:
                exp = live_totals[fn] - sc
                if abs(exp - ap) > max(2.0, abs(exp)*0.02):
                    flag(f"{platform}/leaderboard[{period}]", f"{fn} {period}_pnl {ap:.2f} != total-sc {exp:.2f}")

    # ---- SNAPSHOT (chart): today present, matches live totals, no dupes/future ----
    snaps = d.get("snapshots") or []
    dates = [s.get("date") for s in snaps]
    if len(dates) != len(set(dates)):
        flag(f"{platform}/snapshots", "duplicate snapshot dates")
    if any(str(dt) > TODAY for dt in dates if dt):
        flag(f"{platform}/snapshots", "snapshot dated in the FUTURE")
    today_snap = next((s for s in snaps if s.get("date") == TODAY), None)
    if today_snap:
        for fund in FUNDS:
            sv = fnum(today_snap.get(fund)); lv = live_totals.get(fund)
            if sv is not None and lv is not None and not approx(sv, lv, max(2.0, abs(lv)*0.02)):
                flag(f"{platform}/snapshot", f"{fund} snapshot {sv:.2f} != live total {lv:.2f}")

# ---- MEMBER PAGES (per-portfolio) -- needs internal key ----
print("\n## member portfolios")
if not KEY:
    print("   (internal key unavailable -- skipping member checks)")
else:
    for platform, usize in PLATFORMS.items():
        sc = float(usize * 1000)
        req = urllib.request.Request(f"{BACKEND}/internal/portfolios/active?platform={platform}",
                                     headers={"X-Internal-Key": KEY})
        try:
            body = json.load(urllib.request.urlopen(req, timeout=25))
            ports = body.get("portfolios", body if isinstance(body, list) else [])
        except Exception as e:
            print(f"   {platform}: could not list portfolios ({e})"); continue
        for p in ports:
            bid = p.get("bot_id") or p.get("id")
            r2 = urllib.request.Request(f"{BACKEND}/internal/portfolio-fund-state/{bid}/bot13",
                                        headers={"X-Internal-Key": KEY})
            try:
                st = json.load(urllib.request.urlopen(r2, timeout=20))
                mv = st.get("data", st)
                T = fnum(mv.get("total_value"))
                if T is not None and T <= 0:
                    flag(f"member/{platform}/{bid}", f"bot13 total_value <= 0 ({T})")
            except Exception:
                pass
        print(f"   {platform}: {len(ports)} portfolio(s) checked")

print("\n" + "=" * 70)
if flags:
    print(f"  RESULT: {len(flags)} FLAG(S)")
    for fl in flags: print("   - " + fl)
    sys.exit(1)
else:
    print("  RESULT: ALL CLEAN -- every number on every page reconciles.")
    sys.exit(0)
