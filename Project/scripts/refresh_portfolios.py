#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
refresh_portfolios.py
=====================
Runs all 5 bot strategy engines against every active member portfolio
and pushes results to /internal/portfolio-bot-state/upsert.

Called by each platform's refresh script after pushing global state.
Reuses prices + hist_data already fetched -- no extra API calls needed
when called inline from refresh_aistocks.py / refresh_wallstbots.py / refresh_bitbot13.py.

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
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))
from bot13_engine import (
    resolve_edge_score,
    run_bot13_equity, run_bot13_crypto,
    EQUITY_CFG, CRYPTO_CFG,
    et_now, window_open as _window_open, next_trading_day,
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
    "lvl13":      {"market": "equity", "cfg": EQUITY_CFG},   # legacy alias (pre-migration)
    # (2026-07-06 fix) "aistocks" was MISSING here: refresh_aistocks.py calls
    # run("aistocks"), which fell through to market=None -> is_equity False -> aistocks
    # member BOT13 was simulated with the CRYPTO engine and crypto session hours.
    "aistocks":   {"market": "equity", "cfg": EQUITY_CFG},
    "wallstbots": {"market": "equity", "cfg": EQUITY_CFG},
    "bitbot13":   {"market": "crypto", "cfg": CRYPTO_CFG},
}


def _entry_dp(price):
    """Decimal places for a stored entry price. Sub-penny coins need 8dp -- rounding a
    half-cent coin to 4dp shifted cost_basis vs shares*entry by ~1% (audit-caught on VET,
    2026-07-06). Same tiering as the platform crypto engine: 8dp < $0.01, 6dp < $1,
    4dp < $10, 2dp above (real equity quotes are 2dp, so stocks are unaffected)."""
    try:
        p = float(price)
    except Exception:
        return 4
    return 8 if p < 0.01 else (6 if p < 1 else (4 if p < 10 else 2))


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


def get_prices_for_symbols(symbols, yf_map=None):
    """Fetch live prices for a set of symbols via yfinance.

    yf_map (2026-07-06 crypto-parity fix): optional {state_symbol: yahoo_ticker} mapping.
    Crypto members' coins need Yahoo tickers ("ADA" -> "ADA-USD", "UNI" -> "UNI7083-USD");
    downloading raw member symbols returned junk/no prices, which is what broke bitbot13
    member baselines (-37% fiction). Same mapping source as the platform engine
    (refresh_bitbot13.UNIVERSE_MAP) -- one truth for both public and member sims.
    """
    if yf is None or not symbols:
        return {}, {}
    import pandas as pd
    yf_map = yf_map or {}
    dl_of  = {sym: (yf_map.get(sym) or sym) for sym in symbols}
    prices, prev_closes = {}, {}
    try:
        raw = yf.download(list(set(dl_of.values())), period="2d", auto_adjust=True, progress=False)
        if raw.empty:
            return {}, {}
        for sym in symbols:
            try:
                col = dl_of[sym]
                if isinstance(raw.columns, pd.MultiIndex):
                    closes = raw["Close"][col].dropna()
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


def get_hist_for_symbols(symbols, yf_map=None):
    """Fetch 90-day history for a set of symbols. yf_map: see get_prices_for_symbols."""
    if yf is None or not symbols:
        return {}
    import pandas as pd
    yf_map = yf_map or {}
    dl_of  = {sym: (yf_map.get(sym) or sym) for sym in symbols}
    hist = {}
    try:
        raw = yf.download(list(set(dl_of.values())), period="90d", auto_adjust=True, progress=False)
        if raw.empty:
            return {}
        for sym in symbols:
            try:
                col = dl_of[sym]
                if isinstance(raw.columns, pd.MultiIndex):
                    closes = [float(x) for x in raw["Close"][col].dropna().tolist()]
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
        # Shares are computed from the ROUNDED entry so cost_basis == shares * entry_price
        # exactly as stored (2026-07-06 fix: rounding after division left a ~1% gap on
        # sub-penny coins, breaking the "verifiable from entry" identity).
        price  = round(prices.get(sym, 0), _entry_dp(prices.get(sym, 0)))
        shares = alloc / price if price > 0 else 0
        positions.append({
            "symbol":      sym,
            "shares":      round(shares, 6),
            "entry_price": price,             # locked at time of rebalance
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
        # Shares from the ROUNDED entry so cost_basis == shares * entry_price exactly
        # (2026-07-06 fix -- see run_oracle_for_universe).
        price  = round(prices.get(sym, 0), _entry_dp(prices.get(sym, 0)))
        shares = alloc / price if price > 0 else 0
        positions.append({
            "symbol":      sym,
            "shares":      round(shares, 6),
            "entry_price": price,             # locked at time of rebalance
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
            # LEDGER-DERIVED (owner order 2026-07-21, kills JUP-class bugs for good):
            # cost basis is NEVER read from a stored aggregate -- it is re-derived from
            # the immutable receipt pair (shares x entry_price) on every run. A stored
            # aggregate corrupted once (JUP price-feed glitch) was carried forward
            # forever; receipt math self-heals it on the next refresh.
            cost_basis  = round(shares * entry_price, 2) if entry_price > 0 else float(stored.get("cost_basis", 0))
        else:
            # First run for this holding -- set inception values now, at the LIVE price
            # (2026-07-07, Rule 0: a real entry at a real price. The old prev_close entry
            # counted an overnight gap the fund never held as day-1 P&L).
            # NO REAL PRICE -> NO POSITION: an unpriceable symbol is skipped -- its
            # allocation stays as cash -- and it seeds itself at the real price on the
            # first run that can price it. Never a fabricated entry.
            if price <= 0:
                continue
            alloc       = original_cost / len(universe) if universe else 0
            # Shares from the ROUNDED entry so cost_basis == shares * entry_price exactly.
            entry_price = round(price, _entry_dp(price))
            shares      = alloc / entry_price if entry_price > 0 else 0
            cost_basis  = alloc

        value        = shares * price if price > 0 else shares * entry_price
        position_pnl = shares * (price - prev) if price > 0 and prev > 0 else 0.0

        total_value += value
        day_pnl     += position_pnl

        positions.append({
            "symbol":        sym,
            "shares":        round(shares, 6),
            "entry_price":   round(entry_price, _entry_dp(entry_price)),   # FIXED at inception, never updated (8dp sub-penny)
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
    Compute per-member portfolio values as INDEPENDENT simulations (CLAUDE.md Rule 0).

    Each member fund is its OWN simulation seeded at original_cost (= N x $1,000) on the
    portfolio's creation day. Every dollar value is derived from the fund's OWN positions
    at real entry prices -- see the "REAL, INDEPENDENT DOLLAR VALUES" block below. Member
    values are NEVER scaled from the platform tracker (the pre-2026-07-06 engine scaled
    member dollars by platform_total/platform_sc; that fabricated member gains and is the
    exact corruption the audit's member checks now catch -- do not reintroduce it).

    The platform tracker is still fetched, but ONLY as an availability gate and for
    logging -- never as a source of member dollar values.
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
                "total":     float(v.get("total")   or 0),
                "pnl":       float(v.get("pnl")     or 0),
                "day_open":  float(v.get("day_open") or v.get("total") or 0),
                "day_pct":   float(v.get("day_pct") or 0),
                "day_pnl":   float(v.get("day_pnl") or 0),
                "trade_log": v.get("trade_log") or [],
            }
        print(f"  [portfolios] tracker loaded: sc={platform_sc}, funds={list(tracker_funds.keys())}")
    except Exception as e:
        print(f"  [portfolios] WARNING: could not fetch tracker state: {e}")

    if not platform_sc or platform_sc <= 0:
        print(f"  [portfolios] ERROR: platform_sc={platform_sc} -- tracker state unavailable. Aborting this run.")
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

        # ACTIVATION: a portfolio NEVER trades on (or before) its creation day -- first-day numbers
        # would be fake. It begins on the next real trading SESSION. For equity that skips weekends
        # + holidays (the win_open gate on every seed/trade below enforces it); for crypto it is
        # simply the next day. Parse created_at in ET so late-evening (UTC-rollover) sign-ups line up.
        _ca = str(portfolio.get("created_at") or "")
        try:
            _cad = dt.datetime.fromisoformat(_ca.replace("Z", "+00:00"))
            if _cad.tzinfo is None:
                _cad = _cad.replace(tzinfo=dt.timezone.utc)
            created_date = _cad.astimezone(ZoneInfo("America/New_York")).date()
        except Exception:
            created_date = None
        if created_date is not None and today <= created_date:
            # A portfolio NEVER trades on its creation day (day-1 numbers would be fake). Instead of
            # skipping it (which left the page blank), write a PENDING state at starting capital so the
            # member sees their portfolio at cost with a clear "trading begins next session" message.
            # It activates -- takes its first REAL entries -- at the next trading session.
            _oc = round(len(universe) * 1000.0, 2)
            try:
                _starts = next_trading_day(cfg, created_date).isoformat()
            except Exception:
                _starts = ""
            for _fn in ["bot13", "oracle", "wizard", "equalizer", "titan"]:
                results.append({
                    "bot_id": bot_id, "fund_name": _fn, "positions": [], "trade_log": [],
                    "strategy": {"decision": "PENDING", "pending": True, "starts_on": _starts,
                                 "rationale": f"Trading begins the next trading session ({_starts})."},
                    "total_value": _oc, "entry_cost": _oc, "gain_loss": 0.0, "gain_loss_pct": 0.0,
                    "day_pnl": 0.0, "day_pct": 0.0, "window_open": False, "holding_cash": True,
                    "traded_today": False, "closed_out": False,
                })
            print(f"  [portfolios] bot_id={bot_id} PENDING -- created {created_date} (ET); trading begins {_starts}")
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

            # HONOR A STORED PENDING STATE (2026-07-06 night fix): a data repair/reset writes
            # strategy.pending=True with starts_on = the next trading session. The engine must
            # NOT trade this fund before that date. Previously only creation-day portfolios got
            # the wait rule, so a repaired fund re-seeded on the SAME mid-session refresh
            # (bitbot13, 2026-07-06 21:15 ET) -- violating "first entries at the next session".
            # Re-emit the pending state unchanged until starts_on arrives; on starts_on itself
            # the fund simulates normally and takes its first real entries.
            _pend_prev  = prev_states.get(fund_name) or {}
            _pend_strat = _pend_prev.get("strategy") if isinstance(_pend_prev.get("strategy"), dict) else {}
            if _pend_strat.get("pending") is True and str(_pend_strat.get("starts_on") or "") > today_iso:
                results.append({
                    "bot_id": bot_id, "fund_name": fund_name, "positions": [], "trade_log": [],
                    "strategy": _pend_strat,
                    "total_value": round(original_cost, 2), "entry_cost": round(original_cost, 2),
                    "gain_loss": 0.0, "gain_loss_pct": 0.0, "day_pnl": 0.0, "day_pct": 0.0,
                    "window_open": False, "holding_cash": True, "traded_today": False, "closed_out": False,
                })
                print(f"  [portfolios] bot_id={bot_id} {fund_name}: PENDING honored -- trading begins {_pend_strat.get('starts_on')}")
                continue

            # (2026-07-06) The old "core scaling formula" that computed member dollars from
            # platform tracker ratios was DELETED here. It was dead code -- its outputs were
            # overwritten by the REAL, INDEPENDENT DOLLAR VALUES block below -- but its
            # presence (and a docstring calling it "confirmed correct") invited someone to
            # trust it again. Member dollars come ONLY from the member's own positions.

            # -- Strategy / positions --
            positions = []
            strategy  = {}
            _member_closed_out = False   # set True below if bot13 force-flattened today

            if fund_name == "bot13":
                b13_capital = float(b13_state.get("total_value") or original_cost)
                # -- CARRY-FORWARD SANITY GUARD (Rule 0 compliant, 2026-07-06 fix) --
                # Member portfolios are INDEPENDENT simulations: never compare or
                # clamp against a platform-scaled number (the old guard's fallback to
                # member_value re-introduced platform scaling whenever it fired).
                # Corruption is detected the same way as the public engines: an
                # impossible day-over-day jump vs the fund's OWN prior day-open
                # (falling back to the member's own entry cost on day 1).
                _own_ref = float((b13_state.get("strategy") or {}).get("_day_open") or 0) or original_cost
                if _own_ref > 0 and b13_capital > _own_ref * 1.5:
                    print(f"  [portfolios] BOT13 carry-forward guard: stored "
                          f"${b13_capital:,.0f} is {b13_capital/_own_ref:.1f}x this fund's OWN "
                          f"prior day-open ${_own_ref:,.0f} -- bad data, using own prior value.")
                    b13_capital = _own_ref
                # Daily close-out: BOT13 must be fully flat by 3:30 PM ET (equity) /
                # 9 PM ET (crypto). If we're past that cutoff and the member's stored
                # state still shows today's strategy as TRADE with open positions, the
                # platform tracker (refresh_wallstbots.py / refresh_aistocks.py /
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
                elif not win_open:
                    # Market closed (weekend / holiday / outside session hours) -- BOT13 NEVER opens
                    # new positions on a non-trading session. Mirror the frozen public tracker: hold
                    # cash and keep the prior day's picks for display only.
                    b13_dec   = "HOLD"
                    b13_pos   = []
                    b13_picks = prev_b13_strategy.get("picks", [])
                    b13_rat   = "Market closed -- BOT13 holds cash until the next trading session."
                    b13_log   = b13_state.get("trade_log", [])
                    b13_proj  = float(prev_b13_strategy.get("projected_return", 0.0))
                elif is_equity:
                    portfolio_cfg = dict(cfg)
                    portfolio_cfg["min_picks"] = max(1, min(3, max(1, round(len(universe) / 3))))
                    b13_dec, b13_pos, b13_picks, b13_rat, b13_log, b13_proj = run_bot13_equity(
                        portfolio_cfg, universe, prices, prev_closes, hist_data, b13_capital, today_iso,
                        prev_strategy=prev_b13_strategy,
                        held_positions=b13_state.get("positions") or [],   # QUALITY OVER QUANTITY
                    )
                else:
                    b13_dec, b13_pos, b13_picks, b13_rat, b13_log, b13_proj = run_bot13_crypto(
                        cfg, universe, prices, prev_closes, hist_data, b13_capital, today_iso,
                        prev_strategy=prev_b13_strategy,
                        held_positions=b13_state.get("positions") or [],   # QUALITY OVER QUANTITY
                    )
                positions = b13_pos if b13_dec == "TRADE" and b13_pos else []
                # LEDGER CASH CARRY (2026-07-21 night fix, audit-caught): under
                # hold-the-book the engine may keep only PART of the day's book
                # (a stop closed a name) or none of it (done for the day). The
                # exited names' liquidation cash must stay in the member's total
                # or the fund looks like it lost the whole allocation (live
                # example: member fund showed -66% because 1 kept position was
                # counted as the entire fund). Banked cash accumulates across
                # today's runs in strategy["_banked"] and resets on a new day.
                _banked_b13 = 0.0
                if (prev_b13_strategy or {}).get("day") == today_iso:
                    _banked_b13 = float((prev_b13_strategy or {}).get("_banked") or 0.0)
                    _kept_syms = {p.get("symbol") for p in positions}
                    for _hp in (b13_state.get("positions") or []):
                        _s = _hp.get("symbol")
                        if _s and _s not in _kept_syms:
                            _px = float(prices.get(_s) or _hp.get("price") or _hp.get("entry_price") or 0)
                            _banked_b13 += float(_hp.get("shares") or 0) * _px
                b13_proj, _b13_samps, _b13_lastset = resolve_edge_score(prev_b13_strategy, b13_proj, b13_picks, today_iso, session_ended)  # FREEZE decision-time edge score (parity w/ engines)
                strategy  = {
                    "decision": b13_dec, "picks": b13_picks, "rationale": b13_rat,
                    "projected_return": b13_proj, "day": today_iso,
                    "proj_samples": _b13_samps, "proj_last_set": _b13_lastset,
                    "session_ended": session_ended,
                }
                # BOT13 always sells before close -- after session ends it is in cash
                holding_cash = b13_dec in ("CASH", "HOLD") or session_ended

            elif fund_name == "oracle":
                # Carry-forward sanity guard (Rule 0 compliant, 2026-07-06 fix):
                # detect corruption vs the fund's OWN prior day-open -- never clamp
                # to a platform-scaled value (that re-introduced platform scaling).
                _own_ref = float((oracle_state.get("strategy") or {}).get("_day_open") or 0) or original_cost
                if _own_ref > 0 and prev_oracle_total > _own_ref * 1.5:
                    print(f"  [portfolios] Oracle carry-forward guard: stored "
                          f"${prev_oracle_total:,.0f} vs this fund's OWN prior ${_own_ref:,.0f} "
                          f"-- bad data, using own prior value.")
                    prev_oracle_total = _own_ref
                if (oracle_day or not oracle_state.get("positions")) and win_open:  # never seed on a non-trading day
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
                # Carry-forward sanity guard (Rule 0 compliant, 2026-07-06 fix):
                # detect corruption vs the fund's OWN prior day-open -- never clamp
                # to a platform-scaled value (that re-introduced platform scaling).
                _own_ref = float((wizard_state.get("strategy") or {}).get("_day_open") or 0) or original_cost
                if _own_ref > 0 and prev_wizard_total > _own_ref * 1.5:
                    print(f"  [portfolios] Wizard carry-forward guard: stored "
                          f"${prev_wizard_total:,.0f} vs this fund's OWN prior ${_own_ref:,.0f} "
                          f"-- bad data, using own prior value.")
                    prev_wizard_total = _own_ref
                if (wizard_day or not wizard_state.get("positions")) and win_open:  # never seed on a non-trading day
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
                if not eq_prev_positions and not win_open:
                    positions = []                      # market closed -- wait for next session to seed
                else:
                    positions, _, _ = build_baseline_positions(
                        universe, prices, prev_closes, original_cost, eq_prev_positions
                    )
                strategy     = {"decision": "TRADE"}
                holding_cash = not positions

            elif fund_name == "titan":
                titan_prev_positions = titan_state.get("positions") or []
                if titan_prev_positions:
                    positions, _, _ = build_baseline_positions(
                        universe, prices, prev_closes, original_cost, titan_prev_positions
                    )
                elif not win_open:
                    positions = []                      # market closed -- wait for next session to seed
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
                        # NO REAL PRICE -> NO POSITION (2026-07-06 night fix, Rule 0): this
                        # block still fabricated a $1.00 entry after the shared builder was
                        # fixed -- the audit caught it recurring the same evening (BNC/NOTE/
                        # POL/SAFE/XEC). An unpriceable symbol stays as cash and seeds itself
                        # at the first run that can price it.
                        if price <= 0:
                            continue
                        entry  = round(price, _entry_dp(price))
                        shares = alloc / entry if entry > 0 else 0
                        inception_positions.append({
                            "symbol":      sym,
                            "shares":      round(shares, 6),
                            "entry_price": entry,             # already rounded to _entry_dp
                            "cost_basis":  round(alloc, 2),
                        })
                    positions, _, _ = build_baseline_positions(
                        universe, prices, prev_closes, original_cost, inception_positions
                    )
                strategy     = {"decision": "TRADE"}
                holding_cash = not positions

            # --- Member Trade History = the member's OWN BOT13 trades (data-integrity Rule 0:
            #     verifiable from THIS portfolio's real entries, NEVER scaled from the tracker) ---
            _member_traded_today = False
            if fund_name == "bot13":
                _today_iso = et_now().date().isoformat()
                _trade_log = [dict(e) for e in (b13_log or []) if str(e.get("ts", ""))[:10] == _today_iso]
                _member_traded_today = bool(_trade_log) or _member_closed_out
            else:
                _trade_log = []

            # ===== REAL, INDEPENDENT DOLLAR VALUES (data-integrity mission -- CLAUDE.md Rule 0) =====
            # Each member fund is its OWN simulation, seeded at original_cost (= N x $1,000) on THIS
            # portfolio's creation day. total = the LIVE value of the fund's own positions (+ carried
            # cash on a cash day) -- never scaled from the platform tracker, never inheriting prior
            # gains. Day 1 opens at original_cost, so Today's Change == Total P&L on day 1 and every
            # number is verifiable from the member's real entry prices.
            # Re-mark EVERY holding to LIVE prices (held oracle/wizard lots are otherwise reused
            # stale) so both the total and the Holdings table are current and verifiable.
            _pv = 0.0
            for _p in positions:
                _sh = float(_p.get("shares") or 0)
                _px = float(prices.get(_p.get("symbol"), _p.get("price") or 0) or 0)
                _en = float(_p.get("entry_price") or 0)
                # LEDGER-DERIVED (owner order 2026-07-21): cost basis = shares x entry
                # (the immutable receipt), never the stored aggregate. Self-heals any
                # historically corrupted cost_basis (the JUP bug) on the next refresh.
                _cb = round(_sh * _en, 2) if _en > 0 else float(_p.get("cost_basis") or 0)
                _p["cost_basis"] = _cb
                _val = round(_sh * _px, 2)
                _pc = float(prev_closes.get(_p.get("symbol"), _px) or _px)
                _p["price"]   = _px
                _p["value"]   = _val
                _p["pnl"]     = round(_val - _cb, 2)
                _p["pnl_pct"] = round((_px / _en - 1) * 100, 2) if _en > 0 else 0
                _p["day_pnl"] = round(_sh * (_px - _pc), 2)
                _p["day_pct"] = round((_px / _pc - 1) * 100, 2) if _pc > 0 else 0
                _pv += _val
            _pos_value = round(_pv, 2)
            if fund_name == "bot13":
                _carry = float(b13_capital)
            elif fund_name == "oracle":
                _carry = float(prev_oracle_total)
            elif fund_name == "wizard":
                _carry = float(prev_wizard_total)
            else:
                _carry = float(original_cost)            # equalizer/titan capital is fixed at cost
            real_total = _pos_value if positions else round(_carry, 2)
            # LEDGER CASH CARRY (2026-07-21): bot13's banked cash from today's
            # exited names stays in the total (see _banked_b13 above).
            if fund_name == "bot13":
                if _banked_b13 > 0.005:
                    real_total = round(_pos_value + _banked_b13, 2)
                strategy["_banked"] = round(_banked_b13, 2)
            # BASELINE IDLE CASH (2026-07-06, Rule 0): equalizer/titan hold $1,000 per stock;
            # a symbol with no real price yet is NOT seeded (no fabricated entries), so its
            # allocation sits as cash and MUST stay in the total (mirrors the public engine's
            # NO VANISHED CASH rule). Baselines never compound, so idle = cost - deployed.
            if fund_name in ("equalizer", "titan") and positions:
                _deployed = sum(float(_p.get("cost_basis") or 0) for _p in positions)
                _idle = max(0.0, float(original_cost) - _deployed)
                if _idle > 0.005:
                    real_total = round(_pos_value + _idle, 2)

            # Day-1 rule + day_open carry (per fund, ET). First-ever run -> day 1 opens at cost.
            _ps_map = {"bot13": b13_state, "oracle": oracle_state, "wizard": wizard_state,
                       "equalizer": eq_state, "titan": titan_state}
            _ps            = _ps_map.get(fund_name, {})
            _prev_total_f  = float(_ps.get("total_value") or 0)
            _prev_dayopen  = float((_ps.get("strategy") or {}).get("_day_open") or 0)
            _prev_asof     = str((_ps.get("strategy") or {}).get("_asof") or _ps.get("snapshot_date") or "")[:10]
            _is_day1       = _prev_total_f <= 0
            if _is_day1:
                fund_day_open = float(original_cost)      # DAY 1: opens at starting capital
            elif _prev_asof != today_iso:
                fund_day_open = _prev_total_f             # new day: prior close becomes today's open
            else:
                fund_day_open = _prev_dayopen if _prev_dayopen > 0 else _prev_total_f

            member_value  = real_total
            gain_loss     = round(real_total - original_cost, 2)
            gain_loss_pct = round(gain_loss / original_cost * 100, 4) if original_cost else 0.0
            day_pnl       = round(real_total - fund_day_open, 2)
            day_pct       = round(day_pnl / fund_day_open * 100, 4) if fund_day_open else 0.0
            strategy["_day_open"] = round(fund_day_open, 2)   # persist so tomorrow can open correctly
            strategy["_asof"]     = today_iso

            # Holdings "Today's Change" must sum to the fund's Today's Change. On day 1 every lot was
            # opened today, so each lot's day change is measured from its ENTRY (== its pnl), not a
            # prior close it never saw. (Held-overnight lots keep their prev_close day change.)
            _first_trading = (not (_ps.get("positions"))) and bool(positions)   # first day this fund holds
            if (_is_day1 or _first_trading) and positions:
                for _p in positions:
                    if _p.get("pnl") is not None:
                        _p["day_pnl"] = _p["pnl"]
                        _p["day_pct"] = _p.get("pnl_pct", 0)

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

    # CRYPTO PRICE PARITY (2026-07-06, owner-approved): on the crypto platform, member
    # symbols must be fetched with the SAME Yahoo ticker mapping the platform engine uses
    # ("ADA" -> "ADA-USD", "UNI" -> "UNI7083-USD", ...). Raw member symbols returned junk/no
    # prices, which fabricated member baseline values (bitbot13 equalizer -37% fiction).
    # Symbols outside the platform map fall back to "<SYM>-USD" (+ known aliases); anything
    # STILL unpriceable is handled honestly downstream (stays as cash, never entry=$1).
    yf_map = None
    if PLATFORM_CFG.get(platform, {}).get("market") == "crypto":
        yf_map = {}
        try:
            from refresh_bitbot13 import UNIVERSE_MAP as _platform_map   # lazy: avoids circular import at load
            yf_map.update(_platform_map)
        except Exception as _e:
            print(f"  [portfolios] WARNING: could not load platform crypto map ({_e}); using -USD fallback only")
        _CRYPTO_ALIASES = {"TRON": "TRX-USD"}   # member-entered names Yahoo knows differently
        for _s in all_symbols:
            if _s not in yf_map:
                yf_map[_s] = _CRYPTO_ALIASES.get(_s, _s + "-USD")

    if prices is None or not prices:
        print(f"  [portfolios] fetching prices for {len(all_symbols)} unique symbols...")
        prices, prev_closes = get_prices_for_symbols(all_symbols, yf_map)
        hist_data = get_hist_for_symbols(all_symbols, yf_map)
    else:
        missing = all_symbols - set(prices.keys())
        if missing:
            print(f"  [portfolios] fetching {len(missing)} additional symbols not in global state...")
            extra_p, extra_pc = get_prices_for_symbols(missing, yf_map)
            extra_h = get_hist_for_symbols(missing, yf_map)
            prices      = {**prices, **extra_p}
            prev_closes = {**prev_closes, **extra_pc}
            hist_data   = {**hist_data, **extra_h}

    results = run_portfolio_simulations(platform, portfolios, prices, prev_closes, hist_data or {}, secrets)
    push_bot_states(secrets, results)


# -- Standalone ----------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    # (2026-07-06) choices updated: "aistocks" was missing (stale pre-migration list --
    # the AI/quantum site moved from lvl13 to aistocks; lvl13 kept as a legacy alias).
    parser.add_argument("platform", nargs="?", default="aistocks",
                        choices=["lvl13", "aistocks", "wallstbots", "bitbot13"])
    args = parser.parse_args()
    run(args.platform)
