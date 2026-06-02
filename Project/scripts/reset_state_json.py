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

    # ── 1. Reset snapshots to today only ──────────────────────────────────────
    today_snapshot = {"date": TODAY}
    for fid in FUND_ORDER:
        today_snapshot[fid] = sc  # all start at starting_capital today
    state_data["snapshots"] = [today_snapshot]
    print(f"  snapshots reset to today ({TODAY}) only")

    # ── 2. Reset each fund's balance to starting_capital ─────────────────────
    for fid in FUND_ORDER:
        fund = funds.get(fid)
        if not fund:
            continue

        fund_sc = float(fund.get("starting_capital", sc))

        # Reset inception to today
        fund["inception"] = TODAY

        # Reset value totals — preserve positions and prices, just zero the P&L
        val = fund.get("value", {})
        if val:
            val["total"]        = fund_sc
            val["pnl"]          = 0.0
            val["pnl_pct"]      = 0.0
            val["day_pnl"]      = 0.0
            val["day_pct"]      = 0.0
            val["day_open"]     = fund_sc

            # For baselines (equalizer/titan): also reset positions entry_price
            # to current price so they start from today's price, not old prices
            if fid in ("equalizer", "titan"):
                positions = val.get("positions", [])
                for pos in positions:
                    # entry_price = today's price (current price IS inception price now)
                    pos["entry_price"] = pos.get("price", pos.get("entry_price", 0))
                    pos["cost_basis"]  = round(float(pos.get("shares", 0)) * float(pos.get("entry_price", 0)), 2)
                    pos["pnl"]         = 0.0
                    pos["pnl_pct"]     = 0.0

        print(f"  {fid}: reset to ${fund_sc:,.2f}, inception={TODAY}")

    # ── 3. Write back ─────────────────────────────────────────────────────────
    out = json.dumps(raw, indent=2, ensure_ascii=False)
    path.write_text(out, encoding="utf-8")
    print(f"  written: {path}")

print("\n[done] All 3 state.json files reset to today as day 1.")
print("Run REFRESH-ALL-PLATFORMS-NOW.bat to push the reset state live.")
