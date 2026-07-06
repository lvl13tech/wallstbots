#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
repair_member_states.py -- ONE-TIME surgical repair of corrupt member fund-states
(owner-approved 2026-07-06).

WHY: before the member engine became truly independent, member dollar values were
scaled from the platform tracker. That era left platform-scale dollars ($50k/$55k
day-opens), impossible carried totals (+260% on a $20,000 portfolio), and fabricated
$1.00 entry prices (unpriced crypto seeds) inside bot_fund_state rows. The database
holds NO real member entries from that era (bot_holdings.entry_price is empty, member
trades were never stored), so there is no true history to reconstruct -- per the Day-1
rule the only honest repair is: restart the CORRUPT fund-states at the member's own
N x $1,000 with trading beginning at the next real session. Healthy fund-states (the
ones the independent engine already rebuilt from real entries) are NOT touched.
Nothing is deleted -- old rows/snapshots stay in the DB as the audit trail, and the
frontend era-guard starts charts at the repair boundary automatically.

DETECTION (a state is corrupt if ANY of):
  (a) LEAK ............ strategy._day_open ~= the PLATFORM starting capital while the
                        member's own entry_cost differs materially
  (b) IMPOSSIBLE MOVE . |day_pct| > 30% (equity) / 50% (crypto) in one day
  (c) FABRICATED SEED . any stored position with entry_price == 1.0 exactly
                        (the old "no price -> $1.00 entry" fallback)
  (d) NOT OWN-DERIVED . total_value differs >1% from the sum of the state's own
                        position values (+ idle cash for equalizer/titan)
  (e) IMPOSSIBLE CARRY  total_value > 1.5x entry_cost (no member fund can have
                        legitimately earned +50% in the few days since the engines
                        became independent -- one-time criterion for THIS repair)

USAGE:
    python Project/scripts/repair_member_states.py            (dry run: report only)
    python Project/scripts/repair_member_states.py --apply    (write the repairs)
"""
import json, sys, urllib.request
from pathlib import Path
from datetime import datetime, date
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bot13_engine import next_trading_day, EQUITY_CFG, CRYPTO_CFG

ROOT = Path(__file__).resolve().parents[2]
secrets = json.loads((ROOT / "Project" / "config" / "secrets.json").read_text())
BACKEND = (secrets.get("api_url") or "").rstrip("/")
KEY     = secrets.get("internal_api_key") or ""
if not BACKEND or not KEY:
    print("ERROR: api_url / internal_api_key missing from secrets.json"); sys.exit(2)

APPLY     = "--apply" in sys.argv
PLATFORMS = {"wallstbots": (55, EQUITY_CFG), "aistocks": (50, EQUITY_CFG), "bitbot13": (50, CRYPTO_CFG)}
FUNDS     = ["bot13", "oracle", "wizard", "equalizer", "titan"]
TODAY     = datetime.now(ZoneInfo("America/New_York")).date()

def get(url, key=None):
    # 3 attempts with backoff -- a single transient read timeout must not kill a repair
    # run (it did on 2026-07-06: the APPLY pass crashed mid-scan on one slow response).
    import time
    last = None
    for attempt in range(3):
        u = url + ("&" if "?" in url else "?") + "_ab=" + datetime.now().strftime("%Y%m%d%H%M%S%f")
        req = urllib.request.Request(u, headers={"Cache-Control": "no-cache"})
        if key: req.add_header("x-internal-key", key)
        try:
            return json.load(urllib.request.urlopen(req, timeout=30))
        except Exception as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise last

def post(url, payload, key):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", "x-internal-key": key})
    return json.load(urllib.request.urlopen(req, timeout=30))

def fnum(x):
    try: return float(x)
    except Exception: return None

repairs, kept = [], []
for platform, (usize, cfg) in PLATFORMS.items():
    sc = float(usize * 1000)
    move_cap = 50.0 if platform == "bitbot13" else 30.0
    ports = get(f"{BACKEND}/internal/portfolios/active?platform={platform}", KEY).get("portfolios", [])
    for p in ports:
        bid = p["bot_id"]; n = len(p.get("holdings") or []); ec_true = n * 1000.0
        _port_repairs, _port_kept = [], []   # per-portfolio buckets (see escalation below)
        for fund in FUNDS:
            st = (get(f"{BACKEND}/internal/portfolio-fund-state/{bid}/{fund}", KEY) or {}).get("state")
            if not st: continue
            tv  = fnum(st.get("total_value")); ec = fnum(st.get("entry_cost")) or ec_true
            dpc = fnum(st.get("day_pct")) or 0.0
            strat = st.get("strategy") if isinstance(st.get("strategy"), dict) else {}
            mdo = fnum(strat.get("_day_open"))
            pos = st.get("positions") if isinstance(st.get("positions"), list) else []
            reasons = []
            if mdo is not None and abs(ec - sc) > max(2.0, sc*0.001) and abs(mdo - sc) <= max(2.0, sc*0.001):
                reasons.append(f"LEAK _day_open={mdo}==platform sc {sc}")
            if abs(dpc) > move_cap:
                reasons.append(f"IMPOSSIBLE MOVE day_pct={dpc}%")
            if any(fnum(x.get("entry_price")) == 1.0 for x in pos):
                reasons.append("FABRICATED $1.00 entry in stored positions")
            if pos and tv is not None:
                sumval  = sum(fnum(x.get("value")) or 0 for x in pos)
                sumcost = sum(fnum(x.get("cost_basis")) or 0 for x in pos)
                exp = sumval + (max(0.0, ec - sumcost) if fund in ("equalizer","titan") else 0.0)
                if abs(tv - exp) > max(1.0, abs(tv)*0.01):
                    reasons.append(f"NOT OWN-DERIVED tv={tv} vs own positions {round(exp,2)}")
            if tv is not None and ec and tv > ec * 1.5:
                reasons.append(f"IMPOSSIBLE CARRY tv={tv} > 1.5x cost {ec}")
            tag = f"{platform}/{str(bid)[:8]}/{fund}"
            try:    starts = next_trading_day(cfg, TODAY).isoformat()
            except Exception: starts = ""
            _entry = {"tag": tag, "before": f"tv={tv} glp={st.get('gain_loss_pct')} day_open={mdo}",
                      "reasons": reasons, "state": {
                "bot_id": bid, "fund_name": fund, "positions": [], "trade_log": [],
                "strategy": {"decision": "PENDING", "pending": True, "starts_on": starts,
                             "rationale": f"Fund restarted at its own starting capital (data repair "
                                          f"{TODAY.isoformat()}). Trading begins {starts}.",
                             "_day_open": round(ec_true, 2), "_asof": TODAY.isoformat()},
                "total_value": round(ec_true, 2), "entry_cost": round(ec_true, 2),
                "gain_loss": 0.0, "gain_loss_pct": 0.0, "day_pnl": 0.0, "day_pct": 0.0,
                "window_open": False, "holding_cash": True, "traded_today": False, "closed_out": False,
            }}
            if reasons:
                _port_repairs.append(_entry)
            else:
                _port_kept.append(_entry)

        # PORTFOLIO-WIDE RESET (owner rule 2026-07-06): "on a reset every bot on that page
        # needs to be reset." A member's 5 funds share one page and one story -- if ANY fund
        # in a portfolio is corrupt, ALL 5 restart together at the member's own N x $1,000.
        # Funds in fully-healthy portfolios are never touched.
        if _port_repairs:
            for e in _port_kept:
                e["reasons"] = ["PORTFOLIO-WIDE RESET: sibling fund(s) corrupt -- every bot on the "
                                "member's page restarts together (owner rule)"]
            repairs.extend(_port_repairs + _port_kept)
        else:
            kept.extend(f"{e['tag']}  {e['before']}  (healthy -- untouched)" for e in _port_kept)

print("=" * 78)
print(f"  MEMBER FUND-STATE REPAIR  --  {TODAY.isoformat()}  --  mode: {'APPLY' if APPLY else 'DRY RUN'}")
print("=" * 78)
print(f"\nHEALTHY (untouched): {len(kept)}")
for k in kept: print("   OK  " + k)
print(f"\nCORRUPT (to repair): {len(repairs)}")
for r in repairs:
    print(f"   XX  {r['tag']}  {r['before']}")
    for rs in r["reasons"]: print(f"         - {rs}")
    print(f"         -> restart at own cost ${r['state']['total_value']:,.2f}, trading begins {r['state']['strategy']['starts_on']}")

if not APPLY:
    print("\nDRY RUN ONLY -- nothing written. Re-run with --apply to write the repairs.")
    sys.exit(0)
if not repairs:
    print("\nNothing to repair."); sys.exit(0)

res = post(f"{BACKEND}/internal/portfolio-bot-state/upsert", {"results": [r["state"] for r in repairs]}, KEY)
print(f"\nUPSERTED: {res.get('upserted')} states")
print("Done. Run the audit (RUN-AUDIT.bat) to confirm all member checks now pass.")
sys.exit(0)
