#!/usr/bin/env python3
"""
reset_bitbot13_bot13.py
-----------------------
One-time cleanup: a garbage price feed gave JUP a fake move, so BOT13 on bitbot13
deployed 100% into it and inflated to ~$1.59M, then COMPOUNDED across multiple days
(06-15 -> 06-20) because BOT13 reinvests its whole balance daily.

The engine now has a day-over-day jump guard (refresh_bitbot13.py) so this can't
recur, but the already-corrupted value is still stored in the live tracker state +
every recent snapshot. This script clears it and starts BOT13 fresh from $50k.

Run:  python Project/scripts/reset_bitbot13_bot13.py
Dry:  python Project/scripts/reset_bitbot13_bot13.py --dry
"""
import json, os, sys
from pathlib import Path
import requests

ROOT      = Path(__file__).resolve().parents[2]
SECRETS   = ROOT / "Project" / "config" / "secrets.json"
BACKEND   = "https://wallstbots-backend-868128114349.us-east1.run.app"
PLATFORM  = "bitbot13"
DRY       = "--dry" in sys.argv

LAST_GOOD_TOTAL = 50000.0
LAST_GOOD_DATE  = "2026-06-20"
START_CAP       = 50000.0
SANE_SNAP_CEILING = 250000.0

def internal_key():
    if SECRETS.exists():
        try:
            k = json.loads(SECRETS.read_text(encoding="utf-8")).get("internal_api_key")
            if k:
                return k
        except Exception:
            pass
    return os.environ.get("INTERNAL_API_KEY", "")

def main():
    key = internal_key()
    if not key:
        print("[reset] ERROR: no INTERNAL_API_KEY (secrets.json or env). Aborting.")
        sys.exit(1)

    print("[reset] fetching live bitbot13 state...")
    r = requests.get(f"{BACKEND}/public/tracker/state?platform={PLATFORM}", timeout=20)
    state = r.json().get("data", {})
    if not state or "funds" not in state:
        print("[reset] ERROR: could not read state. Aborting.")
        sys.exit(1)

    b13 = state["funds"].get("bot13")
    if not b13:
        print("[reset] ERROR: no bot13 fund in state. Aborting.")
        sys.exit(1)

    old_total = b13.get("value", {}).get("total")
    print(f"[reset] current BOT13 total = ${old_total:,.2f}  -> resetting to ${LAST_GOOD_TOTAL:,.2f}")

    pnl     = LAST_GOOD_TOTAL - START_CAP
    pnl_pct = round((LAST_GOOD_TOTAL / START_CAP - 1) * 100, 2)
    b13["value"] = {
        "pnl": round(pnl, 2), "cash": LAST_GOOD_TOTAL, "total": LAST_GOOD_TOTAL,
        "day_pct": 0.0, "day_pnl": 0.0, "pnl_pct": pnl_pct,
        "pos_val": 0.0, "day_open": LAST_GOOD_TOTAL, "positions": [],
        "window_open": b13.get("value", {}).get("window_open", False),
        "holding_cash": True,
        "session_open_et": b13.get("value", {}).get("session_open_et", "9:00"),
        "session_close_et": b13.get("value", {}).get("session_close_et", "21:00"),
    }
    b13["current_strategy"] = {
        "day": LAST_GOOD_DATE, "picks": [], "decision": "HOLD",
        "rationale": "Reset after a bad price-feed reading; awaiting next clean session.",
        "session_log": [], "projected_return": 0.0,
    }

    fixed = 0
    for snap in state.get("snapshots", []):
        if snap.get("bot13", 0) > SANE_SNAP_CEILING:
            print(f"[reset]   snapshot {snap.get('date')}: ${snap['bot13']:,.0f} -> ${LAST_GOOD_TOTAL:,.0f}")
            snap["bot13"] = LAST_GOOD_TOTAL
            fixed += 1
    print(f"[reset] fixed {fixed} poisoned snapshot(s)")

    lb = state.get("leaderboards", {}).get("all", [])
    for row in lb:
        if row.get("fund") == "bot13":
            row["all_pnl"] = round(pnl, 2)
            row["all_pct"] = pnl_pct
            row["overall_grade"] = "C"

    if DRY:
        print("[reset] DRY RUN -- corrected BOT13 total/snapshot/leaderboard, NOT pushing.")
        print(json.dumps(b13["value"], indent=2))
        return

    print("[reset] pushing corrected state to backend...")
    pr = requests.post(
        f"{BACKEND}/internal/tracker/push",
        json={"platform": PLATFORM, "data_type": "state", "data": state},
        headers={"x-internal-key": key}, timeout=30,
    )
    if pr.status_code == 200:
        print("[reset] OK -- bitbot13 BOT13 reset to $50k start. Verify the site.")
    else:
        print(f"[reset] PUSH FAILED HTTP {pr.status_code}: {pr.text[:200]}")
        sys.exit(1)

if __name__ == "__main__":
    main()
