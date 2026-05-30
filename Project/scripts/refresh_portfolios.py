#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
refresh_portfolios.py
=====================
Runs all 5 bot strategy engines against every active member portfolio
and pushes results to /internal/portfolio-bot-state/upsert.

Called by each platform's refresh script after pushing global state.
Reuses prices + hist_data already fetched — no extra API calls needed
when called inline from refresh_lvl13.py / refresh_wallstbots.py / refresh_bitbot13.py.

Can also be run standalone:
    python Project/scripts/refresh_portfolios.py --platform lvl13

Scales to thousands of users: all bot engines run in-process against
each portfolio's custom universe using prices already in memory.
"""

import datetime as dt
import json
import os
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bot13_engine import (
    run_bot13_equity, run_bot13_crypto,
    EQUITY_CFG, CRYPTO_CFG,
    et_now, window_open as _window_open,
    session_phase as _session_phase,
    check_drawdown, enrich_position,
)

try:
    import requests as _requests
except ImportError:
    _requests = None

try:
    import yfinance as yf
except ImportError:
    yf = None

ROOT    = Path(__file__).resolve().parents[2]
SECRETS = ROOT / "Project" / "config" / "secrets.json"

BACKEND_URL = "https://wallstbots-backend-868128114349.us-east1.run.app"

# ── Platform configs ──────────────────────────────────────────────────────────

PLATFORM_CFG = {
    "lvl13":      {"market": "equity", "cfg": EQUITY_CFG},
    "wallstbots": {"market": "equity", "cfg": EQUITY_CFG},
    "bitbot13":   {"market": "crypto", "cfg": CRYPTO_CFG},
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_secrets():
    if SECRETS.exists():
        return json.loads(SECRETS.read_text())
    return {}


def compute_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    avg_g = sum(gains[-period:]) / period
    avg_l = sum(losses[-period:]) / period
    if avg_l == 0:
        return 100.0
    return round(100 - (100 / (1 + avg_g / avg_l)), 1)


def get_all_portfolios(secrets, platform):
    """Fetch all active portfolios with holdings from the backend."""
    if _requests is None:
        return []
    api_url = secrets.get("api_url", BACKEND_URL)
    key     = secrets.get("internal_api_key") or os.environ.get("INTERNAL_API_KEY", "")
    try:
        r = _requests.get(
            f"{api_url}/internal/portfolios/active",
            params={"platform": platform},
            headers={"x-internal-key": key},
            timeout=20,
        )
        if r.status_code == 200:
            data = r.json()
            portfolios = data.get("portfolios", [])
            print(f"  [portfolios] {len(portfolios)} active portfolios for {platform}")
            return portfolios
        else:
            print(f"  [portfolios] HTTP {r.status_code}: {r.text[:120]}")
            return []
    except Exception as e:
        print(f"  [portfolios] error: {e}")
        return []


def push_bot_states(secrets, results):
    """Push per-portfolio bot state to backend."""
    if _requests is None or not results:
        return
    api_url = secrets.get("api_url", BACKEND_URL)
    key     = secrets.get("internal_api_key") or os.environ.get("INTERNAL_API_KEY", "")
    try:
        r = _requests.post(
            f"{api_url}/internal/portfolio-bot-state/upsert",
            json={"results": results},
            headers={"x-internal-key": key},
            timeout=30,
        )
        if r.status_code == 200:
            res = r.json()
            print(f"  [bot-state] OK — {res.get('upserted', 0)} states upserted")
        else:
            print(f"  [bot-state] HTTP {r.status_code}: {r.text[:120]}")
    except Exception as e:
        print(f"  [bot-state] error: {e}")


def get_prices_for_symbols(symbols):
    """Fetch live prices for a set of symbols via yfinance."""
    if yf is None or not symbols:
        return {}, {}
    import pandas as pd
    prices, prev_closes = {}, {}
    try:
        raw = yf.download(list(symbols), period="2d", auto_adjust=True, progress=False)
        if raw.empty:
            return {}, {}
        for sym in symbols:
            try:
                if isinstance(raw.columns, pd.MultiIndex):
                    closes = raw["Close"][sym].dropna()
                else:
                    closes = raw["Close"].dropna()
                if len(closes) >= 1:
                    p  = float(closes.iloc[-1])
                    pc = float(closes.iloc[-2]) if len(closes) >= 2 else p
                    if p > 0:
                        prices[sym]      = round(p, 4)
                        prev_closes[sym] = round(pc, 4)
            except Exception:
                pass
    except Exception as e:
        print(f"  [prices] error: {e}")
    return prices, prev_closes


def get_hist_for_symbols(symbols):
    """Fetch 90-day history for a set of symbols."""
    if yf is None or not symbols:
        return {}
    import pandas as pd
    hist = {}
    try:
        raw = yf.download(list(symbols), period="90d", auto_adjust=True, progress=False)
        if raw.empty:
            return {}
        for sym in symbols:
            try:
                if isinstance(raw.columns, pd.MultiIndex):
                    closes = [float(x) for x in raw["Close"][sym].dropna().tolist()]
                else:
                    closes = [float(x) for x in raw["Close"].dropna().tolist()]
                if len(closes) >= 20:
                    hist[sym] = {"closes": closes, "volumes": []}
            except Exception:
                pass
    except Exception as e:
        print(f"  [hist] error: {e}")
    return hist


# ── Bot decision functions (universe-parameterized) ───────────────────────────

def run_oracle_for_universe(universe, prices, prev_closes, hist_data, starting_capital, week_str):
    """Oracle decision against a custom universe."""
    scored = []
    for sym in universe:
        p_now = prices.get(sym, 0)
        if p_now <= 0:
            continue
        info   = hist_data.get(sym, {})
        closes = info.get("closes", [])
        vols   = info.get("volumes", [])
        if len(closes) < 21:
            continue
        p5  = closes[-5]  if len(closes) >= 5  else closes[0]
        p20 = closes[-20] if len(closes) >= 20 else closes[0]
        ret5  = (p_now / p5  - 1) * 100 if p5  > 0 else 0
        ret20 = (p_now / p20 - 1) * 100 if p20 > 0 else 0
        if ret20 < 0:
            continue
        rsi = compute_rsi(closes[-15:] + [p_now])
        if rsi > 75:
            rsi_score = -0.5 * (rsi - 75) / 25
        else:
            rsi_score = (rsi - 50) / 25
        vol_r = 1.0
        if len(vols) >= 20:
            avg5  = sum(vols[-5:]) / 5
            avg20 = sum(vols[-20:]) / 20
            vol_r = avg5 / avg20 if avg20 > 0 else 1.0
        composite = ret5 * 0.40 + ret20 * 0.30 + rsi_score * 10.0 * 0.20 + (vol_r - 1) * 10.0 * 0.10
        scored.append((sym, composite, ret5, ret20, rsi, vol_r))

    if not scored:
        return "CASH", [], [], "No qualifying picks in your universe.", 0.0

    scored.sort(key=lambda x: -x[1])
    picks_raw = scored[:min(5, len(scored))]
    total_score = sum(s for _, s, *_ in picks_raw)
    raw_w = [max(0.12, min(0.35, s / total_score)) if total_score > 0 else 0.2 for _, s, *_ in picks_raw]
    total_rw = sum(raw_w)
    weights = [w / total_rw for w in raw_w]
    oracle_proj = round(sum(w * ret5 for (_, _, ret5, *_), w in zip(picks_raw, weights)), 2)

    positions, picks = [], []
    for i, (sym, score, ret5, ret20, rsi, vol_r) in enumerate(picks_raw):
        w      = weights[i]
        alloc  = starting_capital * w
        price  = prices.get(sym, 0)
        shares = alloc / price if price > 0 else 0
        positions.append({"symbol": sym, "shares": round(shares, 6),
                          "entry_price": round(price, 4), "cost_basis": round(alloc, 2)})
        picks.append({"symbol": sym, "weight": round(w, 4), "score": round(score, 1),
                      "rationale": f"{sym}: 5d {ret5:+.1f}% | 20d {ret20:+.1f}% | RSI {rsi:.0f}. Allocated {w*100:.0f}%.",
                      "indicators": {"mom_5d": round(ret5, 2), "mom_20d": round(ret20, 2), "rsi_14": round(rsi, 1)}})

    rationale = (f"Projected week return: +{oracle_proj:.2f}%. "
                 f"Top {len(picks)} names from your {len(universe)}-stock universe by momentum.")
    return "TRADE", positions, picks, rationale, oracle_proj


def run_wizard_for_universe(universe, prices, prev_closes, hist_data, starting_capital, month_str):
    """Wizard decision against a custom universe."""
    scored = []
    for sym in universe:
        p_now  = prices.get(sym, 0)
        if p_now <= 0:
            continue
        info   = hist_data.get(sym, {})
        closes = info.get("closes", [])
        if len(closes) < 21:
            continue
        p20  = closes[-20] if len(closes) >= 20 else closes[0]
        p60  = closes[-60] if len(closes) >= 60 else closes[0]
        ma50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else p_now
        ret20 = (p_now / p20 - 1) * 100 if p20 > 0 else 0
        ret60 = (p_now / p60 - 1) * 100 if p60 > 0 else 0
        if ret60 < 0:
            continue
        daily_rets = [(closes[i] / closes[i-1] - 1) for i in range(max(1, len(closes)-60), len(closes))]
        sharpe = 0.0
        if len(daily_rets) >= 10:
            std = statistics.stdev(daily_rets) * 100
            mean = (sum(daily_rets) / len(daily_rets)) * 100
            sharpe = mean / std if std > 0 else 0
        dist_ma50 = (p_now / ma50 - 1) * 100 if ma50 > 0 else 0
        score = ret20 * 0.35 + ret60 * 0.35 + sharpe * 20 * 0.20 + dist_ma50 * 0.10
        scored.append((sym, score, ret20, ret60, sharpe, dist_ma50))

    if not scored:
        return "CASH", [], [], "No qualifying picks in your universe.", 0.0

    scored.sort(key=lambda x: -x[1])
    picks_raw = scored[:min(8, len(scored))]
    n = len(picks_raw)
    q1_cut = max(1, round(n * 0.25))
    q3_cut = max(q1_cut + 1, round(n * 0.75))
    raw_w = [3.0 if i < q1_cut else (1.8 if i < q3_cut else 1.0) for i in range(n)]
    total_rw = sum(raw_w)
    weights = [w / total_rw for w in raw_w]
    wizard_proj = round(sum(w * ret20 for (_, _, ret20, *_), w in zip(picks_raw, weights)), 2)

    positions, picks = [], []
    for i, (sym, score, ret20, ret60, sharpe, dist) in enumerate(picks_raw):
        w      = weights[i]
        alloc  = starting_capital * w
        price  = prices.get(sym, 0)
        shares = alloc / price if price > 0 else 0
        positions.append({"symbol": sym, "shares": round(shares, 6),
                          "entry_price": round(price, 4), "cost_basis": round(alloc, 2)})
        picks.append({"symbol": sym, "weight": round(w, 4), "score": round(score, 1),
                      "rationale": f"{sym}: 20d {ret20:+.1f}% | 60d {ret60:+.1f}% | Sharpe {sharpe:.2f}. Allocated {w*100:.0f}%.",
                      "indicators": {"mom_20d": round(ret20, 2), "mom_60d": round(ret60, 2)}})

    rationale = (f"Projected month return: +{wizard_proj:.2f}%. "
                 f"Top {len(picks)} quality names from your {len(universe)}-stock universe.")
    return "TRADE", positions, picks, rationale, wizard_proj


def run_equalizer_for_universe(universe, prices, prev_closes, starting_capital):
    """Equalizer: equal $1,000 per stock."""
    positions = []
    for sym in universe:
        price = prices.get(sym, 0)
        prev  = prev_closes.get(sym, price)
        alloc = starting_capital / len(universe) if universe else 0
        shares = alloc / price if price > 0 else 0
        pnl    = shares * (price - prev) if price > 0 else 0
        positions.append({
            "symbol":        sym,
            "shares":        round(shares, 6),
            "entry_price":   round(price, 4),
            "price":         round(price, 4),
            "cost_basis":    round(alloc, 2),
            "value":         round(shares * price, 2),
            "pnl":           round(pnl, 2),
            "pnl_pct":       0.0,
            "day_pnl":       round(pnl, 2),
            "day_pct":       round((price / prev - 1) * 100 if prev > 0 else 0, 2),
        })
    return "TRADE", positions


def run_titan_for_universe(universe, prices, prev_closes, starting_capital):
    """Titan: top 20% get 2x weight, rest get 1x."""
    n = len(universe)
    if n == 0:
        return "CASH", []
    top_n = max(1, round(n * 0.20))
    # Simple proxy: sort by price desc as rough market-cap proxy
    sorted_u = sorted(universe, key=lambda s: prices.get(s, 0), reverse=True)
    raw_w = [2.0 if i < top_n else 1.0 for i in range(n)]
    total_w = sum(raw_w)
    weights = {sym: raw_w[i] / total_w for i, sym in enumerate(sorted_u)}

    positions = []
    for sym in universe:
        w      = weights.get(sym, 1.0 / n)
        alloc  = starting_capital * w
        price  = prices.get(sym, 0)
        prev   = prev_closes.get(sym, price)
        shares = alloc / price if price > 0 else 0
        pnl    = shares * (price - prev) if price > 0 else 0
        positions.append({
            "symbol":      sym,
            "shares":      round(shares, 6),
            "entry_price": round(price, 4),
            "price":       round(price, 4),
            "cost_basis":  round(alloc, 2),
            "value":       round(shares * price, 2),
            "pnl":         round(pnl, 2),
            "pnl_pct":     0.0,
            "day_pnl":     round(pnl, 2),
            "day_pct":     round((price / prev - 1) * 100 if prev > 0 else 0, 2),
        })
    return "TRADE", positions


# ── Main simulation loop ──────────────────────────────────────────────────────

def run_portfolio_simulations(platform, portfolios, prices, prev_closes, hist_data):
    """
    Run all 5 bot engines against each portfolio's custom universe.
    Returns list of state dicts ready to push to /internal/portfolio-bot-state/upsert.
    """
    today      = dt.date.today()
    today_iso  = today.isoformat()
    week_str   = str(today.isocalendar()[0:2])
    month_str  = today.strftime("%Y-%m")
    is_equity  = PLATFORM_CFG.get(platform, {}).get("market") == "equity"
    cfg        = PLATFORM_CFG.get(platform, {}).get("cfg", EQUITY_CFG)
    win_open   = _window_open(cfg)

    results = []

    for portfolio in portfolios:
        bot_id   = portfolio["bot_id"]
        holdings = portfolio.get("holdings", [])
        if not holdings:
            continue

        universe = [h["symbol"].upper() for h in holdings if h.get("symbol")]
        if not universe:
            continue

        starting_capital = len(universe) * 1000.0

        # Compute total portfolio value and day P&L across all positions
        total_value = 0.0
        day_pnl_total = 0.0
        for sym in universe:
            price = prices.get(sym, 0)
            prev  = prev_closes.get(sym, price)
            if price > 0:
                total_value   += price / (prev if prev > 0 else price) * 1000.0
            else:
                total_value   += 1000.0
            day_pnl_total += (price - prev) * (1000.0 / prev if prev > 0 else 0)

        gain_loss     = round(total_value - starting_capital, 2)
        gain_loss_pct = round(gain_loss / starting_capital * 100, 4) if starting_capital > 0 else 0
        day_pct       = round(day_pnl_total / starting_capital * 100, 4) if starting_capital > 0 else 0

        # ── BOT13 ──
        if is_equity:
            b13_dec, b13_pos, b13_picks, b13_rat, b13_log, b13_proj = run_bot13_equity(
                cfg, universe, prices, prev_closes, hist_data, starting_capital, today_iso
            )
        else:
            b13_dec, b13_pos, b13_picks, b13_rat, b13_log, b13_proj = run_bot13_crypto(
                cfg, universe, prices, prev_closes, hist_data, starting_capital, today_iso
            )
        results.append({
            "bot_id": bot_id, "fund_name": "bot13",
            "positions": b13_pos,
            "strategy": {"decision": b13_dec, "picks": b13_picks, "rationale": b13_rat,
                         "projected_return": b13_proj, "day": today_iso},
            "total_value": round(total_value, 2), "entry_cost": round(starting_capital, 2),
            "gain_loss": gain_loss, "gain_loss_pct": gain_loss_pct,
            "day_pnl": round(day_pnl_total, 2), "day_pct": day_pct,
            "window_open": win_open, "holding_cash": b13_dec in ("CASH", "HOLD"),
        })

        # ── ORACLE ──
        oracle_dec, oracle_pos, oracle_picks, oracle_rat, oracle_proj = run_oracle_for_universe(
            universe, prices, prev_closes, hist_data, starting_capital, week_str
        )
        results.append({
            "bot_id": bot_id, "fund_name": "oracle",
            "positions": oracle_pos,
            "strategy": {"decision": oracle_dec, "picks": oracle_picks, "rationale": oracle_rat,
                         "projected_return": oracle_proj, "week": week_str},
            "total_value": round(total_value, 2), "entry_cost": round(starting_capital, 2),
            "gain_loss": gain_loss, "gain_loss_pct": gain_loss_pct,
            "day_pnl": round(day_pnl_total, 2), "day_pct": day_pct,
            "window_open": win_open, "holding_cash": oracle_dec in ("CASH", "HOLD"),
        })

        # ── WIZARD ──
        wizard_dec, wizard_pos, wizard_picks, wizard_rat, wizard_proj = run_wizard_for_universe(
            universe, prices, prev_closes, hist_data, starting_capital, month_str
        )
        results.append({
            "bot_id": bot_id, "fund_name": "wizard",
            "positions": wizard_pos,
            "strategy": {"decision": wizard_dec, "picks": wizard_picks, "rationale": wizard_rat,
                         "projected_return": wizard_proj, "month": month_str},
            "total_value": round(total_value, 2), "entry_cost": round(starting_capital, 2),
            "gain_loss": gain_loss, "gain_loss_pct": gain_loss_pct,
            "day_pnl": round(day_pnl_total, 2), "day_pct": day_pct,
            "window_open": win_open, "holding_cash": wizard_dec in ("CASH", "HOLD"),
        })

        # ── EQUALIZER ──
        eq_dec, eq_pos = run_equalizer_for_universe(universe, prices, prev_closes, starting_capital)
        results.append({
            "bot_id": bot_id, "fund_name": "equalizer",
            "positions": eq_pos, "strategy": {"decision": eq_dec},
            "total_value": round(total_value, 2), "entry_cost": round(starting_capital, 2),
            "gain_loss": gain_loss, "gain_loss_pct": gain_loss_pct,
            "day_pnl": round(day_pnl_total, 2), "day_pct": day_pct,
            "window_open": win_open, "holding_cash": False,
        })

        # ── TITAN ──
        tt_dec, tt_pos = run_titan_for_universe(universe, prices, prev_closes, starting_capital)
        results.append({
            "bot_id": bot_id, "fund_name": "titan",
            "positions": tt_pos, "strategy": {"decision": tt_dec},
            "total_value": round(total_value, 2), "entry_cost": round(starting_capital, 2),
            "gain_loss": gain_loss, "gain_loss_pct": gain_loss_pct,
            "day_pnl": round(day_pnl_total, 2), "day_pct": day_pct,
            "window_open": win_open, "holding_cash": False,
        })

    print(f"  [simulation] {len(portfolios)} portfolios × 5 bots = {len(results)} states computed")
    return results


def run(platform, prices=None, prev_closes=None, hist_data=None, secrets=None):
    """
    Main entry point. Called inline from refresh scripts (prices already fetched)
    or standalone (will fetch prices itself).
    """
    if secrets is None:
        secrets = load_secrets()

    print(f"\n[portfolios] running simulations for platform={platform}")

    # Fetch portfolios
    portfolios = get_all_portfolios(secrets, platform)
    if not portfolios:
        print(f"  [portfolios] no active portfolios — skipping")
        return

    # Collect all unique symbols across all portfolios
    all_symbols = set()
    for p in portfolios:
        for h in p.get("holdings", []):
            sym = (h.get("symbol") or "").upper()
            if sym:
                all_symbols.add(sym)

    # Fetch prices if not provided (standalone mode)
    if prices is None or not prices:
        print(f"  [portfolios] fetching prices for {len(all_symbols)} unique symbols...")
        prices, prev_closes = get_prices_for_symbols(all_symbols)
        hist_data = get_hist_for_symbols(all_symbols)
    else:
        # Inline mode: supplement with any missing symbols
        missing = all_symbols - set(prices.keys())
        if missing:
            print(f"  [portfolios] fetching {len(missing)} additional symbols not in global state...")
            extra_p, extra_pc = get_prices_for_symbols(missing)
            extra_h = get_hist_for_symbols(missing)
            prices      = {**prices, **extra_p}
            prev_closes = {**prev_closes, **extra_pc}
            hist_data   = {**hist_data, **extra_h}

    # Run simulations
    results = run_portfolio_simulations(platform, portfolios, prices, prev_closes, hist_data or {})

    # Push to backend
    push_bot_states(secrets, results)


# ── Standalone ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", default="lvl13",
                        choices=["lvl13", "wallstbots", "bitbot13"])
    args = parser.parse_args()
    run(args.platform)
