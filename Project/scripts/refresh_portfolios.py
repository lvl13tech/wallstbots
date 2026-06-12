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

Bot compounding rules (enforced here, permanent):
  BOT13     — daily. Carries yesterday's closing total_value as next day's capital.
              Intraday refreshes mark-to-market but do NOT update carryover capital
              until the session closes (after 4 PM ET for equity, 9 PM ET for crypto).
  ORACLE    — weekly. Rebalances ONLY on Monday. All other days: mark existing
              positions to market, carry balance forward unchanged.
  WIZARD    — monthly. Rebalances ONLY on the 1st of the month. All other days:
              mark existing positions to market, carry balance forward unchanged.
  EQUALIZER — buy once at inception, never sell. Entry prices stored permanently
              on first run. Value drifts with market forever.
  TITAN     — buy once at inception, never sell. Same as Equalizer.
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


def is_session_closed(platform):
    """
    Return True if the trading session for today is definitively over.
    Used to decide whether to lock BOT13's closing balance as next-day capital.
    Equity closes at 4 PM ET. Crypto closes at 9 PM ET.
    """
    now = et_now()
    if platform == "bitbot13":
        # Crypto session closes at 9 PM ET
        return now.hour >= 21
    else:
        # Equity session closes at 4 PM ET
        return now.hour >= 16


def is_oracle_rebalance_day():
    """Oracle rebalances on Monday only."""
    return et_now().date().weekday() == 0  # 0 = Monday — uses ET not UTC


def is_wizard_rebalance_day():
    """Wizard rebalances on the 1st of the month only."""
    return et_now().date().day == 1  # uses ET not UTC


def mark_positions_to_market(positions, prices, prev_closes):
    """
    Take a stored list of positions and revalue them at current prices.
    Returns (total_value, day_pnl) without changing entry_price.
    Entry prices are NEVER updated after inception — only shares and cost_basis matter.
    """
    total_value = 0.0
    day_pnl     = 0.0
    for p in positions:
        sym    = p.get("symbol", "")
        shares = float(p.get("shares", 0))
        entry  = float(p.get("entry_price", 0))
        price  = prices.get(sym, entry)        # fall back to entry if no live price
        prev   = prev_closes.get(sym, price)   # fall back to current if no prev

        value       = shares * price if price > 0 else shares * entry
        total_value += value
        day_pnl     += shares * (price - prev) if price > 0 and prev > 0 else 0.0

    return round(total_value, 2), round(day_pnl, 2)


def get_all_portfolios(secrets, platform):
    """
    Fetch all active portfolios with holdings from the backend.
    Also fetches existing bot_fund_state for all 5 funds so we can:
      - carry BOT13/Oracle/Wizard balances forward correctly
      - reuse Equalizer/Titan inception entry prices permanently
    Returns list of portfolio dicts, each with 'prev_states' dict:
        { 'bot13': state_dict, 'oracle': state_dict, ... }
    """
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
        else:
            print(f"  [portfolios] HTTP {r.status_code}: {r.text[:120]}")
            return []
    except Exception as e:
        print(f"  [portfolios] error: {e}")
        return []

    # Fetch previous state for ALL 5 funds per portfolio
    for portfolio in portfolios:
        bot_id      = portfolio["bot_id"]
        prev_states = {}
        for fund in ("bot13", "oracle", "wizard", "equalizer", "titan"):
            try:
                rs = _requests.get(
                    f"{api_url}/internal/portfolio-fund-state/{bot_id}/{fund}",
                    headers={"x-internal-key": key},
                    timeout=10,
                )
                if rs.status_code == 200:
                    state = rs.json().get("state")
                    if state:
                        prev_states[fund] = state
            except Exception:
                pass
        portfolio["prev_states"] = prev_states

    return portfolios


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
    picks_raw   = scored[:min(5, len(scored))]
    total_score = sum(s for _, s, *_ in picks_raw)
    raw_w       = [max(0.12, min(0.35, s / total_score)) if total_score > 0 else 0.2 for _, s, *_ in picks_raw]
    total_rw    = sum(raw_w)
    weights     = [w / total_rw for w in raw_w]
    oracle_proj = round(sum(w * ret5 for (_, _, ret5, *_), w in zip(picks_raw, weights)), 2)

    positions, picks = [], []
    for i, (sym, score, ret5, ret20, rsi, vol_r) in enumerate(picks_raw):
        w      = weights[i]
        alloc  = starting_capital * w
        price  = prices.get(sym, 0)
        shares = alloc / price if price > 0 else 0
        positions.append({
            "symbol":      sym,
            "shares":      round(shares, 6),
            "entry_price": round(price, 4),   # locked at time of rebalance
            "cost_basis":  round(alloc, 2),
        })
        picks.append({
            "symbol": sym, "weight": round(w, 4), "score": round(score, 1),
            "rationale": f"{sym}: 5d {ret5:+.1f}% | 20d {ret20:+.1f}% | RSI {rsi:.0f}. Allocated {w*100:.0f}%.",
            "indicators": {"mom_5d": round(ret5, 2), "mom_20d": round(ret20, 2), "rsi_14": round(rsi, 1)},
        })

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
            std   = statistics.stdev(daily_rets) * 100
            mean  = (sum(daily_rets) / len(daily_rets)) * 100
            sharpe = mean / std if std > 0 else 0
        dist_ma50 = (p_now / ma50 - 1) * 100 if ma50 > 0 else 0
        score = ret20 * 0.35 + ret60 * 0.35 + sharpe * 20 * 0.20 + dist_ma50 * 0.10
        scored.append((sym, score, ret20, ret60, sharpe, dist_ma50))

    if not scored:
        return "CASH", [], [], "No qualifying picks in your universe.", 0.0

    scored.sort(key=lambda x: -x[1])
    picks_raw = scored[:min(8, len(scored))]
    n         = len(picks_raw)
    q1_cut    = max(1, round(n * 0.25))
    q3_cut    = max(q1_cut + 1, round(n * 0.75))
    raw_w     = [3.0 if i < q1_cut else (1.8 if i < q3_cut else 1.0) for i in range(n)]
    total_rw  = sum(raw_w)
    weights   = [w / total_rw for w in raw_w]
    wizard_proj = round(sum(w * ret20 for (_, _, ret20, *_), w in zip(picks_raw, weights)), 2)

    positions, picks = [], []
    for i, (sym, score, ret20, ret60, sharpe, dist) in enumerate(picks_raw):
        w      = weights[i]
        alloc  = starting_capital * w
        price  = prices.get(sym, 0)
        shares = alloc / price if price > 0 else 0
        positions.append({
            "symbol":      sym,
            "shares":      round(shares, 6),
            "entry_price": round(price, 4),   # locked at time of rebalance
            "cost_basis":  round(alloc, 2),
        })
        picks.append({
            "symbol": sym, "weight": round(w, 4), "score": round(score, 1),
            "rationale": f"{sym}: 20d {ret20:+.1f}% | 60d {ret60:+.1f}% | Sharpe {sharpe:.2f}. Allocated {w*100:.0f}%.",
            "indicators": {"mom_20d": round(ret20, 2), "mom_60d": round(ret60, 2)},
        })

    rationale = (f"Projected month return: +{wizard_proj:.2f}%. "
                 f"Top {len(picks)} quality names from your {len(universe)}-stock universe.")
    return "TRADE", positions, picks, rationale, wizard_proj


def build_baseline_positions(universe, prices, prev_closes, original_cost, prev_positions):
    """
    Build Equalizer / Titan positions.

    If prev_positions exist (from a prior run), reuse their entry_price and shares
    permanently — we never change the inception allocation. Just mark current value.

    If this is the first run (no prev_positions), set entry_price = today's price.
    That price is then stored and reused forever.

    Returns (positions, total_value, day_pnl).
    """
    # Build a lookup of previously stored inception data
    prev_lookup = {}
    if prev_positions:
        for p in prev_positions:
            sym = (p.get("symbol") or "").upper()
            if sym:
                prev_lookup[sym] = p

    positions   = []
    total_value = 0.0
    day_pnl     = 0.0

    for sym in universe:
        price = prices.get(sym, 0)
        prev  = prev_closes.get(sym, price)

        if sym in prev_lookup:
            # Reuse inception entry_price and shares — never change them
            stored = prev_lookup[sym]
            shares      = float(stored.get("shares", 0))
            entry_price = float(stored.get("entry_price", price))
            cost_basis  = float(stored.get("cost_basis", 0))
        else:
            # First run for this holding — set inception values now.
            # Use prev_close as entry price so P&L reflects real movement
            # from the prior close. If no prev_close, fall back to today's price.
            alloc       = original_cost / len(universe) if universe else 0
            entry_price = prev if prev > 0 else (price if price > 0 else 1.0)
            shares      = alloc / entry_price if entry_price > 0 else 0
            cost_basis  = alloc

        value        = shares * price if price > 0 else shares * entry_price
        position_pnl = shares * (price - prev) if price > 0 and prev > 0 else 0.0

        total_value += value
        day_pnl     += position_pnl

        positions.append({
            "symbol":        sym,
            "shares":        round(shares, 6),
            "entry_price":   round(entry_price, 4),   # FIXED at inception, never updated
            "price":         round(price, 4),
            "cost_basis":    round(cost_basis, 2),
            "value":         round(value, 2),
            "pnl":           round(value - cost_basis, 2),
            "pnl_pct":       round((price / entry_price - 1) * 100 if entry_price > 0 else 0, 2),
            "day_pnl":       round(position_pnl, 2),
            "day_pct":       round((price / prev - 1) * 100 if prev > 0 else 0, 2),
        })

    return positions, round(total_value, 2), round(day_pnl, 2)


# ── Main simulation loop ──────────────────────────────────────────────────────

def run_portfolio_simulations(platform, portfolios, prices, prev_closes, hist_data):
    """
    Compute per-portfolio fund state by scaling platform tracker ratios to member capital.

    Formula for every fund:
        member_value   = entry_cost * (platform_fund_total / platform_starting_capital)
        gain_loss      = member_value - entry_cost
        gain_loss_pct  = gain_loss / entry_cost * 100
        day_pct        = same as platform day_pct (percentage is capital-neutral)
        day_pnl        = member_value * (day_pct / 100)

    BOT13 strategy/picks/rationale still come from the bot engine (for display only).
    All dollar values are derived from the platform tracker — no independent simulation drift.
    """
    today_iso  = et_now().date().isoformat()
    win_open   = _window_open(PLATFORM_CFG.get(platform, {}).get("cfg", EQUITY_CFG))
    is_equity  = PLATFORM_CFG.get(platform, {}).get("market") == "equity"
    cfg        = PLATFORM_CFG.get(platform, {}).get("cfg", EQUITY_CFG)

    # ── Fetch platform tracker state ─────────────────────────────────────────
    tracker_funds = {}
    platform_sc   = None
    try:
        r = _requests.get(
            f"{BACKEND_URL}/public/tracker/state?platform={platform}",
            timeout=15
        )
        if r.status_code == 200:
            data = r.json().get("data", {})
            platform_sc   = float(data.get("starting_capital") or 0)
            raw_funds     = data.get("funds", {})
            for fid, fdata in raw_funds.items():
                v = fdata.get("value", {})
                tracker_funds[fid] = {
                    "total":    float(v.get("total")   or 0),
                    "day_pct":  float(v.get("day_pct") or 0),
                    "day_pnl":  float(v.get("day_pnl") or 0),
                }
            print(f"  [portfolios] tracker loaded: sc={platform_sc}, funds={list(tracker_funds.keys())}")
        else:
            print(f"  [portfolios] tracker HTTP {r.status_code} — skipping")
            return []
    except Exception as e:
        print(f"  [portfolios] tracker fetch error: {e} — skipping")
        return []

    if not platform_sc or platform_sc <= 0:
        print(f"  [portfolios] platform starting_capital is 0 or missing — skipping")
        return []

    results = []

    for portfolio in portfolios:
        bot_id     = portfolio["bot_id"]
        holdings   = portfolio.get("holdings", [])
        prev_states = portfolio.get("prev_states", {})

        if not holdings:
            continue

        universe = [h["symbol"].upper() for h in holdings if h.get("symbol")]
        if not universe:
            continue

        # Skip portfolios created today
        portfolio_created = (portfolio.get("created_at") or "")[:10]
        if portfolio_created == today_iso:
            print(f"  [portfolios] skipping bot_id={bot_id} — created today, activates next trading day")
            continue

        # Minimum 5 holdings required
        if len(universe) < 5:
            print(f"  [portfolios] skipping bot_id={bot_id} — only {len(universe)} holdings, minimum 5 required")
            continue

        # Member's cost basis — always $1,000 per holding, fixed at inception
        original_cost = len(universe) * 1000.0

        for fund_name in ("bot13", "oracle", "wizard", "equalizer", "titan"):
            tf = tracker_funds.get(fund_name)
            if not tf or tf["total"] <= 0:
                print(f"  [portfolios] no tracker data for {fund_name} — skipping")
                continue

            # Scale platform performance to member capital
            ratio        = tf["total"] / platform_sc
            member_value = round(original_cost * ratio, 2)
            gain_loss    = round(member_value - original_cost, 2)
            gain_loss_pct= round(gain_loss / original_cost * 100, 4) if original_cost > 0 else 0
            day_pct      = tf["day_pct"]   # percentage is capital-neutral
            day_pnl      = round(member_value * (day_pct / 100), 2)

            # BOT13: also run engine for strategy display (picks/rationale) — not for dollar values
            strategy  = {}
            positions = []
            holding_cash = False

            if fund_name == "bot13":
                b13_state   = prev_states.get("bot13") or {}
                b13_capital = float(b13_state.get("total_value") or original_cost)
                try:
                    if is_equity:
                        portfolio_cfg = dict(cfg)
                        portfolio_cfg["min_picks"] = max(1, min(3, max(1, round(len(universe) / 3))))
                        b13_dec, b13_pos, b13_picks, b13_rat, b13_log, b13_proj = run_bot13_equity(
                            portfolio_cfg, universe, prices, prev_closes, hist_data, b13_capital, today_iso
                        )
                    else:
                        b13_dec, b13_pos, b13_picks, b13_rat, b13_log, b13_proj = run_bot13_crypto(
                            cfg, universe, prices, prev_closes, hist_data, b13_capital, today_iso
                        )
                    strategy     = {"decision": b13_dec, "picks": b13_picks, "rationale": b13_rat,
                                    "projected_return": b13_proj, "day": today_iso}
                    positions    = b13_pos or []
                    holding_cash = b13_dec in ("CASH", "HOLD")
                except Exception as e:
                    print(f"  [portfolios] bot13 engine error for {bot_id}: {e}")
                    strategy     = {"decision": "HOLD", "picks": [], "rationale": "Engine error.", "day": today_iso}
                    holding_cash = True

            elif fund_name == "oracle":
                oracle_state = prev_states.get("oracle") or {}
                oracle_day   = is_oracle_rebalance_day()
                prev_oracle_total = float(oracle_state.get("total_value") or original_cost)
                if oracle_day or not oracle_state.get("positions"):
                    try:
                        week_str = str(et_now().date().isocalendar()[0:2])
                        o_dec, o_pos, o_picks, o_rat, o_proj = run_oracle_for_universe(
                            universe, prices, prev_closes, hist_data, prev_oracle_total,
                            week_str
                        )
                        strategy  = {"decision": o_dec, "picks": o_picks, "rationale": o_rat,
                                     "projected_return": o_proj, "week": week_str}
                        positions = o_pos or []
                    except Exception as e:
                        print(f"  [portfolios] oracle engine error for {bot_id}: {e}")
                        strategy  = {"decision": "HOLD", "picks": [], "rationale": "Engine error."}
                        positions = oracle_state.get("positions") or []
                else:
                    strategy  = oracle_state.get("strategy") or {"decision": "TRADE"}
                    positions = oracle_state.get("positions") or []

            elif fund_name == "wizard":
                wizard_state = prev_states.get("wizard") or {}
                wizard_day   = is_wizard_rebalance_day()
                prev_wizard_total = float(wizard_state.get("total_value") or original_cost)
                if wizard_day or not wizard_state.get("positions"):
                    try:
                        month_str = et_now().date().strftime("%Y-%m")
                        w_dec, w_pos, w_picks, w_rat, w_proj = run_wizard_for_universe(
                            universe, prices, prev_closes, hist_data, prev_wizard_total,
                            month_str
                        )
                        strategy  = {"decision": w_dec, "picks": w_picks, "rationale": w_rat,
                                     "projected_return": w_proj, "month": month_str}
                        positions = w_pos or []
                    except Exception as e:
                        print(f"  [portfolios] wizard engine error for {bot_id}: {e}")
                        strategy  = {"decision": "HOLD", "picks": [], "rationale": "Engine error."}
                        positions = wizard_state.get("positions") or []
                else:
                    strategy  = wizard_state.get("strategy") or {"decision": "TRADE"}
                    positions = wizard_state.get("positions") or []

            elif fund_name in ("equalizer", "titan"):
                prev_state = prev_states.get(fund_name) or {}
                positions  = prev_state.get("positions") or []
                strategy   = prev_state.get("strategy") or {"decision": "TRADE"}
                # First run: build inception positions from current prices
                if not positions:
                    if fund_name == "equalizer":
                        positions, _, _ = build_baseline_positions(
                            universe, prices, prev_closes, original_cost, []
                        )
                    else:  # titan
                        n       = len(universe)
                        top_n   = max(1, round(n * 0.20))
                        sorted_u= sorted(universe, key=lambda s: prices.get(s, 0), reverse=True)
                        raw_w   = [2.0 if i < top_n else 1.0 for i in range(n)]
                        total_w = sum(raw_w)
                        weights = {sym: raw_w[i] / total_w for i, sym in enumerate(sorted_u)}
                        positions = []
                        for sym in universe:
                            w     = weights.get(sym, 1.0 / n)
                            alloc = original_cost * w
                            price = prices.get(sym, 0)
                            entry = price if price > 0 else 1.0
                            shares= alloc / entry if entry > 0 else 0
                            positions.append({
                                "symbol": sym, "shares": round(shares, 6),
                                "entry_price": round(entry, 4), "cost_basis": round(alloc, 2),
                            })

            results.append({
                "bot_id":        bot_id,
                "fund_name":     fund_name,
                "positions":     positions,
                "strategy":      strategy,
                "total_value":   member_value,
                "entry_cost":    round(original_cost, 2),
                "gain_loss":     gain_loss,
                "gain_loss_pct": gain_loss_pct,
                "day_pnl":       day_pnl,
                "day_pct":       day_pct,
                "window_open":   win_open,
                "holding_cash":  holding_cash,
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

    # Fetch portfolios (includes prev_states for all 5 funds)
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
            p