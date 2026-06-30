#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audit_integrity.py -- read-only data-integrity audit for the bot race.

Checks every fund x platform against the live backend and reports a clean bill of
health or a list of flags. Run anytime:

    python Project/scripts/audit_integrity.py

Reads the backend URL from Project/config/secrets.json (no key needed -- uses the
public tracker state endpoint). Exits 0 if all clean, 1 if any flags.

Checks per fund:
  - total > 0 (never zero/negative -- the race never bankrupts a bot)
  - total ~= cash + pos_val            (accounting reconciles)
  - pnl_pct ~= (total - sc) / sc * 100 (P&L matches the total)
  - day reconciles: total ~= day_open + day_pnl (where exposed)
  - no zero/negative position prices
Checks per platform:
  - all 5 funds present
  - (informational) per-fund total + pnl so you can eyeball the standings
"""
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
secrets = {}
sp = ROOT / "Project" / "config" / "secrets.json"
if sp.exists():
    secrets = json.loads(sp.read_text())
BACKEND = (secrets.get("api_url") or "").rstrip("/")
if not BACKEND:
    print("ERROR: api_url not found in secrets.json"); sys.exit(2)

PLATFORMS = ["wallstbots", "aistocks", "bitbot13"]
FUNDS     = ["bot13", "oracle", "wizard", "equalizer", "titan"]

flags = []

def warn(plat, fund, msg):
    flags.append(f"[{plat}/{fund}] {msg}")

def get_state(plat):
    try:
        r = urllib.request.urlopen(BACKEND + f"/public/tracker/state?platform={plat}", timeout=25)
        return json.load(r).get("data", {}) or {}
    except Exception as e:
        warn(plat, "-", f"could not load state: {e}")
        return {}

print("=" * 68)
print("  WallStBots data-integrity audit")
print("=" * 68)

for plat in PLATFORMS:
    d = get_state(plat)
    funds = d.get("funds", {}) or {}
    print(f"\n## {plat}   (last_refresh: {d.get('last_refresh') or d.get('last_updated')})")
    if not funds:
        warn(plat, "-", "no funds in state"); continue

    present = [f for f in FUNDS if f in funds]
    missing = [f for f in FUNDS if f not in funds]
    if missing:
        warn(plat, "-", f"missing funds: {missing}")

    for fund in present:
        f = funds.get(fund) or {}
        v = f.get("value") or f
        sc = f.get("starting_capital")
        total   = v.get("total") or v.get("total_value")
        pos_val = v.get("pos_val")
        cash    = v.get("cash")
        pnl_pct = v.get("pnl_pct")
        day_open= v.get("day_open")
        day_pnl = v.get("day_pnl")
        positions = v.get("positions") or []

        def fnum(x):
            try: return float(x)
            except: return None

        T, PV, CH, PP, SC, DO, DPN = map(fnum, (total, pos_val, cash, pnl_pct, sc, day_open, day_pnl))

        # 1) total > 0
        if T is None:
            warn(plat, fund, "total missing")
        elif T <= 0:
            warn(plat, fund, f"total <= 0 ({T})")

        # 2) total ~= cash + pos_val
        if T is not None and PV is not None and CH is not None:
            eps = max(1.0, T * 0.01)
            if abs(T - (PV + CH)) > eps:
                warn(plat, fund, f"total {T:.2f} != cash {CH:.2f} + pos_val {PV:.2f}")

        # 3) pnl_pct ~= (total - sc)/sc*100
        if T is not None and SC and SC > 0 and PP is not None:
            calc = (T - SC) / SC * 100
            if abs(calc - PP) > 0.5:
                warn(plat, fund, f"pnl_pct {PP:.2f} != calc {calc:.2f} (total {T:.2f}, sc {SC:.2f})")

        # 4) day reconcile (only when both exposed)
        if T is not None and DO is not None and DPN is not None and DO > 0:
            eps = max(1.0, T * 0.01)
            if abs(T - (DO + DPN)) > eps:
                warn(plat, fund, f"total {T:.2f} != day_open {DO:.2f} + day_pnl {DPN:.2f}")

        # 5) no zero/neg position prices
        for p in positions:
            pr = fnum(p.get("price") or p.get("current_price"))
            if pr is not None and pr <= 0:
                warn(plat, fund, f"position {p.get('symbol')} has price {pr}")

        tstr = f"{T:,.2f}" if T is not None else "?"
        pstr = f"{PP:+.2f}%" if PP is not None else "?"
        print(f"   {fund:10} total={tstr:>14}  pnl={pstr:>9}  positions={len(positions)}")

print("\n" + "=" * 68)
if flags:
    print(f"  RESULT: {len(flags)} FLAG(S) FOUND")
    for fl in flags:
        print("   - " + fl)
    sys.exit(1)
else:
    print("  RESULT: ALL CLEAN -- every fund reconciles, no integrity issues.")
    sys.exit(0)
