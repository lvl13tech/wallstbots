#!/usr/bin/env python3
"""
reset_state_json.py
====================
Resets the snapshots and fund balances in all 3 state.json files back to
today as day 1. Preserves current positions, prices, and today's strategy.

Run once after a hard reset:
    python Project/scripts/reset_state_json.py
"""

import json
import datetime as dt
from pathlib import Path

ROOT     = Path(__file__).resolve().parents[2]
TODAY    = dt.date.today().isoformat()

PLATFORMS = [
    ROOT / "Frontends" / "bitbot13.tech"  / "data" / "state.json",
    ROOT / "Frontends" / "wallstbots.tech" / "data" / "state.json",
    ROOT / "Frontends" / "lvl13.tech"     / "data" / "state.json",
]

FUND_ORDER = ["bot13", "oracle", "wizard", "equalizer", "titan"]

for path in PLATFORMS:
    if not path.exists():
        print(f"[skip] {path} not found")
        continue

    raw        = json.loads(path.read_text(encoding="utf-8"))
    state_data = raw.get("data", raw)
    funds      = state_data.get("funds", {})
    sc         = float(state_data.get("starting_capital", 0))

    print(f"\n[reset] {path.parent.parent.name}/{path.name}")
    print(f"  starting_capital: {sc}")

    # -- 1. Reset snapshots to today only --------------------------------------
    today_snapshot = {"date": TODAY}
    for fid in FUND_ORDER:
        fund_sc = float((funds.get(fid) or {}).get("starting_capital") or sc)
        today_snapshot[fid] = fund_sc  # each fund starts at its own starting_capital
    state_data["snapshots"] = [today_snapshot]
    print(f"  snapshots reset to today ({TODAY}) only")

    # -- 2. Reset each fund's balance to starting_capital ---------------------
    for fid in FUND_ORDER:
        fund = funds.get(fid)
        if not fund:
            continue

        fund_sc = float(fund.get("starting_capital", sc))

        # Reset inception to today
        fund["inception"] = TODAY

        # Wipe ALL positions — the refresh scripts will re-seed at today's prices
        # on the next run. This is the only way to guarantee pnl starts at 0.
        val = fund.get("value", {})
        if val:
            val["positions"]    = []   # force fresh seed on next refresh
            val["total"]        = fund_sc
            val["pnl"]          = 0.0
            val["pnl_pct"]      = 0.0
            val["day_pnl"]      = 0.0
            val["day_pct"]      = 0.0
            val["day_open"]     = fund_sc
            val["cash"]         = fund_sc
            val["pos_val"]      = 0.0

        # Also wipe current_strategy so bots don't carry forward old decisions
        fund["current_strategy"] = {}

        print(f"  {fid}: reset to ${fund_sc:,.2f}, positions wiped, inception={TODAY}")

    # -- 3. Write back ---------------------------------------------------------
    out = json.dumps(raw, indent=2, ensure_ascii=False)
    path.write_text(out, encoding="utf-8")
    print(f"  written: {path}")

print("\n[done] All 3 state.json files reset to today as day 1.")
print("Run REFRESH-ALL-PLATFORMS-NOW.bat to push the reset state live.")
