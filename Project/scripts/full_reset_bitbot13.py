#!/usr/bin/env python3
"""
full_reset_bitbot13.py
-----------------------
FULL RESET for bitbot13.tech — all 5 bots, all history DELETED (not edited in
place), at every layer. This is the owner's standing definition of "full reset"
(see project memory feedback_full_reset_not_partial.md) — run this any time a
"full reset" is requested for this platform; do not ask whether to delete vs.
correct, deletion is the standing answer.

Why this script exists (history):
  - reset_bitbot13_bot13.py only patched the live backend's public cache. It never
    touched Frontends/bitbot13.tech/data/state.json on disk, which refresh_bitbot13.py
    reads as its actual source of truth every cron cycle — so the bad number kept
    coming back for 3 days (see feedback_never_patch_blindly.md).
  - A later attempt flattened bad VALUES but kept old snapshot rows/array entries in
    place — the owner explicitly rejected this: "delete all historical data... so
    this data cannot even be accessed again," not just "make the numbers agree."

What this script does, for ALL 5 bots (bot13, oracle, wizard, equalizer, titan):
  1. Frontends/bitbot13.tech/data/state.json (DISK — the cron source of truth):
     - DELETES every entry in `snapshots[]` (the whole array, not just bad rows).
     - Resets every fund's `value` to a clean $50k baseline, zero pnl, no positions.
     - Resets EVERY leaderboard period key (all/week/today/etc.), every fund row.
     - Clears `current_strategy` / trade_log for every fund.
  2. Live backend public cache (/internal/tracker/push) — same corrected, history-free
     blob, so the site reflects the reset immediately instead of waiting on cron.
  3. Member DB layer, for every active bitbot13 portfolio:
     - DELETES all bot_performance_snapshots rows (new endpoint:
       POST /internal/portfolio-fund-snapshots/wipe) — the only true history table
       on the member side. This is a hard delete; rows are not retrievable after.
     - Resets bot_fund_state for all 5 funds per portfolio to the clean baseline
       (this table is already one-row-per-fund/upsert, so "reset" = overwrite it
       clean — there is no separate history row to delete here).

Run:  python Project/scripts/full_reset_bitbot13.py --dry     (show changes, touch nothing)
      python Project/scripts/full_reset_bitbot13.py            (apply everywhere)
"""
import json, os, sys
from pathlib import Path
import requests

ROOT       = Path(__file__).resolve().parents[2]
STATE_FILE = ROOT / "Frontends" / "bitbot13.tech" / "data" / "state.json"
SECRETS    = ROOT / "Project" / "config" / "secrets.json"
BACKEND    = "https://wallstbots-backend-868128114349.us-east1.run.app"
PLATFORM   = "bitbot13"
DRY        = "--dry" in sys.argv

START_CAP = 50000.0
TODAY_ISO = "2026-06-22"
BOTS      = ["bot13", "oracle", "wizard", "equalizer", "titan"]


def internal_key():
    if SECRETS.exists():
        try:
            k = json.loads(SECRETS.read_text(encoding="utf-8")).get("internal_api_key")
            if k:
                return k
        except Exception:
            pass
    return os.environ.get("INTERNAL_API_KEY", "")


def clean_fund_value(prior_value=None):
    return {
        "pnl": 0.0, "cash": START_CAP, "total": START_CAP,
        "day_pct": 0.0, "day_pnl": 0.0, "pnl_pct": 0.0,
        "pos_val": 0.0, "day_open": START_CAP, "positions": [],
        "window_open": (prior_value or {}).get("window_open", False),
        "holding_cash": True,
        "session_open_et": (prior_value or {}).get("session_open_et", "9:00"),
        "session_close_et": (prior_value or {}).get("session_close_et", "21:00"),
        "trade_log": [],
    }


def clean_strategy():
    return {
        "day": TODAY_ISO, "picks": [], "decision": "HOLD",
        "rationale": "Full reset — starting fresh from the next trading day.",
        "session_log": [], "projected_return": 0.0,
    }


def full_reset_state_blob(state):
    """Mutate a tracker state dict (same shape on disk and in the live API) in place.
    Resets ALL 5 bots and DELETES all snapshot history (the whole array)."""
    funds = state.get("funds", {})
    for bot in BOTS:
        fund = funds.get(bot)
        if not fund:
            print(f"[reset]   WARNING: no '{bot}' fund in this blob — skipping")
            continue
        old_total = fund.get("value", {}).get("total")
        print(f"[reset]   {bot}: ${old_total:,.2f} -> ${START_CAP:,.2f} (clean baseline)")
        fund["value"] = clean_fund_value(fund.get("value"))
        fund["current_strategy"] = clean_strategy()

    # Snapshots: DELETE the entire array — owner's explicit instruction is that old
    # history must not be readable afterward, not merely corrected in place.
    n_before = len(state.get("snapshots", []))
    state["snapshots"] = []
    print(f"[reset]   snapshots: deleted all {n_before} historical entries (array is now empty)")

    # Leaderboards: reset EVERY period key (all/week/today/...), every bot row.
    lb = state.get("leaderboards", {})
    for period, rows in lb.items():
        for row in rows:
            fund_name = row.get("fund")
            if fund_name in BOTS:
                for k in list(row.keys()):
                    if k == "fund":
                        continue
                    if "grade" in k:
                        row[k] = "C"
                    else:
                        row[k] = 0.0
        print(f"[reset]   leaderboard[{period}]: all bot rows reset to zero baseline")

    return state


def main():
    key = internal_key()
    if not key:
        print("[reset] ERROR: no INTERNAL_API_KEY. Aborting.")
        sys.exit(1)
    headers = {"x-internal-key": key}

    print("=" * 70)
    print("FULL RESET — bitbot13.tech — ALL 5 BOTS — DELETING ALL HISTORY")
    print("=" * 70)

    # ---- LAYER 1: state.json on disk (the actual source refresh_bitbot13.py reads) ----
    print("\n=== LAYER 1: Frontends/bitbot13.tech/data/state.json (on disk) ===")
    raw = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    data = raw.get("data", raw)
    full_reset_state_blob(data)

    if DRY:
        print("\n[reset] DRY RUN -- state.json NOT written.")
    else:
        STATE_FILE.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        print(f"[reset] wrote corrected {STATE_FILE}")

    # ---- LAYER 2: live backend public cache ----
    print("\n=== LAYER 2: live backend cache (/public/tracker/state) ===")
    r = requests.get(f"{BACKEND}/public/tracker/state?platform={PLATFORM}", timeout=20)
    live_state = r.json().get("data", {})
    full_reset_state_blob(live_state)

    if DRY:
        print("[reset] DRY RUN -- backend cache NOT pushed.")
    else:
        pr = requests.post(
            f"{BACKEND}/internal/tracker/push",
            json={"platform": PLATFORM, "data_type": "state", "data": live_state},
            headers=headers, timeout=30,
        )
        print(f"[reset] backend push -> HTTP {pr.status_code}")
        if pr.status_code != 200:
            print(f"[reset]   {pr.text[:300]}")

    # ---- LAYER 3: member DB — delete bot_performance_snapshots history + reset bot_fund_state ----
    print(f"\n=== LAYER 3: member DB — all active {PLATFORM} portfolios ===")
    r = requests.get(f"{BACKEND}/internal/portfolios/active?platform={PLATFORM}",
                      headers=headers, timeout=20)
    if r.status_code != 200:
        print(f"[reset]   WARNING: could not list active portfolios (HTTP {r.status_code}): {r.text[:200]}")
        portfolios = []
    else:
        body = r.json()
        portfolios = body.get("portfolios", body if isinstance(body, list) else [])

    bot_ids = [p.get("bot_id") or p.get("id") for p in portfolios] if portfolios else []
    print(f"[reset]   found {len(bot_ids)} active portfolio(s): {bot_ids}")

    if DRY:
        print("[reset] DRY RUN -- bot_performance_snapshots NOT wiped, bot_fund_state NOT reset.")
    else:
        # 3a. Hard-delete ALL snapshot history rows for this platform (new endpoint).
        wr = requests.post(
            f"{BACKEND}/internal/portfolio-fund-snapshots/wipe",
            json={"platform": PLATFORM}, headers=headers, timeout=30,
        )
        print(f"[reset]   portfolio-fund-snapshots WIPE -> HTTP {wr.status_code} {wr.text[:200]}")

        # 3b. Reset bot_fund_state for all 5 funds, every active portfolio, to clean baseline.
        for bot_id in bot_ids:
            results = []
            for fund in BOTS:
                results.append({
                    "bot_id": bot_id,
                    "fund_name": fund,
                    "positions": [],
                    "strategy": clean_strategy(),
                    "total_value": START_CAP,
                    "entry_cost": START_CAP,
                    "gain_loss": 0.0,
                    "gain_loss_pct": 0.0,
                    "day_pnl": 0.0,
                    "day_pct": 0.0,
                    "window_open": False,
                    "holding_cash": True,
                    "trade_log": [],
                })
            ur = requests.post(
                f"{BACKEND}/internal/portfolio-bot-state/upsert",
                json={"results": results}, headers=headers, timeout=30,
            )
            print(f"[reset]   portfolio {bot_id}: bot_fund_state reset (all 5 funds) -> HTTP {ur.status_code}")
            if ur.status_code != 200:
                print(f"[reset]     {ur.text[:300]}")

        # Re-run the snapshot refresh so today's date has a single clean baseline row
        # (sourced from equalizer, now clean) instead of zero rows looking broken.
        pr3 = requests.post(
            f"{BACKEND}/internal/portfolio-fund-snapshots/refresh",
            json={"platform": PLATFORM}, headers=headers, timeout=30,
        )
        print(f"[reset]   portfolio-fund-snapshots refresh (seed today) -> HTTP {pr3.status_code} {pr3.text[:150]}")

    print("\n[reset] FULL RESET COMPLETE." if not DRY else "\n[reset] DRY RUN COMPLETE -- nothing written or deleted.")


if __name__ == "__main__":
    main()
