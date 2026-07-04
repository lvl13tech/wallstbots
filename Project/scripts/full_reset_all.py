#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
full_reset_all.py -- FINAL full reset for ALL 3 platforms, ALL 5 funds.

Owner's standing definition of "full reset" = HARD DELETE all history at every layer
(not edit-in-place). Starts the multi-year race clean at $1,000 x universe size:
  wallstbots = 55 assets -> $55,000
  aistocks   = 50 assets -> $50,000
  bitbot13   = 50 assets -> $50,000

Authoritative source is the BACKEND (all 3 engines fall back to the live API, and
several committed disk state.json files are NUL-corrupted anyway). So this resets:
  LAYER 1: backend public cache  (/internal/tracker/push)   -- what every site reads
  LAYER 2: member DB             -- wipe bot_performance_snapshots (hard delete) +
                                    reset bot_fund_state for all 5 funds/portfolio +
                                    reseed one clean snapshot row
  LAYER 3: disk state.json       -- write CLEAN (NUL-free) reset JSON for wallstbots +
                                    bitbot13 (they read disk first); aistocks is
                                    backend-driven so disk is informational only.

Uses the backend's own current state blob as the structural template (guaranteed the
right shape per platform), then zeroes it. Reads internal key from secrets.json.

Run:  python Project/scripts/full_reset_all.py --dry   (show, touch nothing)
      python Project/scripts/full_reset_all.py          (apply everywhere)
"""
import json, os, sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from datetime import date as _date, timedelta as _timedelta
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bot13_engine import is_trading_day as _is_trading_day, EQUITY_CFG as _EQ_CFG, CRYPTO_CFG as _CR_CFG

def _last_trading_day(cfg, d):
    """Most recent real trading day on/before d (skips weekends + US market holidays)."""
    for _ in range(10):
        if _is_trading_day(cfg, d):
            return d
        d = d - _timedelta(days=1)
    return d
import requests

ROOT     = Path(__file__).resolve().parents[2]
SECRETS  = ROOT / "Project" / "config" / "secrets.json"
BACKEND  = "https://wallstbots-backend-868128114349.us-east1.run.app"
DRY      = "--dry" in sys.argv
# SAFETY: target a single platform with --platform <name>; reset ALL only with --all.
# This prevents accidentally wiping every site when you meant to fix just one.
_TARGET = None
for _i, _a in enumerate(sys.argv):
    if _a == "--platform" and _i + 1 < len(sys.argv):
        _TARGET = sys.argv[_i + 1].strip().lower()
_ALL = "--all" in sys.argv
TODAY    = datetime.now(ZoneInfo("America/New_York")).date().isoformat()
BOTS     = ["bot13", "oracle", "wizard", "equalizer", "titan"]

# platform -> (universe size, disk state path or None if backend-only-authoritative)
PLATFORMS = {
    "wallstbots": (55, ROOT / "Frontends" / "wallstbots.tech" / "data" / "state.json"),
    "aistocks":   (50, None),  # backend-driven; disk file ignored/overwritten by engine
    "bitbot13":   (50, ROOT / "Frontends" / "bitbot13.tech" / "data" / "state.json"),
}


def internal_key():
    if SECRETS.exists():
        try:
            k = json.loads(SECRETS.read_text(encoding="utf-8")).get("internal_api_key")
            if k:
                return k
        except Exception:
            pass
    return os.environ.get("INTERNAL_API_KEY", "")


def clean_value(start_cap, prior=None):
    prior = prior or {}
    return {
        "pnl": 0.0, "cash": start_cap, "total": start_cap,
        "day_pct": 0.0, "day_pnl": 0.0, "pnl_pct": 0.0,
        "pos_val": 0.0, "day_open": start_cap, "positions": [],
        "window_open": prior.get("window_open", False),
        "holding_cash": True,
        "trade_log": [],
    }


def clean_strategy():
    return {"day": TODAY, "week": TODAY, "month": TODAY, "picks": [], "decision": "HOLD",
            "rationale": "Full reset -- starting fresh.", "session_log": [],
            "projected_return": 0.0}


def reset_blob(state, start_cap, snap_date):
    """Zero every fund, delete all snapshots, reset leaderboards. In place."""
    funds = state.get("funds", {})
    for bot in BOTS:
        f = funds.get(bot)
        if not f:
            print(f"    WARNING: no '{bot}' fund -- skipping")
            continue
        old = (f.get("value") or {}).get("total")
        print(f"    {bot}: {old} -> {start_cap:,.0f}")
        f["value"] = clean_value(start_cap, f.get("value"))
        f["current_strategy"] = clean_strategy()
        f["inception"] = TODAY   # fresh inception -> engine's holdover guard deploys exactly sc
    state["starting_capital"] = start_cap
    n = len(state.get("snapshots", []))
    state["snapshots"] = [{"date": snap_date, **{b: start_cap for b in BOTS}}]  # last TRADING day, not a weekend/holiday
    print(f"    snapshots: deleted {n}, seeded 1 clean baseline row")
    lb = state.get("leaderboards", {})
    for period, rows in lb.items():
        for row in rows:
            if row.get("fund") in BOTS:
                for k in list(row.keys()):
                    if k == "fund": continue
                    row[k] = "C" if "grade" in k else 0.0
    return state


def main():
    key = internal_key()
    if not key:
        print("ERROR: no internal key"); sys.exit(1)
    headers = {"x-internal-key": key}
    if _TARGET and _TARGET not in PLATFORMS:
        print(f"ERROR: unknown --platform '{_TARGET}'. Valid: {list(PLATFORMS)}"); sys.exit(1)
    if not _TARGET and not _ALL:
        print("REFUSING to reset: pass --platform <name> for one site, or --all for every site.")
        print(f"  e.g. python {Path(__file__).name} --platform bitbot13")
        print(f"       python {Path(__file__).name} --all")
        sys.exit(1)
    targets = {_TARGET: PLATFORMS[_TARGET]} if _TARGET else PLATFORMS
    scope = _TARGET if _TARGET else "ALL 3 PLATFORMS"
    print("=" * 70)
    print(f"FULL RESET -- {scope} -- {TODAY}{'  [DRY RUN]' if DRY else ''}")
    print("=" * 70)

    for platform, (usize, disk_path) in targets.items():
        start_cap = float(usize * 1000)
        print(f"\n### {platform}  (universe {usize} -> ${start_cap:,.0f}) ###")

        # Use the live backend blob as the structural template (guaranteed clean shape).
        try:
            r = requests.get(f"{BACKEND}/public/tracker/state?platform={platform}", timeout=20)
            blob = r.json().get("data", {}) or {}
        except Exception as e:
            print(f"  ERROR fetching backend state: {e}"); continue
        if not blob.get("funds"):
            print("  ERROR: backend returned no funds -- skipping"); continue

        # LAYER 1: reset + push to backend cache
        print("  LAYER 1: backend cache")
        _cfg = _CR_CFG if platform == "bitbot13" else _EQ_CFG
        _snap_date = _last_trading_day(_cfg, _date.fromisoformat(TODAY)).isoformat()
        reset_blob(blob, start_cap, _snap_date)
        if not DRY:
            pr = requests.post(f"{BACKEND}/internal/tracker/push",
                               json={"platform": platform, "data_type": "state", "data": blob},
                               headers=headers, timeout=30)
            print(f"    push -> HTTP {pr.status_code}")

        # LAYER 2: member DB
        print("  LAYER 2: member DB")
        try:
            r = requests.get(f"{BACKEND}/internal/portfolios/active?platform={platform}",
                             headers=headers, timeout=20)
            body = r.json() if r.status_code == 200 else {}
            ports = body.get("portfolios", body if isinstance(body, list) else [])
            bot_ids = [p.get("bot_id") or p.get("id") for p in ports]
        except Exception as e:
            print(f"    WARNING listing portfolios: {e}"); bot_ids = []
        print(f"    {len(bot_ids)} active portfolio(s)")
        if not DRY:
            wr = requests.post(f"{BACKEND}/internal/portfolio-fund-snapshots/wipe",
                               json={"platform": platform}, headers=headers, timeout=30)
            print(f"    snapshots WIPE -> HTTP {wr.status_code} {wr.text[:120]}")
            for bid in bot_ids:
                results = [{
                    "bot_id": bid, "fund_name": fn, "positions": [],
                    "strategy": clean_strategy(), "total_value": start_cap,
                    "entry_cost": start_cap, "gain_loss": 0.0, "gain_loss_pct": 0.0,
                    "day_pnl": 0.0, "day_pct": 0.0, "window_open": False,
                    "holding_cash": True, "trade_log": [],
                } for fn in BOTS]
                ur = requests.post(f"{BACKEND}/internal/portfolio-bot-state/upsert",
                                   json={"results": results}, headers=headers, timeout=30)
                print(f"    portfolio {bid}: reset -> HTTP {ur.status_code}")
            requests.post(f"{BACKEND}/internal/portfolio-fund-snapshots/refresh",
                          json={"platform": platform}, headers=headers, timeout=30)

        # LAYER 3: disk state.json (CLEAN write -- clears any NUL corruption)
        if disk_path is not None:
            print(f"  LAYER 3: disk {disk_path.name}")
            if not DRY:
                disk_path.write_text(json.dumps({"data": blob}, indent=2), encoding="utf-8")
                # verify no NUL + parses
                raw = disk_path.read_text(encoding="utf-8")
                ok = ("\x00" not in raw)
                try: json.loads(raw); ok = ok and True
                except Exception: ok = False
                print(f"    wrote clean ({'OK' if ok else 'VERIFY FAILED'}, {len(raw)} bytes)")
        else:
            print("  LAYER 3: (aistocks backend-driven -- disk skipped)")

    print(f"\n{'DRY RUN COMPLETE -- nothing changed.' if DRY else 'FULL RESET COMPLETE.'}")


if __name__ == "__main__":
    main()
