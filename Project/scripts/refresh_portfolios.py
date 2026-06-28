#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
refresh_portfolios.py
=====================
Runs all 5 bot strategy engines against every active member portfolio
and pushes results to /internal/portfolio-bot-state/upsert.

Called by each platform's refresh script after pushing global state.
Reuses prices + hist_data already fetched -- no extra API calls needed
when called inline from refresh_lvl13.py / refresh_wallstbots.py / refresh_bitbot13.py.

Can also be run standalone:
    python Project/scripts/refresh_portfolios.py --platform lvl13

Bot compounding rules (enforced here, permanent):
  BOT13     -- daily. Carries yesterday's closing total_value as next day's capital.
              Intraday refreshes mark-to-market but do NOT update carryover capital
              until the session closes (after 4 PM ET for equity, 9 PM ET for crypto).
  ORACLE    -- weekly. Rebalances ONLY on Monday. All other days: mark existing
              positions to market, carry balance forward unchanged.
  WIZARD    -- monthly. Rebalances ONLY on the 1st of the month. All other days:
              mark existing positions to market, carry balance forward unchanged.
  EQUALIZER -- buy once at inception, never sell. Entry prices stored permanently
              on first run. Value drifts with market forever.
  TITAN     -- buy once at inception, never sell. Same as Equalizer.
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
    stamp_and_log, past_close_out,
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

# -- Platform configs ----------------------------------------------------------

PLATFORM_CFG = {
    "lvl13":      {"market": "equity", "cfg": EQUITY_CFG},
    "wallstbots": {"market": "equity", "cfg": EQUITY_CFG},
    "bitbot13":   {"market": "crypto", "cfg": CRYPTO_CFG},
}


# -- Helpers -------------------------------------------------------------------

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
    return et_now().date().weekday() == 0  # 0 = Monday -- uses ET not UTC


def is_wizard_rebalance_day():
    """Wizard rebalances on the 1st of the month only."""
    return et_now().date().day == 1  # uses ET not UTC


def mark_positions_to_market(positions, prices, prev_closes):
    """
    Take a stored list of positions and revalue them at current prices.
    Returns (total_value, day_pnl) without changing entry_price.
    Entry prices are NEVER updated after inception -- only shares and cost_basis matter.
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
            print(f"  [bot-state] OK -- {res.get('upserted', 0)} states upserted")
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

    # -- BAD-DATA GUARD ------------------------------------------------------
    # A garbage price feed can return a near-zero prev_close (e.g. JUP came back
    # with prev=1.4e-05), producing an impossible day move like +1629% that then
    # poisons baseline funds, signals, and scoring for member portfolios. If a
    # coin's implied day move exceeds a sane cap, treat the prev_close as bad and
    # use today's price (day move -> ~0%) so junk data never shows as a gain.
    SANE_MOVE_CAP = 60.0  # % move beyond this in one day = bad data, not signal
    for sym in list(prices.keys()):
        p  = prices.get(sym, 0)
        pc = prev_closes.get(sym, p)
        if p > 0 and pc > 0:
            move = abs((p / pc - 1) * 100)
            if move > SANE_MOVE_CAP:
                print(f"  [prices] bad-data guard: {sym} day move {move:.0f}% "
                      f"(p={p}, prev={pc}) -- neutralizing prev_close")
                prev_closes[sym] = p

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


# -- Bot decision functions (universe-parameterized) ---------------------------

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
    permanently -- we never change the inception allocation. Just mark current value.

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
            # Reuse inception entry_price and shares -- never change them
            stored = prev_lookup[sym]
            shares      = float(stored.get("shares", 0))
            entry_price = float(stored.get("entry_price", price))
            cost_basis  = float(stored.get("cost_basis", 0))
        else:
            # First run for this holding -- set inception values now.
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


# -- Main simulation loop ------------------------------------------------------


# -- Main simulation loop ------------------------------------------------------

def run_portfolio_simulations(platform, portfolios, prices, prev_closes, hist_data, secrets=None):
    """
    Compute per-member portfolio values by scaling from the platform tracker state.

    Formula (confirmed correct):
        member_value  = entry_cost × (platform_fund_total / platform_starting_capital)
        gain_loss     = member_value - entry_cost
        gain_loss_pct = gain_loss / entry_cost × 100
        day_pct       = platform day_pct (capital-neutral -- same % regardless of member size)
        day_pnl       = member_value × (day_pct / 100)

    BOT13/Oracle/Wizard engines still run for strategy/picks/rationale display.
    Equalizer/Titan reuse stored inception positions for holdings table.
    All dollar values come from tracker ratios -- single source of truth.
    """
    if secrets is None:
        secrets = load_secrets()

    today         = et_now().date()
    today_iso     = today.isoformat()
    week_str      = str(today.isocalendar()[0:2])
    month_str     = today.strftime("%Y-%m")
    is_equity     = PLATFORM_CFG.get(platform, {}).get("market") == "equity"
    cfg           = PLATFORM_CFG.get(platform, {}).get("cfg", EQUITY_CFG)
    win_open      = _window_open(cfg)
    session_ended = is_session_closed(platform)
    oracle_day    = is_oracle_rebalance_day()
    wizard_day    = is_wizard_rebalance_day()

    # -- Fetch platform tracker state ------------------------------------------
    tracker_funds = {}
    platform_sc   = None
    try:
        r    = _requests.get(f"{BACKEND_URL}/public/tracker/state?platform={platform}", timeout=15)
        data = r.json().get("data", {})
        platform_sc = float(data.get("starting_capital") or 0)
        for fid, fdata in data.get("funds", {}).items():
            v = fdata.get("value", {})
            tracker_funds[fid] = {
                "total":   float(v.get("total")   or 0),
                "day_pct": float(v.get("day_pct") or 0),
                "day_pnl": float(v.get("day_pnl") or 0),
            }
        print(f"  [portfolios] tracker loaded: sc={platform_sc}, funds={list(tracker_funds.keys())}")
    except Exception as e:
        print(f"  [portfolios] WARNING: could not fetch tracker state: {e}")

    if not platform_sc or platform_sc <= 0:
        print(f"  [portfolios] ERROR: platform_sc={platform_sc} -- cannot scale member values. Aborting.")
        return []

    results = []

    for portfolio in portfolios:
        bot_id      = portfolio["bot_id"]
        holdings    = portfolio.get("holdings", [])
        prev_states = portfolio.get("prev_states", {})
        if not holdings:
            continue

        universe = [h["symbol"].upper() for h in holdings if h.get("symbol")]
        if not universe:
            continue

        portfolio_created = (portfolio.get("created_at") or "")[:10]
        if portfolio_created == today_iso:
            print(f"  [portfolios] skipping bot_id={bot_id} -- created today, activates next trading day")
            continue

        if len(universe) < 5:
            print(f"  [portfolios] skipping bot_id={bot_id} -- only {len(universe)} holding(s), minimum 5 required")
            continue

        original_cost = len(universe) * 1000.0

        b13_state    = prev_states.get("bot13")     or {}
        oracle_state = prev_states.get("oracle")    or {}
        wizard_state = prev_states.get("wizard")    or {}
        eq_state     = prev_states.get("equalizer") or {}
        titan_state  = prev_states.get("titan")     or {}

        prev_oracle_total = float(oracle_state.get("total_value") or original_cost)
        prev_wizard_total = float(wizard_state.get("total_value") or original_cost)

        for fund_name in ["bot13", "oracle", "wizard", "equalizer", "titan"]:
            tf = tracker_funds.get(fund_name)
            if not tf or tf["total"] <= 0:
                print(f"  [portfolios] WARNING: no tracker data for {fund_name} -- skipping")
                continue

            # Core scaling formula
            ratio        = tf["total"] / platform_sc
            member_value = round(original_cost * ratio, 2)
            gain_loss    = round(member_value - original_cost, 2)
            gain_loss_pct= round(gain_loss / original_cost * 100, 4)
            day_pct      = tf["day_pct"]   # percentage is capital-neutral
            day_pnl      = round(member_value * (day_pct / 100), 2)

            # -- Strategy / positions (for display only -- not used for dollar values) --
            positions = []
            strategy  = {}
            _member_closed_out = False   # set True below if bot13 force-flattened today

            if fund_name == "bot13":
                b13_capital = float(b13_state.get("total_value") or original_cost)
                # -- CARRY-FORWARD SANITY GUARD (mirrors the public refresh) --------
                # Member BOT13 reinvests its whole carried-forward balance each day
                # (by design), so a one-time bad price (e.g. the JUP feed) inflates
                # b13_capital and then COMPOUNDS daily. `member_value` above is the
                # clean value scaled from the now-guarded public tracker, so it is a
                # trustworthy sanity reference. If the stored capital is more than 4x
                # that, it is corrupted -- fall back to the clean scaled value. Never
                # clips real growth (the tracker scales with real gains in lockstep).
                if member_value > 0 and b13_capital > member_value * 4.0:
                    print(f"  [portfolios] BOT13 carry-forward guard: stored "
                          f"${b13_capital:,.0f} is {b13_capital/member_value:.1f}x the "
                          f"clean scaled ${member_value:,.0f} -- bad data, using scaled.")
                    b13_capital = member_value
                # Daily close-out: BOT13 must be fully flat by 3:30 PM ET (equity) /
                # 9 PM ET (crypto). If we're past that cutoff and the member's stored
                # state still shows today's strategy as TRADE with open positions, the
                # platform tracker (refresh_wallstbots.py / refresh_lvl13.py /
                # refresh_bitbot13.py) has already force-flattened for the day -- this
                # member-side script must mirror that, instead of re-asking
                # run_bot13_equity/run_bot13_crypto "what would you do right now" and
                # getting a fresh HOLD/0% that wipes Holdings while Trade History and
                # Today's Change (scaled from the tracker) still reflect the real,
                # already-closed trade. See bot13_engine.past_close_out().
                prev_b13_strategy = b13_state.get("strategy") or {}
                close_out_due = (
                    past_close_out(cfg)
                    and prev_b13_strategy.get("day") == today_iso
                    and prev_b13_strategy.get("decision") == "TRADE"
                    and bool(b13_state.get("positions"))
                )
                if close_out_due:
                    _member_closed_out = True
                    now_close = et_now().isoformat(timespec="seconds")
                    stored_b13_positions = b13_state.get("positions") or []
                    for p in stored_b13_positions:
                        p["exit_reason"] = p.get("exit_reason") or "daily close-out"
                        p["exit_time"]   = p.get("exit_time") or now_close
                    b13_dec      = "HOLD"
                    b13_pos      = []
                    b13_picks    = prev_b13_strategy.get("picks", [])
                    b13_rat      = "HOLD -- daily close-out. All positions flattened for the day."
                    b13_log      = b13_state.get("trade_log", [])
                    b13_proj     = 0.0
                    print(f"  [portfolios] BOT13 close-out -- flattened "
                          f"{len(stored_b13_positions)} position(s) (member-side mirror)")
                elif is_equity:
                    portfolio_cfg = dict(cfg)
                    portfolio_cfg["min_picks"] = max(1, min(3, max(1, round(len(universe) / 3))))
                    b13_dec, b13_pos, b13_picks, b13_rat, b13_log, b13_proj = run_bot13_equity(
                        portfolio_cfg, universe, prices, prev_closes, hist_data, b13_capital, today_iso
                    )
                else:
                    b13_dec, b13_pos, b13_picks, b13_rat, b13_log, b13_proj = run_bot13_crypto(
                        cfg, universe, prices, prev_closes, hist_data, b13_capital, today_iso
                    )
                positions = b13_pos if b13_dec == "TRADE" and b13_pos else []
                strategy  = {
                    "decision": b13_dec, "picks": b13_picks, "rationale": b13_rat,
                    "projected_return": b13_proj, "day": today_iso,
                    "session_ended": session_ended,
                }
                # BOT13 always sells before close -- after session ends it is in cash
                holding_cash = b13_dec in ("CASH", "HOLD") or session_ended

            elif fund_name == "oracle":
                # Carry-forward sanity guard (same as BOT13): if stored capital is
                # >4x the clean tracker-scaled value, it's bad data -> use scaled.
                if member_value > 0 and prev_oracle_total > member_value * 4.0:
                    print(f"  [portfolios] Oracle carry-forward guard: stored "
                          f"${prev_oracle_total:,.0f} vs clean ${member_value:,.0f} "
                          f"-- bad data, using scaled.")
                    prev_oracle_total = member_value
                if oracle_day or not oracle_state.get("positions"):
                    oracle_dec, oracle_pos, oracle_picks, oracle_rat, oracle_proj = run_oracle_for_universe(
                        universe, prices, prev_closes, hist_data, prev_oracle_total, week_str
                    )
                    positions = oracle_pos if oracle_dec == "TRADE" and oracle_pos else []
                else:
                    positions  = oracle_state.get("positions") or []
                    oracle_dec = oracle_state.get("strategy", {}).get("decision", "TRADE")
                    oracle_picks = oracle_state.get("strategy", {}).get("picks", [])
                    oracle_rat   = oracle_state.get("strategy", {}).get("rationale", "Holding weekly positions.")
                    oracle_proj  = oracle_state.get("strategy", {}).get("projected_return", 0.0)
                strategy = {
                    "decision": oracle_dec, "picks": oracle_picks, "rationale": oracle_rat,
                    "projected_return": oracle_proj, "week": week_str,
                }
                holding_cash = oracle_dec in ("CASH", "HOLD")

            elif fund_name == "wizard":
                # Carry-forward sanity guard (same as BOT13): if stored capital is
                # >4x the clean tracker-scaled value, it's bad data -> use scaled.
                if member_value > 0 and prev_wizard_total > member_value * 4.0:
                    print(f"  [portfolios] Wizard carry-forward guard: stored "
                          f"${prev_wizard_total:,.0f} vs clean ${member_value:,.0f} "
                          f"-- bad data, using scaled.")
                    prev_wizard_total = member_value
                if wizard_day or not wizard_state.get("positions"):
                    wizard_dec, wizard_pos, wizard_picks, wizard_rat, wizard_proj = run_wizard_for_universe(
                        universe, prices, prev_closes, hist_data, prev_wizard_total, month_str
                    )
                    positions = wizard_pos if wizard_dec == "TRADE" and wizard_pos else []
                else:
                    positions  = wizard_state.get("positions") or []
                    wizard_dec = wizard_state.get("strategy", {}).get("decision", "TRADE")
                    wizard_picks = wizard_state.get("strategy", {}).get("picks", [])
                    wizard_rat   = wizard_state.get("strategy", {}).get("rationale", "Holding monthly positions.")
                    wizard_proj  = wizard_state.get("strategy", {}).get("projected_return", 0.0)
                strategy = {
                    "decision": wizard_dec, "picks": wizard_picks, "rationale": wizard_rat,
                    "projected_return": wizard_proj, "month": month_str,
                }
                holding_cash = wizard_dec in ("CASH", "HOLD")

            elif fund_name == "equalizer":
                eq_prev_positions = eq_state.get("positions") or []
                positions, _, _ = build_baseline_positions(
                    universe, prices, prev_closes, original_cost, eq_prev_positions
                )
                strategy     = {"decision": "TRADE"}
                holding_cash = False

            elif fund_name == "titan":
                titan_prev_positions = titan_state.get("positions") or []
                if titan_prev_positions:
                    positions, _, _ = build_baseline_positions(
                        universe, prices, prev_closes, original_cost, titan_prev_positions
                    )
                else:
                    n      = len(universe)
                    top_n  = max(1, round(n * 0.20))
                    sorted_u = sorted(universe, key=lambda s: prices.get(s, 0), reverse=True)
                    raw_w    = [2.0 if i < top_n else 1.0 for i in range(n)]
                    total_w  = sum(raw_w)
                    weights  = {sym: raw_w[i] / total_w for i, sym in enumerate(sorted_u)}
                    inception_positions = []
                    for sym in universe:
                        w     = weights.get(sym, 1.0 / n)
                        alloc = original_cost * w
                        price = prices.get(sym, 0)
                        entry = price if price > 0 else 1.0
                        shares = alloc / entry if entry > 0 else 0
                        inception_positions.append({
                            "symbol":      sym,
                            "shares":      round(shares, 6),
                            "entry_price": round(entry, 4),
                            "cost_basis":  round(alloc, 2),
                        })
                    positions, _, _ = build_baseline_positions(
                        universe, prices, prev_closes, original_cost, inception_positions
                    )
                strategy     = {"decision": "TRADE"}
                holding_cash = False

            # --- Transparency ledger (member side): stamp opens + BUY/SELL log ---
            # Box F (Trade History) is BOT13-ONLY. Baselines/swing/hold bots were
            # generating spurious BUY/SELL/RESIZE rows from the >2% share-drift rule,
            # so we only run the ledger for bot13 and clear any stale log otherwise.
            _member_traded_today = False
            if fund_name == "bot13":
                _pstate   = prev_states.get(fund_name) or {}
                # Diff REAL positions (the accounting positions), tracked separately so
                # any display layer can't inject phantom rows. TODAY-ONLY log: reset if
                # the carried-forward log is from a prior day (also clears stale rows).
                _prev_pos = _pstate.get("positions") or []
                _prev_log = _pstate.get("trade_log") or []
                # TODAY-ONLY log: reset if carried-forward log is from a prior day
                # (also clears stale/phantom rows from the old buggy logic).
                _today = et_now().date().isoformat()
                _log_is_today = bool(_prev_log) and str((_prev_log[-1] or {}).get("ts",""))[:10] == _today
                if not _log_is_today:
                    _prev_pos = []
                    _prev_log = []
                def _bs_count(log):
                    return sum(1 for e in (log or [])
                               if str(e.get("action", "")).upper() in ("BUY", "SELL"))
                _prev_bs = _bs_count(_prev_log)
                _trade_log = stamp_and_log(_prev_pos, positions, _prev_log, et_now().isoformat(timespec="seconds"))
                _new_bs  = _bs_count(_trade_log)
                _member_traded_today = (_new_bs > _prev_bs) or _member_closed_out
            else:
                _trade_log = []

            results.append({
                "bot_id":        bot_id,
                "fund_name":     fund_name,
                "positions":     positions,
                "trade_log":     _trade_log,
                "strategy":      strategy,
                "total_value":   member_value,
                "entry_cost":    round(original_cost, 2),
                "gain_loss":     gain_loss,
                "gain_loss_pct": gain_loss_pct,
                "day_pnl":       day_pnl,
                "day_pct":       day_pct,
                "window_open":   win_open,
                "holding_cash":  holding_cash,
                "traded_today":  bool(_member_traded_today),
                "closed_out":    bool(_member_closed_out),
            })
            print(f"  [portfolios] bot_id={bot_id} {fund_name}: value=${member_value} gain={gain_loss_pct:.2f}% today={day_pct:.2f}%")

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

    portfolios = get_all_portfolios(secrets, platform)
    if not portfolios:
        print(f"  [portfolios] no active portfolios -- skipping")
        return

    all_symbols = set()
    for p in portfolios:
        for h in p.get("holdings", []):
            sym = (h.get("symbol") or "").upper()
            if sym:
                all_symbols.add(sym)

    if prices is None or not prices:
        print(f"  [portfolios] fetching prices for {len(all_symbols)} unique symbols...")
        prices, prev_closes = get_prices_for_symbols(all_symbols)
        hist_data = get_hist_for_symbols(all_symbols)
    else:
        missing = all_symbols - set(prices.keys())
        if missing:
            print(f"  [portfolios] fetching {len(missing)} additional symbols not in global state...")
            extra_p, extra_pc = get_prices_for_symbols(missing)
            extra_h = get_hist_for_symbols(missing)
            prices      = {**prices, **extra_p}
            prev_closes = {**prev_closes, **extra_pc}
            hist_data   = {**hist_data, **extra_h}

    results = run_portfolio_simulations(platform, portfolios, prices, prev_closes, hist_data or {}, secrets)
    push_bot_states(secrets, results)


# -- Standalone ----------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("platform", nargs="?", default="lvl13",
                        choices=["lvl13", "wallstbots", "bitbot13"])
    args = parser.parse_args()
    run(args.platform)
