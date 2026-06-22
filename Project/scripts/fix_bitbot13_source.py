#!/usr/bin/env python3
"""
fix_bitbot13_source.py
-----------------------
Real fix for the bitbot13 BOT13 JUP-inflation bug, this time at the SOURCE.

Why the earlier reset (reset_bitbot13_bot13.py) didn't stick for 3 days:
  refresh_bitbot13.py reads Frontends/bitbot13.tech/data/state.json from DISK as its
  starting point on every cron run (only falls back to the live API if that file is
  missing/corrupt). The earlier reset script only POSTed a corrected blob to the
  live backend cache (/internal/tracker/push) -- it never touched state.json on disk.
  So every cron cycle re-read the OLD $1.62M total from disk, carried it forward
  (the >4x guard didn't fire because it wasn't a NEW jump, just the same old number
  repeating), wrote a fresh state.json with the same bad number, and the script's own
  git_push() committed+pushed that bad file right back into the repo. Then it also
  pushed the same bad number to the backend cache, undoing any manual fix.

This script fixes, in order:
  1. Frontends/bitbot13.tech/data/state.json on disk (bot13 value, BOTH leaderboard
     rows ('week' AND 'all' -- the earlier fix only caught 'all'), snapshots array
     values AND length).
  2. The live backend public cache (/internal/tracker/push) -- same corrected blob.
  3. The one active bitbot13 member portfolio's bot_fund_state row for bot13
     (found corrupted at $875,649.91 / +3143.15%, matching the same bad lineage)
     via /internal/portfolio-bot-state/upsert.

Run:  python fix_bitbot13_source.py --dry     (show what would change, touch nothing)
      python fix_bitbot13_source.py            (apply everywhere)
"""
import json, os, sys
from pathlib import Path
import requests

ROOT       = Path(__file__).resolve().parents[2]  # repo root (this file lives in Project/scripts/)
STATE_FILE = ROOT / "Frontends" / "bitbot13.tech" / "data" / "state.json"
SECRETS    = ROOT / "Project" / "config" / "secrets.json"
BACKEND    = "https://wallstbots-backend-868128114349.us-east1.run.app"
PLATFORM   = "bitbot13"
DRY        = "--dry" in sys.argv

LAST_GOOD_TOTAL = 50000.0
START_CAP       = 50000.0
TODAY_ISO       = "2026-06-22"
SANE_SNAP_CEILING = 250000.0
MAX_SNAPSHOTS   = 1  # keep only today's flattened snapshot; old poisoned history dropped

MEMBER_BOT_ID  = "f74ae1f8-4c8b-4fcc-9591-4d2d8cf91746"  # the one active bitbot13 portfolio


def internal_key():
    if SECRETS.exists():
        try:
            k = json.loads(SECRETS.read_text(encoding="utf-8")).get("internal_api_key")
            if k:
                return k
        except Exception:
            pass
    return os.environ.get("INTERNAL_API_KEY", "")


def fix_state_blob(state):
    """Mutate a tracker state dict (same shape on disk and in the live API) in place."""
    funds = state.get("funds", {})
    b13 = funds.get("bot13")
    if not b13:
        print("[fix] ERROR: no bot13 fund in state blob -- skipping this blob")
        return state

    old_total = b13.get("value", {}).get("total")
    print(f"[fix]   bot13.value.total: ${old_total:,.2f} -> ${LAST_GOOD_TOTAL:,.2f}")

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
        "trade_log": [],
    }
    b13["current_strategy"] = {
        "day": TODAY_ISO, "picks": [], "decision": "HOLD",
        "rationale": "Reset after a bad price-feed reading; awaiting next clean session.",
        "session_log": [], "projected_return": 0.0,
    }

    # Snapshots: flatten EVERY poisoned bot13 value, then truncate the array itself
    # (per feedback_full_reset_not_partial.md -- stale array LENGTH alone inflates
    # downstream "days" stats even after every value inside it is corrected).
    snaps = state.get("snapshots", [])
    fixed = 0
    for snap in snaps:
        if snap.get("bot13", 0) > SANE_SNAP_CEILING:
            snap["bot13"] = LAST_GOOD_TOTAL
            fixed += 1
    print(f"[fix]   flattened {fixed} poisoned snapshot value(s)")
    if len(snaps) > MAX_SNAPSHOTS:
        print(f"[fix]   truncating snapshots array: {len(snaps)} -> {MAX_SNAPSHOTS} entries (drop stale history)")
        if MAX_SNAPSHOTS > 0:
            del snaps[:-MAX_SNAPSHOTS]
            snaps[-1]["bot13"] = LAST_GOOD_TOTAL
            snaps[-1]["date"] = TODAY_ISO
        else:
            snaps.clear()

    # Leaderboards: BOTH 'week' and 'all' rows (earlier fix only patched 'all')
    lb = state.get("leaderboards", {})
    for period, rows in lb.items():
        for row in rows:
            if row.get("fund") == "bot13":
                if period == "all":
                    row["all_pnl"] = round(pnl, 2)
                    row["all_pct"] = pnl_pct
                    row["overall_grade"] = "C"
                elif period == "week":
                    row["week_pnl"] = 0.0
                    row["week_pct"] = 0.0
                    row["week_grade"] = "C"
                print(f"[fix]   leaderboard[{period}] bot13 row corrected")

    return state


def main():
    key = internal_key()
    if not key:
        print("[fix] ERROR: no INTERNAL_API_KEY. Aborting.")
        sys.exit(1)
    headers = {"x-internal-key": key}

    # ---- LAYER 1: state.json on disk (the actual source refresh_bitbot13.py reads) ----
    print("\n=== LAYER 1: Frontends/bitbot13.tech/data/state.json (on disk) ===")
    raw = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    data = raw.get("data", raw)
    fix_state_blob(data)

    if DRY:
        print("\n[fix] DRY RUN -- state.json NOT written.")
    else:
        STATE_FILE.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        print(f"[fix] wrote corrected {STATE_FILE}")

    # ---- LAYER 2: live backend public cache ----
    print("\n=== LAYER 2: live backend cache (/public/tracker/state) ===")
    r = requests.get(f"{BACKEND}/public/tracker/state?platform={PLATFORM}", timeout=20)
    live_state = r.json().get("data", {})
    fix_state_blob(live_state)

    if DRY:
        print("[fix] DRY RUN -- backend cache NOT pushed.")
    else:
        pr = requests.post(
            f"{BACKEND}/internal/tracker/push",
            json={"platform": PLATFORM, "data_type": "state", "data": live_state},
            headers=headers, timeout=30,
        )
        print(f"[fix] backend push -> HTTP {pr.status_code}")
        if pr.status_code != 200:
            print(f"[fix]   {pr.text[:300]}")

    # ---- LAYER 3: member-side bot_fund_state row for bot13 ----
    print(f"\n=== LAYER 3: member portfolio {MEMBER_BOT_ID} -- bot_fund_state.bot13 ===")
    r = requests.get(
        f"{BACKEND}/internal/portfolio-fund-state/{MEMBER_BOT_ID}/bot13",
        headers=headers, timeout=20,
    )
    before = r.json().get("state")
    print(f"[fix]   before: total_value={before['total_value'] if before else None} "
          f"gain_loss_pct={before['gain_loss_pct'] if before else None}")

    if DRY:
        print("[fix] DRY RUN -- member bot_fund_state NOT changed.")
    else:
        upsert_payload = {
            "bot_id": MEMBER_BOT_ID,
            "fund_name": "bot13",
            "snapshot_date": TODAY_ISO,
            "positions": [],
            "strategy": {
                "day": TODAY_ISO, "picks": [], "decision": "HOLD",
                "rationale": "Reset after a bad price-feed reading; awaiting next clean session.",
                "session_log": [], "projected_return": 0.0,
            },
            "total_value": LAST_GOOD_TOTAL,
            "entry_cost": START_CAP,
            "gain_loss": 0.0,
            "gain_loss_pct": 0.0,
            "day_pnl": 0.0,
            "day_pct": 0.0,
            "window_open": False,
            "holding_cash": True,
            "trade_log": [],
        }
        pr = requests.post(
            f"{BACKEND}/internal/portfolio-bot-state/upsert",
            json=upsert_payload, headers=headers, timeout=30,
        )
        print(f"[fix]   upsert -> HTTP {pr.status_code}")
        if pr.status_code != 200:
            print(f"[fix]   {pr.text[:300]}")
        else:
            r2 = requests.get(
                f"{BACKEND}/internal/portfolio-fund-state/{MEMBER_BOT_ID}/bot13",
                headers=headers, timeout=20,
            )
            after = r2.json().get("state")
            print(f"[fix]   after:  total_value={after['total_value']} gain_loss_pct={after['gain_loss_pct']}")

        # Re-run the portfolio-fund-snapshots refresh so bot_performance_snapshots
        # (sourced from equalizer, already sane) reflects today's date cleanly.
        pr3 = requests.post(
            f"{BACKEND}/internal/portfolio-fund-snapshots/refresh",
            json={"platform": PLATFORM}, headers=headers, timeout=30,
        )
        print(f"[fix]   portfolio-fund-snapshots refresh -> HTTP {pr3.status_code} {pr3.text[:150]}")

    print("\n[fix] DONE." if not DRY else "\n[fix] DRY RUN COMPLETE -- nothing written.")


if __name__ == "__main__":
    main()
