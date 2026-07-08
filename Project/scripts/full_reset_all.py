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
from bot13_engine import is_trading_day as _is_trading_day, next_trading_day as _next_trading_day, EQUITY_CFG as _EQ_CFG, CRYPTO_CFG as _CR_CFG

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

# platform -> (universe size, disk state path). ALL THREE disks must be written:
# every engine (including aistocks) loads its DISK state.json FIRST and pushes it
# back to the backend at the end of each run -- skipping the aistocks disk write
# meant every aistocks reset was resurrected by the very next refresh (root-cause
# finding, 2026-07-06). There is no "backend-only" platform.
PLATFORMS = {
    "wallstbots": (55, ROOT / "Frontends" / "wallstbots.tech" / "data" / "state.json"),
    "aistocks":   (50, ROOT / "Frontends" / "aistocks.tech" / "data" / "state.json"),
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
    # Day 1 must not reference ANY prior-day data: drop the stale day_boundary block
    # (yesterday's price map) so the first post-reset run uses the feed's own closes.
    if state.pop("day_boundary", None) is not None:
        print("    day_boundary: stale prior-day price block removed")
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

        # Structural template resolution (2026-07-08 fix): the live backend blob is the
        # first choice, but after an empty-site incident the backend itself can have NO
        # funds -- which used to make the reset refuse to run (chicken-and-egg: the tool
        # that restores a broken state needed a healthy state to run). Fallback: the
        # platform's DISK state.json (a prior reset wrote a clean, complete blob there).
        blob = {}
        try:
            r = requests.get(f"{BACKEND}/public/tracker/state?platform={platform}", timeout=20)
            blob = r.json().get("data", {}) or {}
        except Exception as e:
            print(f"  WARNING fetching backend state: {e}")
        if not blob.get("funds"):
            print("  backend has no funds -- falling back to the disk state.json template")
            try:
                _draw = json.loads(disk_path.read_text(encoding="utf-8"))
                blob = _draw.get("data", _draw) or {}
            except Exception as e:
                print(f"  ERROR: disk template also unusable ({e})")
        if not blob.get("funds"):
            print("  ERROR: no usable template (backend AND disk have no funds) -- skipping. "
                  "Restore a clean state.json for this platform and re-run."); continue

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
        # ROOT-CAUSE FIX (2026-07-06): this layer used to write the PLATFORM's starting
        # capital (start_cap, e.g. $55,000) into EVERY member portfolio regardless of the
        # member's own size -- so every daily reset RE-CORRUPTED every member portfolio
        # ($55,000 on a $20,000 portfolio = the +175% "gains" that reappeared each morning).
        # A member portfolio's ONLY starting capital is its own N holdings x $1,000, and a
        # reset writes the engine's PENDING shape (strategy.pending + starts_on) so the
        # engines -- which honor PENDING -- take first real entries at the NEXT session.
        print("  LAYER 2: member DB")
        try:
            r = requests.get(f"{BACKEND}/internal/portfolios/active?platform={platform}",
                             headers=headers, timeout=20)
            body = r.json() if r.status_code == 200 else {}
            ports = body.get("portfolios", body if isinstance(body, list) else [])
        except Exception as e:
            print(f"    WARNING listing portfolios: {e}"); ports = []
        print(f"    {len(ports)} active portfolio(s)")
        _starts = _next_trading_day(_cfg, _date.fromisoformat(TODAY)).isoformat()
        if not DRY:
            wr = requests.post(f"{BACKEND}/internal/portfolio-fund-snapshots/wipe",
                               json={"platform": platform}, headers=headers, timeout=30)
            print(f"    snapshots WIPE -> HTTP {wr.status_code} {wr.text[:120]}")
            for p in ports:
                bid = p.get("bot_id") or p.get("id")
                if not bid:
                    continue
                n_hold   = len(p.get("holdings") or [])
                own_cost = round(n_hold * 1000.0, 2)          # the member's OWN capital
                if own_cost <= 0:
                    print(f"    portfolio {bid}: 0 holdings -- skipped"); continue
                results = [{
                    "bot_id": bid, "fund_name": fn, "positions": [], "trade_log": [],
                    "strategy": {"decision": "PENDING", "pending": True, "starts_on": _starts,
                                 "rationale": f"Full reset -- starting fresh at the member's own "
                                              f"${own_cost:,.0f} ({n_hold} x $1,000). Trading begins {_starts}.",
                                 "_day_open": own_cost, "_asof": TODAY},
                    "total_value": own_cost, "entry_cost": own_cost,
                    "gain_loss": 0.0, "gain_loss_pct": 0.0,
                    "day_pnl": 0.0, "day_pct": 0.0, "window_open": False,
                    "holding_cash": True, "traded_today": False, "closed_out": False,
                } for fn in BOTS]
                ur = requests.post(f"{BACKEND}/internal/portfolio-bot-state/upsert",
                                   json={"results": results}, headers=headers, timeout=30)
                print(f"    portfolio {bid}: reset at own ${own_cost:,.0f} ({n_hold} holdings) -> HTTP {ur.status_code}")
            requests.post(f"{BACKEND}/internal/portfolio-fund-snapshots/refresh",
                          json={"platform": platform}, headers=headers, timeout=30)
        else:
            for p in ports:
                n_hold = len(p.get("holdings") or [])
                print(f"    would reset portfolio {(p.get('bot_id') or '')[:8]} at own "
                      f"${n_hold * 1000:,.0f} ({n_hold} holdings), trading begins {_starts}")

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
            # unreachable: every platform now has a disk path (all engines read disk first)
            print("  LAYER 3: ERROR -- no disk path configured; every platform must have one")

    print(f"\n{'DRY RUN COMPLETE -- nothing changed.' if DRY else 'FULL RESET COMPLETE.'}")


if __name__ == "__main__":
    main()
