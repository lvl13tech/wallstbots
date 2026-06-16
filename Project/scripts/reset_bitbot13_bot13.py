#!/usr/bin/env python3
"""
reset_bitbot13_bot13.py
-----------------------
One-time cleanup: a garbage price feed gave JUP a fake +1629% move, so BOT13
on bitbot13 deployed 100% into it and inflated to ~$1.28M. The engine now has a
bad-data guard (bot13_engine.py) so this can't recur, but the corrupted value is
already stored in the live tracker state + the 2026-06-15 snapshot.

This script:
  1. Fetches the live bitbot13 'state' from the backend.
  2. Resets BOT13's value to the last-good level (June-11 snapshot) and clears
     its bad JUP position + current_strategy (so the guarded engine rebuilds it
     cleanly on the next refresh).
  3. Removes the poisoned 2026-06-15 BOT13 snapshot value (sets it to last-good).
  4. Recomputes the BOT13 'all'/'leaderboard' grade off the corrected total.
  5. Pushes the corrected state back via /internal/tracker/push.

Reads INTERNAL_API_KEY from Project/config/secrets.json or env. UTF-8 safe.
Run:  python Project/scripts/reset_bitbot13_bot13.py
Dry run (prints, no push):  python Project/scripts/reset_bitbot13_bot13.py --dry
"""
import json, os, sys
from pathlib import Path
import requests

ROOT      = Path(__file__).resolve().parents[2]
SECRETS   = ROOT / "Project" / "config" / "secrets.json"
BACKEND   = "https://wallstbots-backend-868128114349.us-east1.run.app"
PLATFORM  = "bitbot13"
DRY       = "--dry" in sys.argv

# Last-good BOT13 value for bitbot13 — the June-11 snapshot (before the bad data).
LAST_GOOD_TOTAL = 66436.70
LAST_GOOD_DATE  = "2026-06-11"
BAD_DATE        = "2026-06-15"
START_CAP       = 50000.0

def internal_key():
    if SECRETS.exists():
        try:
            k = json.loads(SECRETS.read_text(encoding="utf-8")).get("internal_api_key")
            if k: return k
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

    # 1. Reset BOT13 value to last-good, flat/cash (guarded engine rebuilds next run)
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
    # Clear the bad current_strategy so the page shows a clean 'holding cash' state
    b13["current_strategy"] = {
        "day": LAST_GOOD_DATE, "picks": [], "decision": "HOLD",
        "rationale": "Reset after a bad price-feed reading; awaiting next clean session.",
        "session_log": [], "projected_return": 0.0,
    }

    # 2. Fix the poisoned snapshot: set the BAD_DATE bot13 value to last-good
    fixed = 0
    for snap in state.get("snapshots", []):
        if snap.get("date") == BAD_DATE and snap.get("bot13", 0) > 500000:
            snap["bot13"] = LAST_GOOD_TOTAL
            fixed += 1
    print(f"[reset] fixed {fixed} poisoned snapshot(s) for {BAD_DATE}")

    # 3. Fix the leaderboard 'all' entry for bot13 off the corrected total
    lb = state.get("leaderboards", {}).get("all", [])
    for row in lb:
        if row.get("fund") == "bot13":
            row["all_pnl"] = round(pnl, 2)
            row["all_pct"] = pnl_pct
            row["overall_grade"] = "B"  # recompute happens naturally next refresh
    if DRY:
        print("[reset] DRY RUN — corrected BOT13 total/snapshot/leaderboard, NOT pushing.")
        print(json.dumps(b13["value"], indent=2))
        return

    # 4. Push corrected state back
    print("[reset] pushing corrected state to backend...")
    pr = requests.post(
        f"{BACKEND}/internal/tracker/push",
        json={"platform": PLATFORM, "data_type": "state", "data": state},
        headers={"x-internal-key": key}, timeout=30,
    )
    if pr.status_code == 200:
        print("[reset] OK — bitbot13 BOT13 reset to last-good. Verify the site.")
    else:
        print(f"[reset] PUSH FAILED HTTP {pr.status_code}: {pr.text[:200]}")
        sys.exit(1)

if __name__ == "__main__":
    main()
