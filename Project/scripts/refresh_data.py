#!/usr/bin/env python3
"""
refresh_data.py
Reads fund state from the AIQC Tracker's local JSON files,
pulls LIVE prices from yfinance for each held position,
and writes public-safe JSON into public_html/data/.

Output:
  - state.json       : fund values + leaderboards + snapshots + per-position prices
  - signals.json     : daily Buy/Sell/Hold recommendations (passthrough)
  - reports.json     : weekly Sunday reports (passthrough)
"""
import json
import sys
import datetime as dt
from pathlib import Path

try:
    import requests as _requests
except ImportError:
    _requests = None

ROOT = Path(__file__).resolve().parents[1]
SECRETS_PATH = ROOT / "config" / "secrets.json"
DATA_OUT = ROOT / "public_html" / "data"

FUND_ORDER = ["bot13", "oracle", "wizard", "equalizer", "titan"]

FUND_META = {
    "bot13":     {"name":"BOT13",    "color":"#ec4899","icon":"13",
                  "tagline":"Daily intraday bot. Buys at open, sells before close. Skips the day if no edge."},
    "oracle":    {"name":"ORACLE",   "color":"#a855f7","icon":"OR",
                  "tagline":"Weekly bot. Trades every Monday. All-in on the week's best bets."},
    "wizard":    {"name":"WIZARD",   "color":"#10b981","icon":"WZ",
                  "tagline":"Monthly hold bot. Buys the 1st trading day, sells the last. Slow and patient."},
    "equalizer": {"name":"EQUALIZER","color":"#00d4ff","icon":"EQ",
                  "tagline":"Equal weight. No favorites. $1,000 in every stock."},
    "titan":     {"name":"TITAN",    "color":"#ff8c00","icon":"TT",
                  "tagline":"Half on the heavyweights. Half on the rest. Concentration meets coverage."},
}


def load_secrets():
    if not SECRETS_PATH.exists():
        print(f"Missing {SECRETS_PATH}.")
        sys.exit(1)
    return json.loads(SECRETS_PATH.read_text())


def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default if default is not None else {}
    try:
        return json.loads(p.read_text())
    except Exception as e:
        print(f"  [warn] could not parse {p.name}: {e}")
        return default if default is not None else {}


def get_live_prices(symbols, quotes_cache):
    """
    Pull live prices for a set of symbols.
    Tries yfinance first, falls back to the tracker's quotes_cache.json.
    """
    prices = {}
    prev_closes = {}

    # First try yfinance (works when running on the GCP VM)
    try:
        import yfinance as yf
        for sym in symbols:
            try:
                t = yf.Ticker(sym)
                fi = getattr(t, "fast_info", None) or {}
                p = float(fi.get("last_price", 0) or 0)
                pc = float(fi.get("previous_close", 0) or 0)
                if p > 0:
                    prices[sym] = p
                    prev_closes[sym] = pc or p
            except Exception as e:
                print(f"  [yfinance] {sym}: {e}")
    except ImportError:
        print("  [info] yfinance not installed — falling back to quotes_cache.json")

    # Fall back to whatever the tracker last cached
    cached = (quotes_cache or {}).get("quotes", {})
    for sym in symbols:
        if sym not in prices:
            cq = cached.get(sym, {})
            if cq.get("price"):
                prices[sym] = float(cq["price"])
                prev_closes[sym] = float(cq.get("prev_close") or cq["price"])
    return prices, prev_closes


def enrich_position(pos, prices, prev_closes):
    """Compute live value, P&L, day P&L for a position."""
    sym = pos.get("symbol")
    shares = float(pos.get("shares") or 0)
    entry = float(pos.get("entry_price") or pos.get("entry") or 0)
    cost_basis = float(pos.get("cost_basis") or (shares * entry))
    price = prices.get(sym, entry)
    prev = prev_closes.get(sym, price)
    value = shares * price
    pnl = value - cost_basis
    pnl_pct = (price/entry - 1) * 100 if entry > 0 else 0
    day_pnl = shares * (price - prev)
    day_pct = (price/prev - 1) * 100 if prev > 0 else 0
    return {
        "symbol": sym,
        "shares": round(shares, 4),
        "entry_price": round(entry, 2),
        "entry": round(entry, 2),
        "cost_basis": round(cost_basis, 2),
        "price": round(price, 2),
        "value": round(value, 2),
        "pnl": round(pnl, 2),
        "pnl_pct": round(pnl_pct, 2),
        "day_pnl": round(day_pnl, 2),
        "day_pct": round(day_pct, 2),
    }


def main():
    secrets = load_secrets()
    tracker_dir = Path(secrets.get("tracker_data_dir", ""))
    if not tracker_dir.exists():
        print(f"Tracker data dir not found: {tracker_dir}")
        sys.exit(1)

    snapshots = load_json(tracker_dir / "snapshots.json", default=[])
    quotes_cache = load_json(tracker_dir / "quotes_cache.json", default={})

    # Collect all unique symbols held across all funds
    all_symbols = set()
    for fid in FUND_ORDER:
        f = load_json(tracker_dir / f"fund_{fid}.json", default=None) or {}
        for pos in f.get("positions", []):
            sym = pos.get("symbol")
            if sym:
                all_symbols.add(sym)
    print(f"[data] fetching prices for {len(all_symbols)} held symbols...")

    prices, prev_closes = get_live_prices(sorted(all_symbols), quotes_cache)
    print(f"[data] got {len(prices)} prices")

    # Build per-fund state
    funds_out = {}
    for fid in FUND_ORDER:
        fund = load_json(tracker_dir / f"fund_{fid}.json", default=None)
        if not fund:
            print(f"  [skip] fund_{fid}.json not found")
            continue
        sc = fund.get("starting_capital", 43000)

        # Enrich positions with live prices
        enriched = [enrich_position(p, prices, prev_closes) for p in fund.get("positions", [])]
        cash = float(fund.get("cash") or 0)
        pos_val = sum(p["value"] for p in enriched)
        total = pos_val + cash
        pnl = total - sc
        pnl_pct = (total/sc - 1) * 100 if sc else 0

        # Day P&L: from snapshots (most accurate at the fund level)
        prev_snap = snapshots[-2].get(fid) if len(snapshots) >= 2 else None
        day_pnl = (total - prev_snap) if prev_snap else sum(p["day_pnl"] for p in enriched)
        day_pct = (total/prev_snap - 1) * 100 if prev_snap else 0

        funds_out[fid] = {
            "id": fid,
            **FUND_META[fid],
            "inception":        fund.get("inception"),
            "starting_capital": sc,
            "value": {
                "total":     round(total, 2),
                "cash":      round(cash, 2),
                "pos_val":   round(pos_val, 2),
                "pnl":       round(pnl, 2),
                "pnl_pct":   round(pnl_pct, 2),
                "day_pnl":   round(day_pnl, 2),
                "day_pct":   round(day_pct, 2),
                "positions": enriched,
            },
            "current_strategy": fund.get("current_strategy"),
            "top10":            fund.get("top10"),
            "per_top_dollars":  fund.get("per_top_dollars"),
            "per_rest_dollars": fund.get("per_rest_dollars"),
        }

    # Update today's snapshot to reflect live prices
    today_iso = dt.date.today().isoformat()
    today_snap = {"date": today_iso}
    for fid in FUND_ORDER:
        if fid in funds_out:
            today_snap[fid] = funds_out[fid]["value"]["total"]
    snapshots = [s for s in snapshots if s.get("date") != today_iso]
    snapshots.append(today_snap)
    snapshots.sort(key=lambda s: s.get("date", ""))

    # Build leaderboards
    today = dt.date.today()
    week_start = today - dt.timedelta(days=today.weekday())
    cands = [s for s in snapshots if s.get("date", "") <= week_start.isoformat()]
    start_snap = cands[-1] if cands else None

    wk, all_lb = [], []
    for fid in FUND_ORDER:
        if fid not in funds_out:
            continue
        v = funds_out[fid]["value"]
        sc = funds_out[fid]["starting_capital"]
        sv = (start_snap or {}).get(fid, sc)
        week_pnl = v["total"] - sv
        week_pct = (v["total"]/sv - 1) * 100 if sv else 0
        wk.append({"fund": fid, "week_pnl": round(week_pnl, 2),
                   "week_pct": round(week_pct, 2), "week_grade": grade(week_pct)})
        all_lb.append({"fund": fid, "all_pnl": v["pnl"], "all_pct": v["pnl_pct"],
                       "overall_grade": grade_overall(v["pnl_pct"], funds_out[fid]["inception"], today)})
    wk.sort(key=lambda r: -r["week_pct"])
    all_lb.sort(key=lambda r: -r["all_pct"])

    state = {
        "starting_capital": 43000,
        "last_refresh":     dt.datetime.now().isoformat(timespec="seconds"),
        "snapshots":        snapshots[-30:],
        "funds":            funds_out,
        "leaderboards":     {"week": wk, "all": all_lb},
    }
    DATA_OUT.mkdir(parents=True, exist_ok=True)
    (DATA_OUT / "state.json").write_text(json.dumps(state, indent=2))
    print(f"[data] wrote state.json ({len(funds_out)} funds, {len(snapshots)} snapshots)")

    recs = load_json(tracker_dir / "recommendations.json", default=None)
    if recs:
        (DATA_OUT / "signals.json").write_text(json.dumps(recs, indent=2))
        print(f"[data] wrote signals.json ({len(recs.get('recommendations', []))} stocks)")

    reports = load_json(tracker_dir / "reports.json", default=[])
    reports_payload = {"reports": reports}
    (DATA_OUT / "reports.json").write_text(json.dumps(reports_payload, indent=2))
    print(f"[data] wrote reports.json ({len(reports)} reports)")

    # ── Push to Supabase via Cloud Run API (dual-write; HostGator already done above) ──
    print("[push] pushing to Supabase...")
    push_to_api(secrets, "state",   state)
    if recs:
        push_to_api(secrets, "signals", recs)
    push_to_api(secrets, "reports", reports_payload)


def grade(pct):
    if pct >= 5:   return "A+"
    if pct >= 3:   return "A"
    if pct >= 1.5: return "B"
    if pct >= 0:   return "C"
    if pct >= -2:  return "D"
    return "F"


def grade_overall(pct, inception_iso, today):
    try:
        inception = dt.date.fromisoformat(inception_iso)
        days = max((today - inception).days, 1)
        weeks = max(days / 7, 1)
        return grade(pct / weeks)
    except Exception:
        return grade(pct)


def push_to_api(secrets, data_type, payload):
    """
    Push a JSON payload to the Cloud Run API so the frontend can read it
    from Supabase instead of HostGator.  Fails silently — HostGator write
    already happened, so this is additive only.
    """
    if _requests is None:
        print(f"  [push] requests not installed — skipping API push for {data_type}")
        return

    api_url = secrets.get("api_url", "")
    api_key  = secrets.get("internal_api_key", "")
    platform = secrets.get("platform", "lvl13")

    if not api_url or not api_key:
        print(f"  [push] api_url/internal_api_key not in secrets.json — skipping push for {data_type}")
        return

    endpoint = f"{api_url.rstrip('/')}/internal/tracker/push"
    try:
        r = _requests.post(
            endpoint,
            json={"data_type": data_type, "platform": platform, "data": payload},
            headers={"X-Internal-Key": api_key},
            timeout=15,
        )
        if r.status_code == 200:
            print(f"  [push] ✓ {data_type} → Supabase (pushed_at={r.json().get('pushed_at','')})")
        else:
            print(f"  [push] ✗ {data_type} HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"  [push] ✗ {data_type} error: {e}")


if __name__ == "__main__":
    main()
