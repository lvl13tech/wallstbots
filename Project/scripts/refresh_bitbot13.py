#!/usr/bin/env python3
"""
refresh_bitbot13.py
====================
Fetches live crypto prices for the bitbot13.tech 50-coin universe,
enriches all bot positions with P&L, generates trading signals,
fetches crypto news from NewsAPI, and writes the updated static
JSON files to Frontends/bitbot13.tech/data/.

Run daily (or hourly -- crypto never closes) on your local Windows machine:
    python Project/scripts/refresh_bitbot13.py

Optional auto-push to GitHub (deploys to Cloudflare Pages):
    python Project/scripts/refresh_bitbot13.py --push

Dependencies:
    pip install yfinance requests
"""

import argparse
import datetime as dt
import json
import statistics
import subprocess
import sys
from pathlib import Path

# -- Bot13 unified engine ---------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent))
import refresh_portfolios
from bot13_engine import (
    resolve_edge_score,
    run_bot13_crypto, check_drawdown,
    CRYPTO_CFG,
    grade, grade_overall, et_now, window_open as _engine_window_open,
    stamp_and_log, reconcile_bot13_log, past_close_out,
    mark_position, build_day_reference, day_boundary_payload, fund_day_fields,
    hold_fund_totals, bot13_bank_flat_day,
)

try:
    import yfinance as yf
except ImportError:
    yf = None

try:
    import requests as _requests
except ImportError:
    _requests = None

import os   # used to read NEWSAPI_KEY env var in GitHub Actions

# -- Trading window (ET) --------------------------------------------------------
TRADING_WINDOW_START = CRYPTO_CFG["session_start"][0]   # 9
TRADING_WINDOW_END   = CRYPTO_CFG["session_end"][0]     # 21
STOP_LOSS_PCT        = CRYPTO_CFG["stop_display"]       # 1.5 -- shown to users


def in_trading_window():
    """True if current ET time is within the crypto trading session."""
    return _engine_window_open(CRYPTO_CFG)


# -- Paths ----------------------------------------------------------------------
ROOT       = Path(__file__).resolve().parents[2]
SECRETS    = ROOT / "Project" / "config" / "secrets.json"
DATA_DIR   = ROOT / "Frontends" / "bitbot13.tech" / "data"
STATE_FILE = DATA_DIR / "state.json"

# -- 50-coin universe -----------------------------------------------------------
# Keys are the symbols used in state.json; values are yfinance ticker strings
UNIVERSE_MAP = {
    "BTC":    "BTC-USD",
    "ETH":    "ETH-USD",
    "BNB":    "BNB-USD",
    "SOL":    "SOL-USD",
    "XRP":    "XRP-USD",
    "ADA":    "ADA-USD",
    "TON":    "TON-USD",
    "AVAX":   "AVAX-USD",
    "DOGE":   "DOGE-USD",
    "TRX":    "TRX-USD",
    "LINK":   "LINK-USD",
    "DOT":    "DOT-USD",
    "SHIB":   "SHIB-USD",
    "BCH":    "BCH-USD",
    "NEAR":   "NEAR-USD",
    "UNI":    "UNI7083-USD",   # yfinance uses UNI7083-USD for Uniswap
    "LTC":    "LTC-USD",
    "APT":    "APT21794-USD",  # yfinance uses APT21794-USD for Aptos
    "SUI":    "SUI20947-USD",  # yfinance uses SUI20947-USD for Sui
    "ATOM":   "ATOM-USD",
    "ICP":    "ICP-USD",
    "FIL":    "FIL-USD",
    "ARB":    "ARB11841-USD",  # yfinance uses ARB11841-USD for Arbitrum
    "AAVE":   "AAVE-USD",
    "OP":     "OP-USD",
    "ETC":    "ETC-USD",
    "VET":    "VET-USD",
    "INJ":    "INJ-USD",
    "ALGO":   "ALGO-USD",
    "XLM":    "XLM-USD",
    "HBAR":   "HBAR-USD",
    "MKR":    "MKR-USD",
    "JUP":    "JUP-USD",              # Jupiter (Solana DEX) -- Coinbase + Binance
    "RENDER": "RENDER-USD",        # Render Network -- AI/GPU, Coinbase + Binance
    "FET":    "FET-USD",           # Fetch.ai/ASI Alliance -- AI crypto, Coinbase + Binance
    "ONDO":   "ONDO-USD",          # Ondo Finance -- RWA/DeFi, Coinbase + Binance
    "WIF":    "WIF-USD",           # dogwifhat -- meme, Coinbase + Binance
    "RUNE":   "RUNE-USD",
    "QNT":    "QNT-USD",
    "KAS":    "KAS-USD",
    "THETA":  "THETA-USD",
    "WLD":    "WLD-USD",
    "SEI":    "SEI-USD",
    "EGLD":   "EGLD-USD",
    "CRV":    "CRV-USD",
    "MANTA":  "MANTA-USD",
    "PEPE":   "PEPE24478-USD", # yfinance uses PEPE24478-USD
    "FLOKI":  "FLOKI-USD",
    "PENDLE": "PENDLE-USD",
    "NOT":    "NOT-USD",
}

UNIVERSE   = list(UNIVERSE_MAP.keys())
YF_REVERSE = {v: k for k, v in UNIVERSE_MAP.items()}  # yf_sym → state_sym

# -- Crypto sectors (for oracle/wizard sector-cap logic) ------------------------
SECTORS = {
    "BTC":"LAYER1",  "ETH":"LAYER1",  "BNB":"LAYER1",  "SOL":"LAYER1",
    "XRP":"LAYER1",  "ADA":"LAYER1",  "TON":"LAYER1",  "AVAX":"LAYER1",
    "TRX":"LAYER1",  "DOT":"LAYER1",  "NEAR":"LAYER1", "ATOM":"LAYER1",
    "ALGO":"LAYER1", "ETC":"LAYER1",  "XLM":"LAYER1",  "EGLD":"LAYER1",
    "APT":"LAYER1",  "SUI":"LAYER1",  "BCH":"LAYER1",
    "LTC":"LAYER1",  "KAS":"LAYER1",  "SEI":"LAYER1",
    "DOGE":"MEME",   "SHIB":"MEME",   "PEPE":"MEME",   "FLOKI":"MEME",  "NOT":"MEME",
    "WIF":"MEME",
    "UNI":"DEFI",    "AAVE":"DEFI",   "MKR":"DEFI",    "CRV":"DEFI",
    "RUNE":"DEFI",   "INJ":"DEFI",    "PENDLE":"DEFI",  "ONDO":"DEFI",
    "ARB":"LAYER2",  "OP":"LAYER2",   "MANTA":"LAYER2", "JUP":"DEFI",
    "LINK":"INFRASTRUCTURE", "FIL":"INFRASTRUCTURE",
    "ICP":"INFRASTRUCTURE",  "HBAR":"INFRASTRUCTURE", "QNT":"INFRASTRUCTURE",
    "THETA":"INFRASTRUCTURE","VET":"INFRASTRUCTURE",
    "FET":"AI CRYPTO", "RENDER":"AI CRYPTO", "WLD":"AI CRYPTO",
}

FUND_ORDER = ["bot13", "oracle", "wizard", "equalizer", "titan"]

# -- Secrets --------------------------------------------------------------------
def load_secrets():
    if SECRETS.exists():
        return json.loads(SECRETS.read_text())
    return {}

# grade() and grade_overall() imported from bot13_engine

# -- Live prices ----------------------------------------------------------------
# -- ROOT-CAUSE PRICE VALIDATION -----------------------------------------------
# The ONLY thing that ever corrupted a fund was a bad price accepted at ingestion
# (previously validated only as ">0"). This gate compares each incoming price to the
# coin's last known good price and rejects an impossible one-refresh jump, reusing the
# last good value instead. One clean gate protects every coin, every fund, every member
# portfolio -- so no downstream cleanup is ever needed. Self-heals when the feed recovers.
MAX_UP_FACTOR   = 1.60   # >60% up in one refresh vs last known = bad data
MAX_DOWN_FACTOR = 0.40   # >60% down (i.e. below 40% of last known) = bad data

def _validate_price(sym, new_price, last_known):
    """Return a trustworthy price. If new_price is an implausible jump vs the coin's
    last known good price, reject it and reuse the last known value (logged)."""
    try:
        new_price = float(new_price)
    except Exception:
        return 0.0
    if new_price <= 0:
        return 0.0
    lk = (last_known or {}).get(sym)
    if lk and lk > 0:
        ratio = new_price / lk
        if ratio > MAX_UP_FACTOR or ratio < MAX_DOWN_FACTOR:
            print(f"  [price-guard] {sym}: rejected {new_price:g} ({ratio:.1f}x last known "
                  f"{lk:g}) -- reusing last known price (bad-feed protection)")
            return lk
    return new_price


def get_live_prices(state_symbols, last_known=None):
    """
    Fetch live price + previous close for each coin via yfinance.
    state_symbols: list of symbols as they appear in state.json (e.g. ["BTC","ETH",...])
    Returns: (prices dict, prev_closes dict) keyed by state symbol.
    """
    if yf is None:
        print("  [ERROR] yfinance not installed. Run:  pip install yfinance requests")
        return {}, {}

    import pandas as pd
    prices, prev_closes = {}, {}
    print(f"  [yfinance] fetching {len(state_symbols)} crypto tickers...")

    yf_syms   = [UNIVERSE_MAP.get(s, f"{s}-USD") for s in state_symbols]
    sym_map   = {UNIVERSE_MAP.get(s, f"{s}-USD"): s for s in state_symbols}

    # Try yfinance up to 2 times -- it can fail transiently on GitHub Actions
    for attempt in range(2):
        try:
            raw = yf.download(yf_syms, period="5d", auto_adjust=True, progress=False,
                              timeout=30)
            if not raw.empty:
                for yf_sym in yf_syms:
                    state_sym = sym_map.get(yf_sym, yf_sym)
                    try:
                        if isinstance(raw.columns, pd.MultiIndex):
                            # Handle both ("Close", "BTC-USD") and ("Close",) shapes
                            if yf_sym in raw["Close"].columns:
                                closes = raw["Close"][yf_sym].dropna()
                            else:
                                continue
                        else:
                            closes = raw["Close"].dropna()
                        if len(closes) >= 1:
                            p  = float(closes.iloc[-1])
                            pc = float(closes.iloc[-2]) if len(closes) >= 2 else p
                            p  = _validate_price(state_sym, p, last_known)
                            if p > 0:
                                prices[state_sym]      = p
                                prev_closes[state_sym] = pc
                    except Exception:
                        pass
                if prices:
                    break  # got data -- stop retrying
                print(f"  [yfinance] attempt {attempt+1}: parsed 0 prices from non-empty frame, retrying...")
            else:
                print(f"  [yfinance] attempt {attempt+1}: empty response, retrying...")
        except Exception as e:
            print(f"  [yfinance] attempt {attempt+1} download error: {e}")

    # For any coins that yfinance missed, try CoinGecko (no auth needed, free tier)
    global _CG_LAST_KNOWN
    _CG_LAST_KNOWN = last_known or {}
    missing = [s for s in state_symbols if s not in prices]
    if missing and _requests is not None:
        print(f"  [coingecko] falling back for {len(missing)} missing coins...")
        _fetch_coingecko(missing, prices, prev_closes)

    print(f"  [yfinance] got {len(prices)}/{len(state_symbols)} prices")
    return prices, prev_closes


_CG_LAST_KNOWN = {}
def _fetch_coingecko(symbols, prices, prev_closes):
    """
    CoinGecko /simple/price fallback (no API key required for free tier).
    Fills prices / prev_closes in-place.
    """
    # CoinGecko IDs for common symbols -- extend if needed
    CG_IDS = {
        "BTC":"bitcoin","ETH":"ethereum","BNB":"binancecoin","SOL":"solana",
        "XRP":"ripple","ADA":"cardano","TON":"the-open-network","AVAX":"avalanche-2",
        "DOGE":"dogecoin","TRX":"tron","LINK":"chainlink","DOT":"polkadot",
        "SHIB":"shiba-inu","BCH":"bitcoin-cash","NEAR":"near","UNI":"uniswap",
        "LTC":"litecoin","APT":"aptos","SUI":"sui","ATOM":"cosmos","ICP":"internet-computer",
        "FIL":"filecoin","ARB":"arbitrum","AAVE":"aave","OP":"optimism","ETC":"ethereum-classic",
        "VET":"vechain","INJ":"injective-protocol","ALGO":"algorand",
        "XLM":"stellar","HBAR":"hedera-hashgraph","MKR":"maker",
        "JUP":"jupiter-exchange-solana","ATOM":"cosmos","RENDER":"render-token","FET":"fetch-ai",
        "ONDO":"ondo-finance","WIF":"dogwifcoin",
        "RUNE":"thorchain","QNT":"quant-network","KAS":"kaspa",
        "THETA":"theta-token","WLD":"worldcoin-wld","SEI":"sei-network",
        "EGLD":"elrond-erd-2","CRV":"curve-dao-token","MANTA":"manta-network",
        "PEPE":"pepe","FLOKI":"floki","PENDLE":"pendle","NOT":"notcoin",
    }
    need = {s: CG_IDS[s] for s in symbols if s in CG_IDS}
    if not need:
        return
    ids_str = ",".join(need.values())
    try:
        r = _requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": ids_str, "vs_currencies": "usd",
                    "include_24hr_change": "true"},
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            id_to_sym = {v: k for k, v in need.items()}
            for cg_id, vals in data.items():
                sym = id_to_sym.get(cg_id)
                if sym and vals.get("usd"):
                    p   = float(vals["usd"])
                    chg = float(vals.get("usd_24h_change") or 0) / 100
                    pc  = p / (1 + chg) if (1 + chg) != 0 else p
                    p   = _validate_price(sym, p, _CG_LAST_KNOWN)
                    if p > 0:
                        prices[sym]      = p
                        prev_closes[sym] = pc
            print(f"  [coingecko] filled {len([s for s in symbols if s in prices])} coins")
        else:
            print(f"  [coingecko] HTTP {r.status_code}")
    except Exception as e:
        print(f"  [coingecko] error: {e}")

# -- Position enrichment --------------------------------------------------------
def enrich_position(pos, prices, prev_closes):
    # SHARED MATH (2026-07-06 de-dup): the single copy of this calculation lives
    # in bot13_engine.mark_position and is used by ALL THREE engines. Do not
    # re-implement it here -- per-site drift in this exact function is what kept
    # breaking the numbers. crypto=True keeps bitbot13's dynamic decimals and
    # crypto receipt fields exactly as before.
    return mark_position(pos, prices, prev_closes, crypto=True)

# -- RSI + history -------------------------------------------------------------
def compute_rsi(closes, period=14):
    """Compute RSI from a list of closes. Returns float 0-100."""
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
    rs = avg_g / avg_l
    return round(100 - (100 / (1 + rs)), 1)


def get_hist_data(state_symbols):
    """
    Fetch 90-day daily OHLCV history for oracle/wizard scoring.
    Uses UNIVERSE_MAP to convert state symbols to yfinance tickers.
    """
    if yf is None:
        return {}
    print("  [yfinance] fetching 90-day history for strategy scoring...")
    import pandas as pd
    yf_syms = [UNIVERSE_MAP.get(s, f"{s}-USD") for s in state_symbols]
    sym_map = {UNIVERSE_MAP.get(s, f"{s}-USD"): s for s in state_symbols}
    hist    = {}
    try:
        raw = yf.download(yf_syms, period="90d", auto_adjust=True, progress=False)
        if raw.empty:
            return {}
        for yf_sym in yf_syms:
            state_sym = sym_map.get(yf_sym, yf_sym)
            try:
                if isinstance(raw.columns, pd.MultiIndex):
                    closes  = [float(x) for x in raw["Close"][yf_sym].dropna().tolist()]
                    volumes = [float(x) for x in raw["Volume"][yf_sym].dropna().tolist()]
                else:
                    closes  = [float(x) for x in raw["Close"].dropna().tolist()]
                    volumes = [float(x) for x in raw["Volume"].dropna().tolist()]
                if len(closes) >= 20:
                    hist[state_sym] = {"closes": closes, "volumes": volumes}
            except Exception:
                pass
    except Exception as e:
        print(f"  [hist] download error: {e}")
    print(f"  [yfinance] history loaded for {len(hist)}/{len(state_symbols)} symbols")
    return hist


def get_intraday_data(state_symbols):
    """
    Fetch 5-day 1-hour OHLCV for BOT13 intraday momentum scoring.
    Returns dict: {sym: {"closes": [...], "volumes": [...]}} -- each list is hourly candles.
    """
    if yf is None:
        return {}
    import pandas as pd
    print("  [yfinance] fetching 1h intraday data for BOT13 scoring...")
    yf_syms = [UNIVERSE_MAP.get(s, f"{s}-USD") for s in state_symbols]
    sym_map = {UNIVERSE_MAP.get(s, f"{s}-USD"): s for s in state_symbols}
    intraday = {}
    try:
        raw = yf.download(yf_syms, period="5d", interval="1h", auto_adjust=True, progress=False)
        if raw.empty:
            return {}
        for yf_sym in yf_syms:
            state_sym = sym_map.get(yf_sym, yf_sym)
            try:
                if isinstance(raw.columns, pd.MultiIndex):
                    closes  = [float(x) for x in raw["Close"][yf_sym].dropna().tolist()]
                    volumes = [float(x) for x in raw["Volume"][yf_sym].dropna().tolist()]
                else:
                    closes  = [float(x) for x in raw["Close"].dropna().tolist()]
                    volumes = [float(x) for x in raw["Volume"].dropna().tolist()]
                if len(closes) >= 4:
                    intraday[state_sym] = {"closes": closes, "volumes": volumes}
            except Exception:
                pass
    except Exception as e:
        print(f"  [intraday] download error: {e}")
    print(f"  [intraday] 1h data loaded for {len(intraday)}/{len(state_symbols)} symbols")
    return intraday


# +==============================================================================+
# |  ORACLE -- Adaptive Weekly Momentum (Crypto)                                   |
# +==============================================================================+

def run_oracle_decision(prices, prev_closes, hist_data, starting_capital, week_str):
    """Score + select Oracle's weekly top-5 picks."""
    scored = []
    for sym in UNIVERSE:
        p_now = prices.get(sym, 0)
        if p_now <= 0:
            continue
        info    = hist_data.get(sym, {})
        closes  = info.get("closes", [])
        volumes = info.get("volumes", [])
        if len(closes) < 21:
            continue

        p5  = closes[-5]  if len(closes) >= 5  else closes[0]
        p20 = closes[-20] if len(closes) >= 20 else closes[0]

        ret5  = (p_now / p5  - 1) * 100 if p5  > 0 else 0
        ret20 = (p_now / p20 - 1) * 100 if p20 > 0 else 0

        # Quality gate: 20d trend must be positive
        if ret20 < 0:
            continue

        rsi = compute_rsi(closes[-15:] + [p_now])
        if rsi > 75:
            rsi_score = -0.5 * (rsi - 75) / 25
        else:
            rsi_score = (rsi - 50) / 25

        if len(volumes) >= 20:
            avg5  = sum(volumes[-5:]) / 5
            avg20 = sum(volumes[-20:]) / 20
            vol_r = avg5 / avg20 if avg20 > 0 else 1.0
        else:
            vol_r = 1.0

        composite = (
            ret5        * 0.40 +
            ret20       * 0.30 +
            rsi_score   * 10.0 * 0.20 +
            (vol_r - 1) * 10.0 * 0.10
        )
        scored.append((sym, composite, ret5, ret20, rsi, vol_r))

    if not scored:
        return None, None, None, 0.0

    scored.sort(key=lambda x: -x[1])

    # Select top 5 with sector cap (max 2 from same sector)
    picks_raw    = []
    sector_count = {}
    for sym, score, ret5, ret20, rsi, vol_r in scored:
        sec = SECTORS.get(sym, "OTHER")
        if sector_count.get(sec, 0) >= 2:
            continue
        picks_raw.append((sym, score, ret5, ret20, rsi, vol_r))
        sector_count[sec] = sector_count.get(sec, 0) + 1
        if len(picks_raw) >= 5:
            break

    if not picks_raw:
        return None, None, None, 0.0

    total_score = sum(s for _, s, *_ in picks_raw)
    raw_w       = [max(0.12, min(0.35, s / total_score)) for _, s, *_ in picks_raw]
    total_rw    = sum(raw_w)
    weights     = [w / total_rw for w in raw_w]

    oracle_proj = round(sum(w * ret5 for (_, _, ret5, *_), w in zip(picks_raw, weights)), 2)

    positions, picks = [], []
    for i, (sym, score, ret5, ret20, rsi, vol_r) in enumerate(picks_raw):
        w      = weights[i]
        alloc  = starting_capital * w
        price  = prices.get(sym, 0)
        shares = alloc / price if price > 0 else 0
        price_dp = 8 if price < 0.01 else (4 if price < 1 else 2)
        positions.append({
            "symbol":      sym,
            "shares":      round(shares, 6),
            "entry_price": round(price, price_dp),
            "cost_basis":  round(alloc, 2),
        })
        picks.append({
            "symbol":    sym,
            "weight":    round(w, 4),
            "score":     round(score, 1),
            "rationale": (f"{sym}: 5d {ret5:+.1f}% | 20d {ret20:+.1f}% | "
                          f"RSI {rsi:.0f} | Vol x{vol_r:.2f}. "
                          f"Allocated {w*100:.0f}%."),
        })

    rationale = (
        f"Projected week return: +{oracle_proj:.2f}%. "
        f"Top {len(picks)} coins by composite momentum. "
        f"Score-weighted (not equal weight). "
        f"Sector cap enforced (max 2 per category). "
        f"Quality gate: 20d momentum positive required."
    )
    return positions, picks, rationale, oracle_proj


# +==============================================================================+
# |  WIZARD -- Quality Monthly Momentum (Crypto)                                   |
# +==============================================================================+

def run_wizard_decision(prices, prev_closes, hist_data, starting_capital, month_str):
    """Score + select Wizard's monthly 8-coin quality portfolio."""
    scored = []
    for sym in UNIVERSE:
        p_now = prices.get(sym, 0)
        if p_now <= 0:
            continue
        info   = hist_data.get(sym, {})
        closes = info.get("closes", [])
        if len(closes) < 61:
            continue

        p20  = closes[-20] if len(closes) >= 20 else closes[0]
        p60  = closes[-60] if len(closes) >= 60 else closes[0]
        ma50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else p_now

        ret20 = (p_now / p20 - 1) * 100 if p20 > 0 else 0
        ret60 = (p_now / p60 - 1) * 100 if p60 > 0 else 0

        # Quality gate: 60d trend must be positive
        if ret60 < 0:
            continue

        daily_rets = [
            (closes[i] / closes[i - 1] - 1)
            for i in range(max(1, len(closes) - 60), len(closes))
        ]
        if len(daily_rets) >= 10:
            std_daily    = statistics.stdev(daily_rets) * 100
            mean_daily   = (sum(daily_rets) / len(daily_rets)) * 100
            sharpe_proxy = mean_daily / std_daily if std_daily > 0 else 0
        else:
            sharpe_proxy = 0

        dist_ma50 = (p_now / ma50 - 1) * 100 if ma50 > 0 else 0

        score = (
            ret20        * 0.35 +
            ret60        * 0.35 +
            sharpe_proxy * 20   * 0.20 +
            dist_ma50           * 0.10
        )
        scored.append((sym, score, ret20, ret60, sharpe_proxy, dist_ma50))

    if not scored:
        return None, None, None, 0.0

    scored.sort(key=lambda x: -x[1])

    picks_raw    = []
    sector_count = {}
    for sym, score, ret20, ret60, sharpe, dist in scored:
        sec = SECTORS.get(sym, "OTHER")
        if sector_count.get(sec, 0) >= 3:
            continue
        picks_raw.append((sym, score, ret20, ret60, sharpe, dist))
        sector_count[sec] = sector_count.get(sec, 0) + 1
        if len(picks_raw) >= 8:
            break

    if not picks_raw:
        return None, None, None, 0.0

    n      = len(picks_raw)
    q1_cut = max(1, round(n * 0.25))
    q3_cut = max(q1_cut + 1, round(n * 0.75))

    raw_w = []
    for i in range(n):
        if i < q1_cut:   raw_w.append(3.0)
        elif i < q3_cut: raw_w.append(1.8)
        else:            raw_w.append(1.0)

    total_rw = sum(raw_w)
    weights  = [w / total_rw for w in raw_w]

    wizard_proj = round(sum(w * ret20 for (_, _, ret20, *_), w in zip(picks_raw, weights)), 2)

    positions, picks = [], []
    for i, (sym, score, ret20, ret60, sharpe, dist) in enumerate(picks_raw):
        w      = weights[i]
        alloc  = starting_capital * w
        price  = prices.get(sym, 0)
        shares = alloc / price if price > 0 else 0
        price_dp = 8 if price < 0.01 else (4 if price < 1 else 2)
        positions.append({
            "symbol":      sym,
            "shares":      round(shares, 6),
            "entry_price": round(price, price_dp),
            "cost_basis":  round(alloc, 2),
        })
        picks.append({
            "symbol":    sym,
            "weight":    round(w, 4),
            "score":     round(score, 1),
            "rationale": (f"{sym}: 20d {ret20:+.1f}% | 60d {ret60:+.1f}% | "
                          f"Sharpe {sharpe:.2f} | {dist:+.1f}% vs 50d MA. "
                          f"Allocated {w*100:.0f}%."),
        })

    rationale = (
        f"Projected month return: +{wizard_proj:.2f}%. "
        f"Top {len(picks)} quality coins for the month. "
        f"Quartile-weighted (top coins get largest allocation). "
        f"60d quality filter applied -- no negative long-term trends. "
        f"Sector cap enforced. Stop flag at -12% intra-month."
    )
    return positions, picks, rationale, wizard_proj


# -- BOT13 crypto decision now handled by bot13_engine.run_bot13_crypto() -----

# -- Signals --------------------------------------------------------------------
def generate_signals(prices, prev_closes):
    today_iso = et_now().date().isoformat()
    recs    = []
    summary = {"STRONG BUY": 0, "BUY": 0, "HOLD": 0, "SELL": 0, "STRONG SELL": 0}

    for sym in UNIVERSE:
        p  = prices.get(sym, 0)
        pc = prev_closes.get(sym, p)
        if not p:
            continue
        pct = (p / pc - 1) * 100 if pc > 0 else 0

        if pct >= 5.0:
            signal = "STRONG BUY";  reason = f"Up {pct:+.2f}% in 24h -- strong upside momentum."
        elif pct >= 2.0:
            signal = "BUY";         reason = f"Up {pct:+.2f}% in 24h -- positive momentum."
        elif pct <= -5.0:
            signal = "STRONG SELL"; reason = f"Down {pct:+.2f}% in 24h -- sharp decline."
        elif pct <= -2.0:
            signal = "SELL";        reason = f"Down {pct:+.2f}% in 24h -- negative momentum."
        else:
            signal = "HOLD";        reason = f"Flat {pct:+.2f}% -- no clear edge right now."

        summary[signal] += 1
        price_dp = 8 if p < 0.01 else (4 if p < 1 else 2)
        # Canonical shape matching lvl13: symbol/action/upside_pct/target/score/risk/rationale/indicators
        score   = round(pct * 5, 1)
        target  = round(p * (1 + pct/100), 8 if p < 0.01 else (4 if p < 1 else 2))
        upside  = round(pct, 2)
        conf_word = "High" if abs(pct) >= 5 else ("Medium" if abs(pct) >= 2 else "Low")
        risk_word = "High" if abs(pct) >= 7 else ("Medium" if abs(pct) >= 3 else "Low")
        recs.append({
            "symbol":     sym,
            "action":     signal,
            "confidence": conf_word,
            "rationale":  reason,
            "price":      round(p, price_dp),
            "target":     target,
            "upside_pct": upside,
            "score":      score,
            "risk":       risk_word,
            "sector":     "CRYPTO",
            "date":       today_iso,
            "indicators": {"mom_1d": upside, "rsi_14": None, "macd_pct": None},
        })

    recs.sort(key=lambda r: -abs(r["upside_pct"]))
    return {
        "recommendations": recs,
        "universe_size":   len(UNIVERSE),
        "summary":         summary,
        "generated_at":    dt.datetime.now().isoformat(timespec="seconds"),
    }

# -- News -----------------------------------------------------------------------
# bitbot13 is CRYPTOCURRENCY ONLY. We restrict to crypto-native publications and
# require every accepted article to mention at least one crypto term -- per spec.

SECTOR_QUERIES = {
    "Bitcoin":    '(Bitcoin OR BTC OR "Bitcoin ETF" OR "Bitcoin halving" OR "Bitcoin price")',
    "Ethereum":   '(Ethereum OR ETH OR "Ethereum upgrade" OR "smart contracts" OR Solidity OR "Ether price")',
    "Altcoins":   '(Solana OR Cardano OR XRP OR Avalanche OR Polkadot OR Chainlink OR altcoin OR memecoin)',
    "DeFi":       '("decentralized finance" OR DeFi OR Uniswap OR Aave OR "yield farming" OR "DEX volume")',
    "Regulation": '("crypto regulation" OR "SEC crypto" OR "CFTC" OR "crypto law" OR "stablecoin regulation" OR "MiCA")',
    "Blockchain": '(blockchain OR Web3 OR NFT OR "crypto adoption" OR "crypto exchange" OR "crypto hack")',
}

# Whitelist of crypto-native publications. NewsAPI allows up to 20 domains.
BITBOT13_DOMAINS = ",".join([
    "coindesk.com", "cointelegraph.com", "decrypt.co", "theblock.co",
    "bitcoinmagazine.com", "u.today", "beincrypto.com", "cryptobriefing.com",
    "cryptoslate.com", "cryptopotato.com", "cryptonews.com", "newsbtc.com",
    "ambcrypto.com", "bitcoinist.com", "coingape.com",
])

# Positive crypto filter -- every accepted article must mention at least one of these.
# (Belt and suspenders since the domains list is already crypto-only.)
CRYPTO_REQUIRED_TERMS = (
    "bitcoin", "btc", "ethereum", "eth", "crypto", "blockchain", "altcoin",
    "defi", "stablecoin", "nft", "web3", "token", "coin", "solana", "cardano",
    "xrp", "avalanche", "polkadot", "chainlink", "memecoin", "binance", "coinbase",
    "ripple", "polygon", "uniswap", "aave", "dogecoin", "shiba",
)

def _has_term(text, terms):
    """Case-insensitive substring check for any term in the list."""
    if not text:
        return False
    t = text.lower()
    return any(term in t for term in terms)

def fetch_news(api_key):
    """Fetch CRYPTO-ONLY news from NewsAPI.org, restricted to crypto-native publications."""
    if _requests is None:
        print("  [news] requests not available -- skipping")
        return []
    if not api_key:
        print("  [news] no NewsAPI key -- skipping")
        return []

    from_date = (dt.datetime.utcnow() - dt.timedelta(days=3)).strftime("%Y-%m-%d")
    all_items = []
    seen = set()

    for sector, query in SECTOR_QUERIES.items():
        try:
            r = _requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q":         query,
                    "from":      from_date,
                    "language":  "en",
                    "sortBy":    "publishedAt",
                    "pageSize":  10,
                    "domains":   BITBOT13_DOMAINS,  # restrict to crypto outlets
                    "apiKey":    api_key,
                },
                timeout=15,
            )
            if r.status_code == 200:
                data = r.json()
                count = 0
                skipped_offtopic = 0
                for a in data.get("articles", []):
                    title       = (a.get("title") or "").split(" - ")[0].strip()
                    description = a.get("description") or ""
                    key         = title[:80].lower()
                    if not title or key in seen or "[Removed]" in title:
                        continue
                    # Require at least one crypto term in title/description
                    if not (_has_term(title, CRYPTO_REQUIRED_TERMS) or _has_term(description, CRYPTO_REQUIRED_TERMS)):
                        skipped_offtopic += 1
                        continue
                    seen.add(key)
                    all_items.append({
                        "title":        title,
                        "source":       (a.get("source") or {}).get("name", ""),
                        "sector":       sector,
                        "published_at": a.get("publishedAt"),
                        "url":          a.get("url", "#"),
                    })
                    count += 1
                msg = f"  [news] {sector}: {count} articles"
                if skipped_offtopic:
                    msg += f" ({skipped_offtopic} off-topic filtered)"
                print(msg)
            else:
                print(f"  [news] {sector} HTTP {r.status_code}: {r.text[:120]}")
        except Exception as e:
            print(f"  [news] {sector} error: {e}")

    all_items.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    all_items = all_items[:30]
    print(f"  [news] fetched {len(all_items)} total crypto articles")
    return all_items


BACKEND_URL = "https://wallstbots-backend-868128114349.us-east1.run.app"

def push_to_api(data_type, data, secrets):
    """Push any data_type (state/signals/news/reports) to the backend tracker API."""
    if _requests is None:
        return
    api_url      = secrets.get("api_url") or os.environ.get("TRACKER_API_URL", BACKEND_URL)
    internal_key = secrets.get("internal_api_key") or os.environ.get("INTERNAL_API_KEY", "")
    if not internal_key:
        print(f"  [push:{data_type}] no INTERNAL_API_KEY -- skipping")
        return
    try:
        r = _requests.post(
            f"{api_url}/internal/tracker/push",
            json={"platform": "bitbot13", "data_type": data_type, "data": data},
            headers={"x-internal-key": internal_key},
            timeout=20,
        )
        if r.status_code == 200:
            print(f"  [push:{data_type}] OK pushed to backend API")
        else:
            print(f"  [push:{data_type}] HTTP {r.status_code}: {r.text[:120]}")
    except Exception as e:
        print(f"  [push:{data_type}] error: {e}")

def trigger_portfolio_snapshots(secrets):
    """
    After pushing global state, tell the backend to compute and store
    per-portfolio daily performance snapshots for all active bitbot13 portfolios.
    """
    if _requests is None:
        return
    api_url      = secrets.get("api_url") or os.environ.get("TRACKER_API_URL", BACKEND_URL)
    internal_key = secrets.get("internal_api_key") or os.environ.get("INTERNAL_API_KEY", "")
    if not internal_key:
        print("  [snapshots] no INTERNAL_API_KEY -- skipping portfolio snapshots")
        return
    try:
        r = _requests.post(
            f"{api_url}/internal/portfolio-fund-snapshots/refresh",
            json={"platform": "bitbot13"},
            headers={"x-internal-key": internal_key},
            timeout=30,
        )
        if r.status_code == 200:
            result = r.json()
            print(f"  [snapshots] OK -- {result.get('portfolios_updated', 0)} portfolios updated, "
                  f"{result.get('prices_available', 0)} prices used")
        else:
            print(f"  [snapshots] HTTP {r.status_code}: {r.text[:120]}")
    except Exception as e:
        print(f"  [snapshots] error: {e}")

# -- Git push -------------------------------------------------------------------
def git_push(msg):
    git_root = Path(__file__).resolve().parents[2]
    try:
        subprocess.run(["git", "-C", str(git_root), "add",
                        "Frontends/bitbot13.tech/data/"], check=True)
        subprocess.run(["git", "-C", str(git_root), "commit",
                        "-m", f"auto: {msg} [{dt.datetime.now().strftime('%Y-%m-%d %H:%M')}]"],
                       check=True)
        subprocess.run(["git", "-C", str(git_root), "push"], check=True)
        print(f"[git] pushed: {msg}")
    except subprocess.CalledProcessError as e:
        print(f"[git] push failed: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--push", action="store_true")
    args = parser.parse_args()

    secrets     = load_secrets()
    newsapi_key = secrets.get("newsapi_key") or os.environ.get("NEWSAPI_KEY", "")

    print("[bitbot13] loading state.json...")
    raw = None
    if STATE_FILE.exists():
        try:
            raw = json.loads(STATE_FILE.read_text())
        except Exception as e:
            print(f"  [state.json] parse error ({e}) -- falling back to live API")
    if raw is None:
        # Fallback: fetch current state from live backend API so a corrupted
        # state.json never silently kills the entire refresh run.
        try:
            api_url = secrets.get("api_url") or os.environ.get("TRACKER_API_URL", BACKEND_URL)
            _fb = _requests.get(
                f"{api_url}/public/tracker/state?platform=bitbot13", timeout=15
            )
            raw = {"data": _fb.json().get("data", {})}
            print("  [state.json] recovered from live API ✅")
        except Exception as e2:
            print(f"  [state.json] API fallback also failed ({e2}) -- using empty state")
            raw = {"data": {}}
    state_data = raw.get("data", raw)
    funds      = state_data.get("funds", {})
    snapshots  = list(state_data.get("snapshots", []))
    sc_global  = float(state_data.get("starting_capital") or len(UNIVERSE) * 1000)

    today      = et_now().date()
    today_iso  = today.isoformat()
    now_iso    = dt.datetime.now().isoformat(timespec="seconds")
    week_str   = today.isocalendar()[0:2].__str__()
    month_str  = today.strftime("%Y-%m")

    is_monday      = today.weekday() == 0
    is_month_start = today.day <= 3

    # Force scoring on first run -- no positions means never deployed yet
    oracle_needs_seed = not funds.get("oracle", {}).get("value", {}).get("positions")
    wizard_needs_seed = not funds.get("wizard", {}).get("value", {}).get("positions")

    # -- Fetch live prices -------------------------------------------------------
    need_syms = set(UNIVERSE)
    for fid, fund in funds.items():
        for pos in fund.get("value", {}).get("positions", []):
            s = pos.get("symbol")
            if s:
                need_syms.add(s)

    # ROOT-CAUSE PRICE VALIDATION: build a "last known good price" map from the prior
    # refresh's stored positions so get_live_prices can reject an implausible jump (a
    # garbage feed value like JUP $0.000012 vs real $0.00023) BEFORE it ever enters the
    # system. Bad data never becomes a stored price -> no bad entries, no inflated shares,
    # no distorted funds. Works for all coins because it's price-vs-history, not per-symbol.
    _last_known = {}
    for _fid, _fund in funds.items():
        for _pos in (_fund.get("value", {}) or {}).get("positions", []) or []:
            _sym = _pos.get("symbol")
            _lp  = _pos.get("current_price") or _pos.get("price") or _pos.get("entry_price")
            try:
                _lp = float(_lp)
            except Exception:
                _lp = None
            if _sym and _lp and _lp > 0 and _sym not in _last_known:
                _last_known[_sym] = _lp

    print(f"[bitbot13] fetching prices for {len(need_syms)} symbols...")
    prices, prev_closes = get_live_prices(sorted(need_syms), last_known=_last_known)

    # If yfinance returned nothing, try CoinGecko directly as full fallback
    if not prices:
        print("[bitbot13] WARNING: yfinance returned zero prices -- attempting full CoinGecko fallback...")
        _fetch_coingecko(list(need_syms), prices, prev_closes)

    if not prices:
        print("[bitbot13] ERROR: zero prices from ALL sources -- aborting to protect DB data.")
        sys.exit(1)

    print(f"[bitbot13] using {len(prices)}/{len(need_syms)} prices after all sources")

    # ONE CLOCK (shared, 2026-07-06 de-dup): resolver lives in bot13_engine.
    # Crypto has no official close, so the feed's prev_close is a different
    # clock than the fund snapshot -- the stored boundary is what reconciles
    # the Today's Change box with the Holdings TODAY column here.
    day_ref_closes = build_day_reference(state_data, snapshots, today_iso, prev_closes, "bitbot13")

    # -- Fetch historical data for oracle/wizard scoring -------------------------
    hist_data = get_hist_data(sorted(need_syms))

    # -- Fetch intraday (1h) data for BOT13 scoring ------------------------------
    intraday_data = get_intraday_data(UNIVERSE)

    # -- Trading window check ----------------------------------------------------
    window_open = in_trading_window()
    _now_et = et_now(); h_et, m_et = _now_et.hour, _now_et.minute
    print(f"[bitbot13] ET time: {h_et:02d}:{m_et:02d} -- trading window {'OPEN' if window_open else 'CLOSED'}")

    # -- BOT13 decision ----------------------------------------------------------
    print("[bitbot13] running BOT13 decision...")
    prev_b13_total    = float(funds.get("bot13", {}).get("value", {}).get("total") or sc_global)

    # -- CARRY-FORWARD SANITY GUARD (day-over-day jump cap) ------------------
    # BOT13 reinvests its ENTIRE balance each day BY DESIGN, and the bots are
    # meant to run forever -- so an ABSOLUTE size ceiling is wrong (real growth
    # would eventually hit any fixed cap and get wrongly reset). What is NEVER
    # legitimate is the balance MULTIPLYING in a single day. The JUP bad-data
    # spike did exactly that (a garbage price ~19x'd the balance in one day),
    # then compounded forever after (66k -> 1.28M -> 1.59M ...). So we compare
    # today's carried-forward total to YESTERDAY's close and reject only an
    # impossible day-over-day jump -- never a normal (even very strong) day.
    # A daily-trading bot's balance multiplying >4x in a SINGLE day is not real
    # growth, it is bad data. Tune here if a legitimate day ever exceeds this.
    MAX_DAY_FACTOR = 4.0
    _prev_close = None
    try:
        for _snap in reversed(snapshots or []):
            if _snap.get("date") == today_iso:
                continue  # skip a partial snapshot already written for today
            _v = float(_snap.get("bot13") or 0)
            if _v > 0:
                _prev_close = _v
                break
    except Exception:
        _prev_close = None
    if _prev_close and prev_b13_total > _prev_close * MAX_DAY_FACTOR:
        print(f"  [bot13] CARRY-FORWARD GUARD: prior total ${prev_b13_total:,.0f} "
              f"is {prev_b13_total/_prev_close:.1f}x yesterday's close "
              f"${_prev_close:,.0f} (> {MAX_DAY_FACTOR:.0f}x cap) -- bad data, "
              f"resetting to yesterday's close")
        prev_b13_total = _prev_close
        # drop inherited positions so the bot redeploys cleanly, and clear the
        # inflated day_open so today's change isn't computed off the bad figure
        _b13v = funds.setdefault("bot13", {}).setdefault("value", {})
        _b13v["positions"] = []
        _b13v["day_open"]  = _prev_close
    b13_prev_strategy = funds.get("bot13", {}).get("current_strategy", {})
    # day_open = value at start of today's session; persists across intraday refreshes
    b13_day_open = (
        float(funds.get("bot13", {}).get("value", {}).get("day_open") or prev_b13_total)
        if b13_prev_strategy.get("day") == today_iso
        else prev_b13_total   # new day: yesterday's close becomes today's open
    )
    b13_inception  = funds.get("bot13", {}).get("inception", today_iso)
    stored_positions = funds.get("bot13", {}).get("value", {}).get("positions", [])

    # Check internal stop-loss trigger
    _stop_internal   = CRYPTO_CFG["stop_internal"]
    stops_triggered  = any(
        float(p.get("entry_price") or 0) > 0 and
        (float(prices.get(p["symbol"], float(p.get("entry_price", 0)))) /
         float(p.get("entry_price", 1)) - 1) * 100 < -_stop_internal
        for p in stored_positions if p.get("symbol")
    )

    # Account-level daily drawdown kill switch
    drawdown_hit = check_drawdown(CRYPTO_CFG, b13_day_open, stored_positions, prices)

    # Guard: if positions already exist for today AND window is open AND no stops/drawdown,
    # just re-price -- don't create new ones
    same_day_trade = (
        b13_prev_strategy.get("day") == today_iso
        and b13_prev_strategy.get("decision") == "TRADE"
        and bool(stored_positions)
        and not stops_triggered
        and not drawdown_hit
    )

    # Daily close-out: BOT13 must be fully flat by 9 PM ET. If we're past that
    # cutoff and still holding today's TRADE positions, force-flatten them now with
    # a real exit_time stamped at this exact moment -- this is what makes every SELL
    # genuine and same-day instead of being inferred later when a symbol silently
    # disappears from a later run's positions. Must be checked before the
    # "outside trading window" branch below, since close_out time == session_end
    # for crypto and window_open would already be False by then.
    close_out_due = (
        past_close_out(CRYPTO_CFG)
        and b13_prev_strategy.get("day") == today_iso
        and b13_prev_strategy.get("decision") == "TRADE"
        and bool(stored_positions)
        and not stops_triggered
        and not drawdown_hit
    )

    if b13_inception >= today_iso:  # do not trade on inception day itself
        b13_decision, b13_positions, b13_picks, b13_rationale, b13_log, b13_proj = "HOLD", [], [], "Pre-inception hold", [], 0.0
        prev_b13_total = sc_global
        print(f"  BOT13: HOLD (pre-inception, starts {b13_inception})")
    elif drawdown_hit:
        _dd_pct = round((b13_day_open - sum(
            prices.get(p["symbol"], float(p.get("entry_price", 0))) * float(p.get("shares", 0))
            for p in stored_positions if p.get("symbol")
        )) / b13_day_open * 100, 2) if stored_positions else 0
        b13_decision  = "HOLD"
        b13_positions = []
        b13_picks     = []
        b13_rationale = (f"HOLD -- daily drawdown limit reached ({_dd_pct:.2f}% account loss). "
                         "Capital protection activated. No new trades today.")
        b13_log       = b13_prev_strategy.get("session_log", [])
        b13_proj      = 0.0
        print(f"  BOT13: HOLD (daily drawdown kill switch -- {_dd_pct:.2f}% loss)")
    elif close_out_due:
        # 9 PM ET close-out -- stamp the SELL at the TRADING DAY's session close (21:00
        # ET), NOT the wall-clock time of whatever run executes this. A dropped 9pm cron
        # firing after midnight must not record a trade outside the 9am-9pm window.
        _eh, _em = CRYPTO_CFG["session_end"]
        _trade_day = (b13_prev_strategy or {}).get("day") or today_iso
        now_close = f"{_trade_day}T{_eh:02d}:{_em:02d}:00"
        for p in stored_positions:
            p["exit_reason"] = p.get("exit_reason") or "daily close-out (9pm ET)"
            p["exit_time"]   = now_close
        # Accounting HOLD (flat now), but DISPLAY preserves today's real trade story.
        b13_decision  = "HOLD"
        b13_positions = []
        b13_picks     = b13_prev_strategy.get("picks", [])
        b13_rationale = b13_prev_strategy.get("rationale", "")
        b13_log       = b13_prev_strategy.get("session_log", [])
        b13_proj      = float(b13_prev_strategy.get("projected_return", 0.0))
        print(f"  BOT13: close-out -- flattened {len(stored_positions)} position(s) at 9pm ET")
    elif not window_open:
        # Outside trading window. BOT13 is a DAILY bot -- it NEVER holds across days. Carry last
        # session's positions for the receipt display ONLY if they are from TODAY. Positions left
        # over from a PRIOR day (a missed 9pm cron, a day roll, or a mid-cycle reset) are stamped
        # closed at that day's 9pm session close and dropped, so BOT13 can never carry stale
        # holdings across midnight (which made Trade History show yesterday's positions with no log).
        _pos_day = (b13_prev_strategy or {}).get("day")
        if stored_positions and _pos_day not in (None, today_iso):
            _eh, _em = CRYPTO_CFG["session_end"]
            _close_ts = f"{_pos_day}T{_eh:02d}:{_em:02d}:00"
            for p in stored_positions:
                p["exit_reason"] = p.get("exit_reason") or "daily close-out (9pm ET)"
                p["exit_time"]   = p.get("exit_time") or _close_ts
            b13_decision  = "HOLD"
            b13_positions = []            # prior day's positions are closed -- BOT13 starts flat
            b13_picks     = []
            b13_rationale = "Prior session closed out -- BOT13 starts each day flat."
            b13_log       = []
            b13_proj      = 0.0
            print(f"  BOT13: dropped {len(stored_positions)} stale position(s) from {_pos_day} (never carry across days)")
        else:
            b13_decision  = b13_prev_strategy.get("decision", "HOLD")
            b13_positions = stored_positions  # today's positions -- preserve for receipt display
            b13_picks     = b13_prev_strategy.get("picks", [])
            b13_rationale = b13_prev_strategy.get("rationale", "")
            b13_log       = b13_prev_strategy.get("session_log", [])
            b13_proj      = float((b13_prev_strategy or {}).get("projected_return", 0.0))
            print(f"  BOT13: {b13_decision} (outside trading window {TRADING_WINDOW_START}am-{TRADING_WINDOW_END-12}pm ET -- carrying forward last session)")
    elif stops_triggered:
        # Stop-loss triggered -- mark stopped positions and open fresh picks
        now_exit = et_now().isoformat(timespec="seconds")
        for p in stored_positions:
            sym = p.get("symbol")
            if sym:
                cur = prices.get(sym, float(p.get("entry_price", 0)))
                ep  = float(p.get("entry_price") or 0)
                if ep > 0 and (cur / ep - 1) * 100 < -_stop_internal:
                    p["stop_triggered"] = True
                    p["exit_reason"]    = f"stop_loss (>{CRYPTO_CFG['stop_display']}% loss)"
                    p["exit_time"]      = now_exit
        print(f"  BOT13: stop-loss triggered -- closing stopped positions, re-picking...")
        b13_decision, b13_positions, b13_picks, b13_rationale, b13_log, b13_proj = run_bot13_crypto(
            CRYPTO_CFG, UNIVERSE, prices, prev_closes, intraday_data, b13_day_open, today_iso, b13_prev_strategy
        )
        print(f"  BOT13: re-entered with {len(b13_picks)} new picks after stop-loss")
    elif same_day_trade:
        # INTRADAY ROTATION ("trade to win"): re-score the whole universe every run.
        # The scorer keeps only qualified, positive-momentum names and drops anything
        # whose edge died -- so adopting its fresh top set naturally (a) sells a broken
        # thesis to cash and (b) rotates toward the best names. To avoid churning on
        # noise, we only SWAP a held coin for a fresh candidate when the candidate's
        # score beats the weakest held score by SWITCH_MARGIN_PCT. Held names that fall
        # out of the qualified set entirely are always dropped (edge died -> to cash).
        SWITCH_MARGIN_PCT = 18.0
        _fresh = run_bot13_crypto(
            CRYPTO_CFG, UNIVERSE, prices, prev_closes, intraday_data,
            b13_day_open, today_iso, b13_prev_strategy
        )
        _f_decision, _f_positions, _f_picks, _f_rationale, _f_log, _f_proj = _fresh
        _held_syms  = {p.get("symbol") for p in stored_positions if p.get("symbol")}
        _fresh_syms = {p.get("symbol") for p in (_f_positions or []) if p.get("symbol")}

        # -- HOLD winners; only rotate out a genuine LOSER (owner rule, 2026-07-02) --------
        # A held name is SOLD intraday ONLY if it hit its stop OR it is down >= LOSS_EXIT_PCT
        # AND its edge has died (no longer in the fresh qualified set). Winners/flat names are
        # KEPT with their ORIGINAL entry & shares (never re-sourced from the fresh run) so they
        # are held, not churned. Each freed slot is filled by the best QUALIFIED, not-currently-
        # held candidate that clearly beats the loser it replaces (SWITCH_MARGIN); any slot with
        # no stronger name goes to CASH. No more selling-and-rebuying the same name every refresh.
        _score        = {pk.get("symbol"): float(pk.get("score") or 0) for pk in (_f_picks or [])}
        _fresh_by_sym = {p.get("symbol"): p for p in (_f_positions or []) if p.get("symbol")}
        _stop_pct     = float(CRYPTO_CFG.get("stop_internal", 1.35))
        LOSS_EXIT_PCT = 1.0
        _kept, _exited, _exit_scores = [], [], []
        for _p in stored_positions:
            _sym   = _p.get("symbol")
            _entry = float(_p.get("entry_price") or 0)
            _cur   = float(prices.get(_sym, _entry) or _entry)
            _ppct  = ((_cur / _entry) - 1) * 100 if _entry > 0 else 0.0
            if (_ppct <= -_stop_pct) or (_ppct <= -LOSS_EXIT_PCT and _sym not in _fresh_syms):
                _exited.append(_sym); _exit_scores.append(float(_p.get("score") or 0))
            else:
                _kept.append(_p)                       # HOLD -- original position untouched
        _kept_syms = {p.get("symbol") for p in _kept}
        _added = []
        if _exited:
            _bar = min(_exit_scores) if _exit_scores else 0.0
            for _s in sorted([s for s in _fresh_syms if s not in _kept_syms], key=lambda s: -_score.get(s, 0.0)):
                if len(_added) >= len(_exited): break
                _cs = _score.get(_s, 0.0)
                if _cs > 0 and (_bar <= 0 or _cs >= _bar * (1 + SWITCH_MARGIN_PCT/100.0)):
                    _added.append(_fresh_by_sym[_s])   # rotate a loser into a DIFFERENT stronger name
        _added_syms = {a.get("symbol") for a in _added}
        if not _exited and not _added:
            # Pure hold -- no losers to rotate, nothing stronger to add. NO churn.
            b13_positions = stored_positions
            b13_decision  = "TRADE" if stored_positions else "HOLD"
            b13_picks     = (b13_prev_strategy or {}).get("picks", [])
            b13_rationale = (b13_prev_strategy or {}).get("rationale", "")
            b13_log       = (b13_prev_strategy or {}).get("session_log", [])
            b13_proj      = float((b13_prev_strategy or {}).get("projected_return", 0.0))
            print(f"  BOT13: hold ({len(b13_positions)} positions -- no losers to rotate)")
        else:
            b13_positions = _kept + _added
            b13_decision  = "TRADE" if b13_positions else "HOLD"
            b13_picks     = ([pk for pk in (b13_prev_strategy or {}).get("picks", []) if pk.get("symbol") in _kept_syms]
                             + [pk for pk in (_f_picks or []) if pk.get("symbol") in _added_syms])
            if _added:
                b13_proj      = float(_f_proj or 0.0)
            elif b13_positions:
                b13_proj      = float((b13_prev_strategy or {}).get("projected_return", 0.0))
            else:
                b13_proj      = 0.0
            # Rebuild the rationale from the FINAL held names so the Strategy-box prose ALWAYS
            # lists the same names as the pick cards. (A rotation rebuilt the picks but used to
            # reuse a stale rationale, so the text named different stocks than the cards.)
            if b13_picks:
                _names = ", ".join(pk.get("symbol", "") for pk in b13_picks)
                _plural = "s" if len(b13_picks) != 1 else ""
                b13_rationale = (f"Holding {len(b13_picks)} high-conviction name{_plural} "
                                 f"({_names}). Rotated {len(_exited)} loser(s) into {len(_added)} "
                                 f"stronger name(s). Stop -{CRYPTO_CFG['stop_display']}% | Target +{CRYPTO_CFG['target_pct']}%.")
            else:
                b13_rationale = "Rotated out of losing position(s) to cash -- no stronger name qualified."
            b13_log       = _f_log or (b13_prev_strategy or {}).get("session_log", [])
            print(f"  BOT13: rotation -> kept {len(_kept)}, exited {len(_exited)}, added {len(_added)}, cash-slots {len(_exited)-len(_added)}")
    elif not _engine_window_open(CRYPTO_CFG):
        # Market closed -- don't enter new positions after hours.
        # If today already had a completed TRADE, preserve its picks/log so the
        # display keeps showing what the bot did; total is preserved via prev_b13_total.
        _prior_dec  = (b13_prev_strategy or {}).get("decision")
        _stored_pos = funds.get("bot13", {}).get("value", {}).get("positions", []) or []
        if _prior_dec == "TRADE":
            b13_decision  = "HOLD"
            b13_positions = (b13_prev_strategy or {}).get("positions", _stored_pos)
            b13_picks     = (b13_prev_strategy or {}).get("picks", [])
            b13_rationale = (b13_prev_strategy or {}).get("rationale", "")
            b13_log       = (b13_prev_strategy or {}).get("session_log", [])
            b13_proj      = float((b13_prev_strategy or {}).get("projected_return", 0.0))
            print("  BOT13: HOLD (market closed -- no new positions after hours)")
        elif _stored_pos:
            # GRACEFUL FALLBACK: the prior strategy chain is broken/missing (e.g. a
            # corrupted state, a platform migration, or a skipped run) so its
            # decision isn't "TRADE" -- but there ARE positions stored from today.
            # Preserve and re-price those (re-enriched below with live prices)
            # instead of blanking the page to empty. Present them like a normal
            # held session (decision "TRADE") so the page matches a healthy site.
            b13_decision  = "TRADE"
            b13_positions = _stored_pos
            b13_picks     = (b13_prev_strategy or {}).get("picks", [])
            b13_rationale = (b13_prev_strategy or {}).get("rationale",
                              "Session complete -- holding today's positions through close.")
            b13_log       = (b13_prev_strategy or {}).get("session_log", [])
            b13_proj      = float((b13_prev_strategy or {}).get("projected_return", 0.0))
            print(f"  BOT13: recovered {len(_stored_pos)} stored positions after close (prior strategy chain was not TRADE)")
        elif (b13_prev_strategy or {}).get("day") == today_iso and (b13_prev_strategy or {}).get("rationale"):
            # Today already had a real trade (close-out already flattened it, so
            # _prior_dec is "HOLD" and _stored_pos is empty) -- keep showing what
            # the bot actually did today instead of overwriting it with the
            # generic never-traded message below.
            b13_decision  = "HOLD"
            b13_positions = []
            b13_picks     = (b13_prev_strategy or {}).get("picks", [])
            b13_rationale = b13_prev_strategy.get("rationale")
            b13_log       = (b13_prev_strategy or {}).get("session_log", [])
            b13_proj      = float((b13_prev_strategy or {}).get("projected_return", 0.0))
            print("  BOT13: HOLD (preserving today's trade story after close-out)")
        else:
            b13_decision  = "HOLD"
            b13_positions = []
            b13_picks     = []
            b13_rationale = "Market closed -- waiting for next trading session."
            b13_log       = (b13_prev_strategy or {}).get("session_log", [])
            b13_proj      = 0.0
            print("  BOT13: HOLD (market closed -- no new positions after hours)")
    else:
        # New session -- run fresh decision
        b13_decision, b13_positions, b13_picks, b13_rationale, b13_log, b13_proj = run_bot13_crypto(
            CRYPTO_CFG, UNIVERSE, prices, prev_closes, intraday_data, b13_day_open, today_iso, b13_prev_strategy
        )
        print(f"  BOT13: {b13_decision} ({len(b13_picks)} picks)")

    # -- GROUND-TRUTH GUARD: never let a no-edge re-eval erase a day that TRADED ----
    _log_now = (funds.get("bot13", {}).get("value", {}).get("trade_log") or [])
    _traded_today_log = any(
        str(e.get("ts",""))[:10] == today_iso
        and str(e.get("action","")).upper() in ("BUY", "SELL")
        for e in _log_now
    )
    if _traded_today_log and b13_decision == "HOLD" and (
        "not enough edge" in (b13_rationale or "").lower()
        or b13_proj <= CRYPTO_CFG["proj_threshold"]
    ):
        _prev_proj = float((b13_prev_strategy or {}).get("projected_return", 0.0) or 0.0)
        if _prev_proj > b13_proj:
            b13_proj = _prev_proj
        if not b13_picks:
            b13_picks = (b13_prev_strategy or {}).get("picks", [])
        b13_rationale = "Session complete -- BOT13 traded today and closed out by session end."
        print("  BOT13: ground-truth guard -- restored TRADE-day story")

    # -- ORACLE decision (Monday only) -------------------------------------------
    oracle_new_positions = None
    oracle_new_picks     = None
    oracle_new_rationale = None
    oracle_new_proj      = 0.0
    if (is_monday or oracle_needs_seed) and hist_data and window_open \
       and today_iso > str(funds.get("oracle", {}).get("inception") or today_iso):
        print(f"[bitbot13] {'Monday' if is_monday else 'first run'} -- running ORACLE recompute...")
        # Compounding: deploy the fund's CURRENT balance into new picks, not the
        # original starting capital -- so winnings are reinvested each rotation.
        # HOLDOVER GUARD: on the fund's inception day (fresh launch or a just-run reset) deploy
        # EXACTLY the starting capital -- never a carried/stale total -- so cost basis can never
        # inherit a holdover. Only AFTER inception does it compound (deploy the carried balance).
        _oracle_incep   = str(funds.get("oracle", {}).get("inception") or today_iso)
        _oracle_capital = sc_global if _oracle_incep >= today_iso else float((funds.get("oracle", {}).get("value", {}) or {}).get("total") or sc_global)
        oracle_new_positions, oracle_new_picks, oracle_new_rationale, oracle_new_proj = run_oracle_decision(
            prices, prev_closes, hist_data, _oracle_capital, week_str
        )
        if oracle_new_picks:
            print(f"  ORACLE: {len(oracle_new_picks)} new picks")
        else:
            print("  ORACLE: scoring returned no picks -- keeping existing")

    # -- WIZARD decision (month start only) --------------------------------------
    wizard_new_positions = None
    wizard_new_picks     = None
    wizard_new_rationale = None
    wizard_new_proj      = 0.0
    if (is_month_start or wizard_needs_seed) and hist_data and window_open \
       and today_iso > str(funds.get("wizard", {}).get("inception") or today_iso):
        print(f"[bitbot13] {'Month start' if is_month_start else 'first run'} ({today_iso}) -- running WIZARD recompute...")
        # HOLDOVER GUARD (see oracle): inception day -> deploy exactly sc; afterwards compound.
        _wizard_incep   = str(funds.get("wizard", {}).get("inception") or today_iso)
        _wizard_capital = sc_global if _wizard_incep >= today_iso else float((funds.get("wizard", {}).get("value", {}) or {}).get("total") or sc_global)
        wizard_new_positions, wizard_new_picks, wizard_new_rationale, wizard_new_proj = run_wizard_decision(
            prices, prev_closes, hist_data, _wizard_capital, month_str
        )
        if wizard_new_picks:
            print(f"  WIZARD: {len(wizard_new_picks)} new picks")
        else:
            print("  WIZARD: scoring returned no picks -- keeping existing")

    # -- Enrich all fund positions -----------------------------------------------
    print("[bitbot13] enriching positions...")
    FUND_ORDER = ["bot13", "oracle", "wizard", "equalizer", "titan"]
    funds_out  = {}

    for fid in FUND_ORDER:
        fund = funds.get(fid)
        if not fund:
            continue
        sc = float(fund.get("starting_capital") or sc_global)

        if fid == "bot13":
            if b13_decision == "TRADE":
                enriched  = [enrich_position(p, prices, day_ref_closes) for p in b13_positions]
                sum_pnl   = sum(p["pnl"]   for p in enriched)  # receipts: sum of position P&L
                pos_val   = sum(p["value"] for p in enriched)
                total     = b13_day_open + sum_pnl              # day_open + receipts = true total
                # cash = banked realized + undeployed capital, so total == cash +
                # pos_val holds INTRADAY too (was hardcoded 0, which broke that
                # identity whenever a rotation banked profit -- audit WARN class).
                cash      = round(total - pos_val, 2)
            else:
                # HOLD/CASH: no active positions. Use prev_b13_total so a completed
                # intraday TRADE's gains are PRESERVED after the session closes -- the bot
                # reinvests its whole balance daily, so banked gains carry forward instead
                # of collapsing to day_open. (Matches equity engine; on a true no-trade
                # day prev_b13_total == b13_day_open.)
                enriched  = []
                pos_val   = 0.0
                total     = prev_b13_total
                cash      = prev_b13_total

            pnl          = total - sc                                    # total gain since inception
            pnl_pct      = (pnl / sc * 100) if sc else 0
            day_pnl_total = total - b13_day_open                        # full day's accumulated gain
            day_pct      = (day_pnl_total / b13_day_open * 100) if b13_day_open else 0

            # holding_cash: true whenever bot13 is not actively in positions
            holding_cash = (b13_decision != "TRADE") or not window_open

            # -- After-hours DISPLAY freeze (Box C/D/E) -------------------------------
            # When bot13 is flat but TRADED earlier today (closed out at session end),
            # keep the day's positions visible READ-ONLY so Holdings + Trade History
            # tell the same story until the next session opens. Display only -- the
            # inception total/pnl above are NOT touched. traded_today lets the frontend
            # show "End of trading - now holding cash" vs "Holding cash - no trades
            # made today".
            _stored_log = (funds.get("bot13", {}).get("value", {}).get("trade_log") or [])
            _traded_in_log = any(
                str(e.get("ts",""))[:10] == today_iso
                and str(e.get("action","")).upper() in ("BUY","SELL")
                for e in _stored_log
            )
            traded_today = _traded_in_log or (
                b13_prev_strategy.get("day") == today_iso and bool(b13_prev_strategy.get("picks"))
            )
            display_positions = enriched
            if not enriched and traded_today and stored_positions:
                # Re-enrich stored positions for the read-only Holdings display after close.
                # Today's Change keeps day_pnl_total = total - b13_day_open (computed above), so it
                # equals Total P&L on day 1 and matches wallstbots/aistocks. (Removed the realized-
                # sum override that diverged bitbot13 and broke the one-day rule.)
                # FROZEN RECEIPT (2026-07-05): a CLOSED position's row must show the FINAL
                # price its SELL was recorded at, not the live market -- otherwise every
                # later refresh drifts the Holdings row away from Trade History's realized.
                _sell_px = {str(e.get("symbol")): float(e.get("price") or 0)
                            for e in _stored_log
                            if str(e.get("action","")).upper() == "SELL"
                            and str(e.get("ts",""))[:10] == today_iso}
                _pin = dict(prices)
                _pin.update({s: p for s, p in _sell_px.items() if p > 0})
                display_positions = [enrich_position(p, _pin, day_ref_closes) for p in stored_positions]

            value    = {"total": round(total,2), "cash": round(cash,2), "pos_val": round(pos_val,2),
                        "pnl": round(pnl,2), "pnl_pct": round(pnl_pct,2),
                        "day_pnl": round(day_pnl_total,2), "day_pct": round(day_pct,2),
                        "day_open": round(b13_day_open,2), "holding_cash": holding_cash,
                        "window_open": window_open,
                        "traded_today": traded_today,
                        "session_open_et": f"{TRADING_WINDOW_START}:00",
                        "session_close_et": f"{TRADING_WINDOW_END}:00",
                        "positions": display_positions}
            b13_proj, _b13_samps, _b13_lastset = resolve_edge_score(b13_prev_strategy, b13_proj, b13_picks, today_iso, not window_open)  # FREEZE decision-time edge score for the day (never becomes Today's Change)
            _display_decision = "TRADE" if traded_today else b13_decision
            strategy = {
                "day":              today_iso,
                "decision":         _display_decision,
                "rationale":        b13_rationale,
                "picks":            b13_picks,
                "session_log":      b13_log,
                "stop_pct":         -CRYPTO_CFG["stop_display"],
                "target_pct":       CRYPTO_CFG["target_pct"],
                "window_open":      window_open,
                "last_updated":     now_iso,
                "projected_return": round(b13_proj, 2),
                "proj_samples": _b13_samps, "proj_last_set": _b13_lastset,
                "traded_today":     traded_today,
            }

        elif fid == "oracle":
            if oracle_new_positions:
                fund_copy = dict(fund)
                fund_copy["value"] = dict(fund.get("value", {}))
                fund_copy["value"]["positions"] = oracle_new_positions
                fund = fund_copy
                strategy = {
                    "week":             today_iso,
                    "decision":         "TRADE",
                    "rationale":        oracle_new_rationale,
                    "picks":            oracle_new_picks,
                    "projected_return": round(oracle_new_proj, 2),
                }
            else:
                strategy = fund.get("current_strategy") or {}
                strategy = {**strategy, "week": week_str}

            raw_pos = fund.get("value", {}).get("positions", [])
            # NOTE (2026-07-02): NO inception-day entry_price rebase. The seed functions already
            # set entry_price = the price the shares were bought at, so cost_basis (= shares*entry)
            # equals the capital deployed and Sum(position P&L) == fund P&L. Rebasing entry_price to
            # prev_close here left shares/cost_basis untouched, so enrich_position recomputed
            # cost_basis = shares*prev_close != deployed capital -> positions no longer summed to the
            # fund's Total P&L on seed day. Do not re-add this block.
            enriched = [enrich_position(p, prices, day_ref_closes) for p in raw_pos]
            pos_val  = sum(p["value"]   for p in enriched)
            # CUMULATIVE / COMPOUNDING (mark-to-market on full balance): the entire
            # balance is deployed into the picks, so total = current market value of
            # positions. pnl is measured vs the original starting capital (sc), so it
            # compounds across rotations and NEVER resets to sc. Falls back to prior
            # total only if there are momentarily no positions (between rotations).
            # SHARED math: residual cash + compounding total live once in bot13_engine.
            cash, total, pnl, pnl_pct, strategy = hold_fund_totals(
                fund, sc, enriched, pos_val, oracle_new_positions,
                _oracle_capital if oracle_new_positions else 0.0, strategy, "ORACLE")
            # Today's Change = total - today's OPENING total (consistent with Total P&L;
            # on day 1 day_open == sc so day_pnl == pnl). day_open carries within a day,
            # resets to the prior close on a new day.
            # Today's Change = total - YESTERDAY'S close (prior-day snapshot). On day 1 the
            # only prior snapshot is the reset baseline (== sc) so day_open == sc and
            # day_pnl == pnl exactly (owner's one-day rule). Sourcing day_open from the
            # snapshot -- not the live mid-day total -- is what keeps Today's Change correct.
            _oracle_day_open, day_pnl, day_pct = fund_day_fields(total, fid, sc, snapshots, today_iso)  # SHARED math

            # Reconcile Holdings TODAY with the fund's Today's Change box. If the fund
            # deployed fresh capital today (these positions were NOT held at yesterday's
            # close), each position's day change is measured from ENTRY (== its pnl) so
            # Holdings never shows a full-day move the fund never took. Detected by comparing
            # the positions' value-at-yesterday's-close to day_open (survives intraday reruns).
            _held_val = sum(p["shares"] * day_ref_closes.get(p["symbol"], p["price"]) for p in enriched)
            if enriched and _oracle_day_open and abs(_held_val - _oracle_day_open) > max(1.0, _oracle_day_open * 0.001):
                for _p in enriched:
                    _p["day_pnl"] = _p["pnl"]; _p["day_pct"] = _p["pnl_pct"]

            # holding_cash for oracle: true on weekends (no active management until Monday)
            oracle_holding_cash = not enriched   # in cash ONLY when it holds no positions (oracle holds its basket through weekends/closed days, so never flag "cash" while invested)
            # Oracle NEVER decides to sit out -- if it holds positions the decision is TRADE.
            if enriched:
                strategy = {**(strategy or {}), "decision": "TRADE"}

            value    = {"total": round(total,2), "cash": round(cash,2), "pos_val": round(pos_val,2),
                        "pnl": round(pnl,2), "pnl_pct": round(pnl_pct,2),
                        "day_pnl": round(day_pnl,2), "day_pct": round(day_pct,2),
                        "day_open": round(_oracle_day_open,2), "day_open_date": today_iso,
                        "holding_cash": oracle_holding_cash, "positions": enriched}

        elif fid == "wizard":
            if wizard_new_positions:
                fund_copy = dict(fund)
                fund_copy["value"] = dict(fund.get("value", {}))
                fund_copy["value"]["positions"] = wizard_new_positions
                fund = fund_copy
                strategy = {
                    "month":            month_str,
                    "decision":         "TRADE",
                    "rationale":        wizard_new_rationale,
                    "picks":            wizard_new_picks,
                    "projected_return": round(wizard_new_proj, 2),
                }
            else:
                strategy = fund.get("current_strategy") or {}
                strategy = {**strategy, "month": month_str}

            raw_pos = fund.get("value", {}).get("positions", [])
            # NOTE (2026-07-02): NO inception-day entry_price rebase. The seed functions already
            # set entry_price = the price the shares were bought at, so cost_basis (= shares*entry)
            # equals the capital deployed and Sum(position P&L) == fund P&L. Rebasing entry_price to
            # prev_close here left shares/cost_basis untouched, so enrich_position recomputed
            # cost_basis = shares*prev_close != deployed capital -> positions no longer summed to the
            # fund's Total P&L on seed day. Do not re-add this block.
            enriched = []
            for p in raw_pos:
                ep = enrich_position(p, prices, day_ref_closes)
                if ep["pnl_pct"] < -STOP_LOSS_PCT:
                    ep["stop_triggered"] = True
                enriched.append(ep)
            pos_val  = sum(p["value"]   for p in enriched)
            # CUMULATIVE / COMPOUNDING (mark-to-market on full balance) -- see oracle note.
            # SHARED math: residual cash + compounding total live once in bot13_engine.
            cash, total, pnl, pnl_pct, strategy = hold_fund_totals(
                fund, sc, enriched, pos_val, wizard_new_positions,
                _wizard_capital if wizard_new_positions else 0.0, strategy, "WIZARD")
            # Today's Change = total - today's OPENING total (consistent with Total P&L).
            # Today's Change = total - YESTERDAY'S close (prior-day snapshot) -- see oracle note.
            _wiz_day_open, day_pnl, day_pct = fund_day_fields(total, fid, sc, snapshots, today_iso)  # SHARED math

            # Reconcile Holdings TODAY with the fund's Today's Change box. If the fund
            # deployed fresh capital today (these positions were NOT held at yesterday's
            # close), each position's day change is measured from ENTRY (== its pnl) so
            # Holdings never shows a full-day move the fund never took. Detected by comparing
            # the positions' value-at-yesterday's-close to day_open (survives intraday reruns).
            _held_val = sum(p["shares"] * day_ref_closes.get(p["symbol"], p["price"]) for p in enriched)
            if enriched and _wiz_day_open and abs(_held_val - _wiz_day_open) > max(1.0, _wiz_day_open * 0.001):
                for _p in enriched:
                    _p["day_pnl"] = _p["pnl"]; _p["day_pct"] = _p["pnl_pct"]
            # Wizard NEVER decides to sit out -- if it holds positions the decision is TRADE.
            if enriched:
                strategy = {**(strategy or {}), "decision": "TRADE"}
            value    = {"total": round(total,2), "cash": round(cash,2), "pos_val": round(pos_val,2),
                        "pnl": round(pnl,2), "pnl_pct": round(pnl_pct,2),
                        "day_pnl": round(day_pnl,2), "day_pct": round(day_pct,2),
                        "day_open": round(_wiz_day_open,2), "day_open_date": today_iso, "positions": enriched}

        else:
            # Equalizer + Titan -- mark-to-market; auto-seed on first run
            raw_pos = fund.get("value", {}).get("positions", [])

            if not raw_pos and fid == "equalizer" and prices and window_open \
               and today_iso > str(fund.get("inception") or today_iso):
                per_coin = sc / len(UNIVERSE)
                for sym in UNIVERSE:
                    price = prev_closes.get(sym) or prices.get(sym, 0)
                    if price > 0:
                        price_dp = 8 if price < 0.01 else (4 if price < 1 else 2)
                        raw_pos.append({
                            "symbol":      sym,
                            "shares":      round(per_coin / price, 6),
                            "entry_price": round(price, price_dp),
                            "cost_basis":  round(per_coin, 2),
                        })
                print(f"  EQUALIZER: seeded {len(raw_pos)} positions at ${per_coin:.0f}/coin")

            elif not raw_pos and fid == "titan" and prices and window_open \
                 and today_iso > str(fund.get("inception") or today_iso):
                top10    = fund.get("top10") or []
                per_top  = float(fund.get("per_top_dollars") or 0)
                per_rest = float(fund.get("per_rest_dollars") or 0)
                rest     = [s for s in UNIVERSE if s not in top10]
                for sym in top10:
                    price = prev_closes.get(sym) or prices.get(sym, 0)
                    if price > 0 and per_top > 0:
                        price_dp = 8 if price < 0.01 else (4 if price < 1 else 2)
                        raw_pos.append({"symbol": sym, "shares": round(per_top / price, 6),
                                        "entry_price": round(price, price_dp), "cost_basis": round(per_top, 2)})
                for sym in rest:
                    price = prev_closes.get(sym) or prices.get(sym, 0)
                    if price > 0 and per_rest > 0:
                        price_dp = 8 if price < 0.01 else (4 if price < 1 else 2)
                        raw_pos.append({"symbol": sym, "shares": round(per_rest / price, 6),
                                        "entry_price": round(price, price_dp), "cost_basis": round(per_rest, 2)})
                print(f"  TITAN: seeded {len(raw_pos)} positions (top10 ${per_top:.0f} / rest ${per_rest:.0f})")

            # NOTE (2026-07-02): NO inception-day entry_price rebase. The seed functions already
            # set entry_price = the price the shares were bought at, so cost_basis (= shares*entry)
            # equals the capital deployed and Sum(position P&L) == fund P&L. Rebasing entry_price to
            # prev_close here left shares/cost_basis untouched, so enrich_position recomputed
            # cost_basis = shares*prev_close != deployed capital -> positions no longer summed to the
            # fund's Total P&L on seed day. Do not re-add this block.
            enriched = [enrich_position(p, prices, day_ref_closes) for p in raw_pos]
            pos_val  = sum(p["value"]   for p in enriched)
            pnl      = sum(p["pnl"]     for p in enriched)
            total    = sc + pnl
            cash     = max(0.0, total - pos_val)
            pnl_pct  = (pnl / sc * 100) if sc else 0
            # Today's Change = total - YESTERDAY'S close (prior-day snapshot), same rule as
            # oracle/wizard so day_pnl == pnl on day 1 and reconciles with Total P&L.
            _eq_day_open, day_pnl, day_pct = fund_day_fields(total, fid, sc, snapshots, today_iso)  # SHARED math

            # Reconcile Holdings TODAY with the fund's Today's Change box. If the fund
            # deployed fresh capital today (these positions were NOT held at yesterday's
            # close), each position's day change is measured from ENTRY (== its pnl) so
            # Holdings never shows a full-day move the fund never took. Detected by comparing
            # the positions' value-at-yesterday's-close to day_open (survives intraday reruns).
            _held_val = sum(p["shares"] * day_ref_closes.get(p["symbol"], p["price"]) for p in enriched)
            if enriched and _eq_day_open and abs(_held_val - _eq_day_open) > max(1.0, _eq_day_open * 0.001):
                for _p in enriched:
                    _p["day_pnl"] = _p["pnl"]; _p["day_pct"] = _p["pnl_pct"]
            value    = {"total": round(total,2), "cash": round(cash,2), "pos_val": round(pos_val,2),
                        "pnl": round(pnl,2), "pnl_pct": round(pnl_pct,2),
                        "day_pnl": round(day_pnl,2), "day_pct": round(day_pct,2),
                        "day_open": round(_eq_day_open,2), "positions": enriched}
            strategy = fund.get("current_strategy")

        # --- Transparency ledger: stamp entry_time on opens + append BUY/SELL log ---
        # Box F (Trade History) is BOT13-ONLY. The buy-and-hold baselines (oracle,
        # wizard, equalizer, titan) were generating spurious BUY/SELL/RESIZE rows
        # from the >2% share-drift rule, so we never run the ledger for them and we
        # clear any stale log they may already carry.
        if fid == "bot13":
            # CRITICAL: diff the REAL accounting positions, not display_positions
            # (which re-show today's already-closed holdings and would create phantom
            # BUY/SELL rows). Track real positions in a separate "_real_positions" key.
            _prev_real = (fund.get("value") or {}).get("_real_positions")
            if _prev_real is None:
                _prev_real = (fund.get("value") or {}).get("positions") or []
            _cur_real = enriched   # true positions held now ([] after close-out)
            _prev_log = (fund.get("value") or {}).get("trade_log") or []
            # Window-clamped timestamp: a SELL must never be stamped outside 9am-9pm ET.
            # If this run executes after close (e.g. a dropped 9pm cron firing after
            # midnight), clamp the log time to the session close (21:00) of the trading day.
            _now_et = et_now()
            _eh2, _em2 = CRYPTO_CFG["session_end"]
            if (_now_et.hour*60+_now_et.minute) >= (_eh2*60+_em2) or _now_et.hour < CRYPTO_CFG["session_start"][0]:
                _td = (b13_prev_strategy or {}).get("day") or today_iso
                _log_ts = f"{_td}T{_eh2:02d}:{_em2:02d}:00"
            else:
                _log_ts = _now_et.isoformat(timespec="seconds")
            # AUTHORITATIVE ledger: record a BUY on every open and a SELL (with realized
            # P&L) on every close, and explicitly close any PRIOR-day book at the day roll
            # so nothing carries across midnight and no trading day is ever blank. Replaces
            # the old snapshot-diff inference (which could silently lose or duplicate trades).
            value["trade_log"], value["_real_positions"] = reconcile_bot13_log(
                _prev_real, _cur_real, _prev_log, today_iso,
                CRYPTO_CFG["session_end"], prices, _log_ts)
            # SHARED banking (LEDGER IS THE ACCOUNT): lives once in bot13_engine.
            if not _cur_real:
                value = bot13_bank_flat_day(value, today_iso, b13_day_open, sc)
        else:
            value["trade_log"] = []

        # -- DATA-INTEGRITY RECONCILIATION (loud WARN; never silently pass bad math) --
        # The platform is a multi-year race; a silent accounting drift corrupts the
        # standings. Re-derive the key relationships and warn if any disagree beyond a
        # small epsilon. These are non-fatal (we still write) but surface in the
        # Actions log so bad data is caught immediately, and audit_integrity.py asserts
        # the same checks against the live API.
        try:
            _v = value
            _sc = float(sc or 0)
            _tot = float(_v.get("total") or 0)
            _pv  = float(_v.get("pos_val") or 0)
            _csh = float(_v.get("cash") or 0)
            _pp  = float(_v.get("pnl_pct") or 0)
            _eps = max(1.0, _tot * 0.01)  # $1 or 1% tolerance
            if abs(_tot - (_pv + _csh)) > _eps:
                print(f"  [INTEGRITY WARN] {fid}: total {_tot:.2f} != pos_val {_pv:.2f} + cash {_csh:.2f}")
            if _sc > 0:
                _calc_pp = (_tot - _sc) / _sc * 100
                if abs(_calc_pp - _pp) > 0.5:
                    print(f"  [INTEGRITY WARN] {fid}: pnl_pct {_pp:.2f} != calc {_calc_pp:.2f} (total {_tot:.2f} vs sc {_sc:.2f})")
            if _tot <= 0:
                print(f"  [INTEGRITY WARN] {fid}: total is {_tot:.2f} (<=0) -- should never happen in a live race")
        except Exception as _ig_err:
            print(f"  [INTEGRITY WARN] {fid}: reconciliation check error: {_ig_err}")

        funds_out[fid] = {
            "id":               fid,
            "name":             fund.get("name"),
            "color":            fund.get("color"),
            "icon":             fund.get("icon"),
            "tagline":          fund.get("tagline"),
            "inception":        fund.get("inception"),
            "starting_capital": sc,
            "value":            value,
            "current_strategy": strategy,
            "top10":            fund.get("top10"),
            "per_top_dollars":  fund.get("per_top_dollars"),
            "per_rest_dollars": fund.get("per_rest_dollars"),
        }

    # -- Snapshots ---------------------------------------------------------------
    today_snap = {"date": today_iso}
    for fid in FUND_ORDER:
        if fid in funds_out:
            today_snap[fid] = funds_out[fid]["value"]["total"]
    snapshots = [s for s in snapshots if s.get("date") != today_iso]
    snapshots = [s for s in snapshots if s.get("date", "") <= today_iso]
    snapshots.append(today_snap)
    snapshots.sort(key=lambda s: s.get("date", ""))
    snapshots = snapshots[-90:]

    # -- Leaderboards ----------------------------------------------------------
    week_start = today - dt.timedelta(days=today.weekday())
    week_cands = [s for s in snapshots if s.get("date", "") <= week_start.isoformat()]
    week_snap  = week_cands[-1] if week_cands else None

    wk_lb, all_lb = [], []
    for fid in FUND_ORDER:
        if fid not in funds_out:
            continue
        v  = funds_out[fid]["value"]
        sc = funds_out[fid]["starting_capital"]
        sv = (week_snap or {}).get(fid, sc)
        wp  = v["total"] - sv
        wpc = (v["total"] / sv - 1) * 100 if sv else 0
        wk_lb.append({"fund": fid, "week_pnl": round(wp,2), "week_pct": round(wpc,2), "week_grade": grade(wpc)})
        all_lb.append({"fund": fid, "all_pnl": v["pnl"], "all_pct": v["pnl_pct"],
                        "overall_grade": grade_overall(v["pnl_pct"], funds_out[fid].get("inception", today_iso), today)})
    wk_lb.sort(key=lambda r: -r["week_pct"])
    all_lb.sort(key=lambda r: -r["all_pct"])

    # -- Build state payload ---------------------------------------------------
    state_data = {
        "starting_capital": sc_global,
        "last_refresh":     now_iso,
        "snapshots":        snapshots,
        "funds":            funds_out,
        "leaderboards":     {"week": wk_lb, "all": all_lb},
        # ONE CLOCK: stored via the shared helper so all 3 engines stay identical.
        "day_boundary":     day_boundary_payload(prices, today_iso),
    }
    STATE_FILE.write_text(json.dumps({"data": state_data}, indent=2))
    print(f"[bitbot13] state -- {len(funds_out)} funds, {len(snapshots)} snapshots")
    push_to_api("state", state_data, secrets)

    # -- Signals ---------------------------------------------------------------
    signals = generate_signals(prices, prev_closes)
    signals_data = signals
    (DATA_DIR / "signals.json").write_text(json.dumps({"data": signals_data}, indent=2))
    n_sig = len(signals["recommendations"])
    print(f"[bitbot13] signals -- {n_sig} signals")
    push_to_api("signals", signals_data, secrets)

    # -- News: owned EXCLUSIVELY by refresh_news.py (Google News RSS, every 4h). The old
    # per-engine NewsAPI fetch/push was REMOVED 2026-07-04: NewsAPI's free tier rate-limits to
    # 0, and this ran every refresh with NO skip-guard, so it kept OVERWRITING the good RSS feed
    # with empty (worst on bitbot13/crypto, which refreshes 24/7 -> news went blank). Do NOT
    # re-add a news push here. refresh_news.py owns the feed and skips pushing on a 0-item fetch.

    # -- Reports (placeholder -- keeps API consistent) --------------------------
    push_to_api("reports", {"reports": [], "generated_at": now_iso}, secrets)

    # -- Portfolio performance snapshots ----------------------------------------
    # -- Member portfolio simulations ------------------------------------------
    print("[bitbot13] running member portfolio simulations...")
    refresh_portfolios.run("bitbot13", prices, prev_closes, intraday_data, secrets)

    # -- Portfolio snapshots ---------------------------------------------------
    trigger_portfolio_snapshots(secrets)

    print("[bitbot13] refresh complete.")


if __name__ == "__main__":
    main()
