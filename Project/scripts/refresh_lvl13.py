#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
refresh_wallstbots.py  (v2 — enhanced strategy engine)
=======================================================
Fetches live prices + 90-day history for the 55-stock universe.
Runs three bot strategy engines:
  - BOT13  : Precision Intraday Momentum (3 runs/day: open, midday, close)
  - ORACLE : Adaptive Weekly Momentum    (recomputes every Monday)
  - WIZARD : Quality Monthly Momentum    (recomputes every 1st trading day)
  - EQUALIZER / TITAN : baselines — mark-to-market only

Auto-run via GitHub Actions; manual run also supported:
  python Project/scripts/refresh_wallstbots.py [--push]

Dependencies: pip install yfinance requests
"""

import argparse
import datetime as dt
import json
import os
import statistics
import subprocess
import sys
from pathlib import Path

# ── Bot13 unified engine ─────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from bot13_engine import (
    run_bot13_equity, check_drawdown,
    EQUITY_CFG,
    grade, grade_overall, et_now, window_open as _engine_window_open,
    session_phase as _engine_session_phase, enrich_position as _engine_enrich,
)

try:
    import yfinance as yf
except ImportError:
    yf = None

try:
    import requests as _requests
except ImportError:
    _requests = None

# ── Paths ───────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).resolve().parents[2]
SECRETS    = ROOT / "Project" / "config" / "secrets.json"
DATA_DIR   = ROOT / "Frontends" / "lvl13.tech" / "data"
STATE_FILE = DATA_DIR / "state.json"

# ── Universe ────────────────────────────────────────────────────────────────────
UNIVERSE = [
    # AI Infrastructure & Semiconductors
    "NVDA","AMD","INTC","ARM","ALAB","MRVL","AVGO","QCOM","SMCI","CRDO",
    # AI Software & Cloud
    "MSFT","GOOGL","META","AMZN","CRM","PLTR","AI","BBAI","SOUN","ORCL",
    # Quantum Computing
    "IONQ","RGTI","QBTS","QUBT","QTUM",
    # AI-Powered Tech & Cybersecurity
    "AAPL","TSLA","RBRK","NOW","SNOW","DDOG","NET","ZS","OKTA","PATH",
    # Next-Gen Hardware & Space
    "ACHR","JOBY","RKLB","ASTR","LUNR",
    # AI Biotech & Health
    "NVTS","RXRX","GRAL","SMMT","BLUE",
]

YF_OVERRIDE = {}
YF_TO_STATE = {}

SECTORS = {
    "NVDA":"AI SEMIS","AMD":"AI SEMIS","INTC":"AI SEMIS","ARM":"AI SEMIS",
    "ALAB":"AI SEMIS","MRVL":"AI SEMIS","AVGO":"AI SEMIS","QCOM":"AI SEMIS",
    "SMCI":"AI SEMIS","CRDO":"AI SEMIS",
    "MSFT":"AI CLOUD","GOOGL":"AI CLOUD","META":"AI CLOUD","AMZN":"AI CLOUD",
    "CRM":"AI CLOUD","PLTR":"AI SOFTWARE","AI":"AI SOFTWARE","BBAI":"AI SOFTWARE",
    "SOUN":"AI SOFTWARE","ORCL":"AI CLOUD",
    "IONQ":"QUANTUM","RGTI":"QUANTUM","QBTS":"QUANTUM","QUBT":"QUANTUM","QTUM":"QUANTUM",
    "AAPL":"AI TECH","TSLA":"AI TECH","RBRK":"CYBER","NOW":"AI CLOUD",
    "SNOW":"AI DATA","DDOG":"AI OPS","NET":"CYBER","ZS":"CYBER","OKTA":"CYBER","PATH":"AI SOFTWARE",
    "ACHR":"NEXT-GEN","JOBY":"NEXT-GEN","RKLB":"NEXT-GEN","ASTR":"NEXT-GEN","LUNR":"NEXT-GEN",
    "NVTS":"AI BIO","RXRX":"AI BIO","GRAL":"AI BIO","SMMT":"AI BIO","BLUE":"AI BIO",
}

FUND_ORDER = ["bot13", "oracle", "wizard", "equalizer", "titan"]

# ── Risk controls ───────────────────────────────────────────────────────────────
# Display value shown to users; internal trigger is EQUITY_CFG["stop_internal"] = 1.35%
STOP_LOSS_PCT = EQUITY_CFG["stop_display"]   # 1.5 — used for Wizard stop-flag check

# ── Helpers ─────────────────────────────────────────────────────────────────────
def load_secrets():
    if SECRETS.exists():
        return json.loads(SECRETS.read_text())
    return {}


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


def sector_weight(picks_list, sector_map):
    """Return dict {sector: total_weight} for a list of pick dicts."""
    sw = {}
    for p in picks_list:
        sec = sector_map.get(p["symbol"], "OTHER")
        sw[sec] = sw.get(sec, 0) + p.get("weight", 0)
    return sw


# ── Live prices ─────────────────────────────────────────────────────────────────
def get_live_prices(symbols):
    """Fetch live price + previous close via yfinance. Returns (prices, prev_closes)."""
    if yf is None:
        print("  [ERROR] yfinance not installed.")
        return {}, {}
    import pandas as pd
    yf_syms     = [YF_OVERRIDE.get(s, s) for s in symbols]
    prices      = {}
    prev_closes = {}
    print(f"  [yfinance] fetching {len(yf_syms)} tickers (live prices)...")
    try:
        raw = yf.download(
            yf_syms,
            period="2d",
            auto_adjust=True,
            progress=False,
        )
        if not raw.empty:
            for yf_sym in yf_syms:
                state_sym = YF_TO_STATE.get(yf_sym, yf_sym)
                try:
                    if isinstance(raw.columns, pd.MultiIndex):
                        closes = raw["Close"][yf_sym].dropna()
                    else:
                        closes = raw["Close"].dropna()
                    if len(closes) >= 1:
                        p  = float(closes.iloc[-1])
                        pc = float(closes.iloc[-2]) if len(closes) >= 2 else p
                        if p > 0:
                            prices[state_sym]      = round(p, 4)
                            prev_closes[state_sym] = round(pc, 4)
                except Exception:
                    pass
    except Exception as e:
        print(f"  [yfinance] download error: {e}")
    print(f"  [yfinance] got {len(prices)}/{len(symbols)} prices")
    return prices, prev_closes


def get_hist_data(symbols):
    """
    Fetch 90-day daily OHLCV history for scoring algorithms.
    Returns {sym: {"closes": [...], "volumes": [...], "highs": [...], "lows": [...]}}
    """
    if yf is None:
        return {}

    print("  [yfinance] fetching 90-day history for strategy scoring...")
    yf_syms = [YF_OVERRIDE.get(s, s) for s in symbols]
    hist = {}
    try:
        import pandas as pd
        raw = yf.download(
            yf_syms,
            period="90d",
            auto_adjust=True,
            progress=False,
        )
        if raw.empty:
            return {}

        # Handle both single and multi-ticker output
        for yf_sym in yf_syms:
            state_sym = YF_TO_STATE.get(yf_sym, yf_sym)
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

    print(f"  [yfinance] history loaded for {len(hist)}/{len(symbols)} symbols")
    return hist


# ── Position enrichment ──────────────────────────────────────────────────────────
def enrich_position(pos, prices, prev_closes):
    sym        = pos["symbol"]
    shares     = float(pos.get("shares") or 0)
    entry      = float(pos.get("entry_price") or pos.get("entry") or 0)
    cost_basis = shares * entry  # always recompute; stored cost_basis may be stale after inception reset
    price      = prices.get(sym, entry)
    prev       = prev_closes.get(sym, price)
    value      = shares * price
    pnl        = value - cost_basis
    pnl_pct    = (price / entry - 1) * 100 if entry > 0 else 0
    day_pnl    = shares * (price - prev)
    day_pct    = (price / prev - 1) * 100 if prev > 0 else 0
    result = {
        "symbol":        sym,
        "shares":        round(shares, 6),
        "entry_price":   round(entry, 4),
        "current_price": round(price, 4),
        "cost_basis":    round(cost_basis, 2),
        "price":         round(price, 4),
        "value":         round(value, 2),
        "pnl":           round(pnl, 2),
        "pnl_pct":       round(pnl_pct, 2),
        "day_pnl":       round(day_pnl, 2),
        "day_pct":       round(day_pct, 2),
    }
    # Preserve stop/target if present
    if "stop_pct" in pos:
        result["stop_pct"]   = pos["stop_pct"]
    if "target_pct" in pos:
        result["target_pct"] = pos["target_pct"]
    # Preserve rich receipt fields if already set on this position
    for field in ("entry_time", "stop_triggered", "exit_reason"):
        if field in pos:
            result[field] = pos[field]
    return result


# ── (run_bot13_decision, _append_log removed — now in bot13_engine.py)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  ORACLE — Adaptive Weekly Momentum                                           ║
# ║                                                                              ║
# ║  Philosophy: Identify the 5 strongest names going into the week using        ║
# ║  composite momentum. Concentrate capital — no equal-weight mediocrity.       ║
# ║                                                                              ║
# ║  Scoring (composite):                                                        ║
# ║  - 5d momentum  × 0.40  — immediate price action (most predictive short-term)║
# ║  - 20d momentum × 0.30  — confirms trend, not just a day trade bounce        ║
# ║  - RSI(14)      × 0.20  — avoids overbought names; rewards healthy pullbacks  ║
# ║  - Volume ratio × 0.10  — institutional confirmation (volume > 20d average)  ║
# ║                                                                              ║
# ║  Portfolio rules:                                                            ║
# ║  - Top 5 picks, weighted by score (not equal weight)                        ║
# ║  - Min 12% / Max 35% per position                                           ║
# ║  - Sector cap: no single sector >40% of portfolio                           ║
# ║  - Quality gate: 20d momentum must be positive to qualify                   ║
# ║  - Recomputes every Monday; holds through Friday close                      ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

def run_oracle_decision(prices, prev_closes, hist_data, starting_capital, week_str):
    """Score + select Oracle's weekly top-5 picks."""
    scored = []
    for sym in UNIVERSE:
        p_now = prices.get(sym, 0)
        if p_now <= 0:
            continue
        info = hist_data.get(sym, {})
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

        # RSI — penalize overbought (>75), reward healthy range (50-70)
        rsi = compute_rsi(closes[-15:] + [p_now])
        if rsi > 75:
            rsi_score = -0.5 * (rsi - 75) / 25   # negative pressure above 75
        else:
            rsi_score = (rsi - 50) / 25           # roughly -1 to +1

        # Volume ratio: last 5d avg vs 20d avg
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

    # Select top 5 with sector cap (max 40% of 5 = 2 from same sector)
    picks_raw = []
    sector_count = {}
    for sym, score, ret5, ret20, rsi, vol_r in scored:
        sec = SECTORS.get(sym, "OTHER")
        if sector_count.get(sec, 0) >= 2:
            continue   # sector cap
        picks_raw.append((sym, score, ret5, ret20, rsi, vol_r))
        sector_count[sec] = sector_count.get(sec, 0) + 1
        if len(picks_raw) >= 5:
            break

    if not picks_raw:
        return None, None, None, 0.0

    # Weight by score, clamp 12-35%, renormalize
    total_score = sum(s for _, s, *_ in picks_raw)
    raw_w = [max(0.12, min(0.35, s / total_score)) for _, s, *_ in picks_raw]
    total_rw = sum(raw_w)
    weights = [w / total_rw for w in raw_w]

    oracle_proj = round(sum(w * ret5 for (_, _, ret5, *_), w in zip(picks_raw, weights)), 2)

    positions, picks = [], []
    for i, (sym, score, ret5, ret20, rsi, vol_r) in enumerate(picks_raw):
        w     = weights[i]
        alloc = starting_capital * w
        price = prices.get(sym, 0)
        prev  = prev_closes.get(sym, price)
        shares = alloc / price if price > 0 else 0
        positions.append({
            "symbol":      sym,
            "shares":      round(shares, 6),
            "entry_price": round(price, 4),
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
        f"Top {len(picks)} names by composite momentum. "
        f"Score-weighted (not equal weight). "
        f"Sector cap enforced (max 2 per sector). "
        f"Quality gate: 20d momentum positive required."
    )
    return positions, picks, rationale, oracle_proj


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  WIZARD — Quality Monthly Momentum                                           ║
# ║                                                                              ║
# ║  Philosophy: Patience is the edge. Let quality compounders do the work.      ║
# ║  Hold 8 names for the full month. No trading noise — only the best trend.    ║
# ║                                                                              ║
# ║  Scoring (long-horizon):                                                     ║
# ║  - 20d momentum × 0.35  — intermediate trend confirmation                   ║
# ║  - 60d momentum × 0.35  — broad trend health (avoids dead-cat bounces)      ║
# ║  - Sharpe proxy × 0.20  — risk-adjusted quality (smooth ride preferred)     ║
# ║  - Distance above 50dMA × 0.10 — trend integrity check                      ║
# ║                                                                              ║
# ║  Portfolio rules:                                                            ║
# ║  - 8 positions, quartile-sized (top 2: ~24%, mid 4: ~14%, bottom 2: ~9%)    ║
# ║  - Quality filter: 60d momentum must be positive                            ║
# ║  - Sector cap: max 35% in any single sector                                 ║
# ║  - Intra-month stop: any position down >12% from entry = exit flag          ║
# ║  - Recomputes on the 1st trading day of each month                          ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

def run_wizard_decision(prices, prev_closes, hist_data, starting_capital, month_str):
    """Score + select Wizard's monthly 8-name quality portfolio."""
    scored = []
    for sym in UNIVERSE:
        p_now = prices.get(sym, 0)
        if p_now <= 0:
            continue
        info = hist_data.get(sym, {})
        closes = info.get("closes", [])
        if len(closes) < 61:
            continue

        p20 = closes[-20] if len(closes) >= 20 else closes[0]
        p60 = closes[-60] if len(closes) >= 60 else closes[0]
        ma50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else p_now

        ret20 = (p_now / p20 - 1) * 100 if p20 > 0 else 0
        ret60 = (p_now / p60 - 1) * 100 if p60 > 0 else 0

        # Quality gate: 60d trend must be positive
        if ret60 < 0:
            continue

        # Sharpe proxy over 60d: annualized mean / std of daily returns
        daily_rets = [
            (closes[i] / closes[i - 1] - 1)
            for i in range(max(1, len(closes) - 60), len(closes))
        ]
        if len(daily_rets) >= 10:
            std_daily = statistics.stdev(daily_rets) * 100
            mean_daily = (sum(daily_rets) / len(daily_rets)) * 100
            sharpe_proxy = mean_daily / std_daily if std_daily > 0 else 0
        else:
            sharpe_proxy = 0

        # Distance above 50d MA
        dist_ma50 = (p_now / ma50 - 1) * 100 if ma50 > 0 else 0

        score = (
            ret20         * 0.35 +
            ret60         * 0.35 +
            sharpe_proxy  * 20   * 0.20 +
            dist_ma50              * 0.10
        )
        scored.append((sym, score, ret20, ret60, sharpe_proxy, dist_ma50))

    if not scored:
        return None, None, None, 0.0

    scored.sort(key=lambda x: -x[1])

    # Select up to 8 with sector cap (max 35% of 8 ~ 3 from same sector)
    picks_raw = []
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

    # Quartile sizing: top 25% of names get double weight
    n = len(picks_raw)
    q1_cut = max(1, round(n * 0.25))  # top quartile
    q3_cut = max(q1_cut + 1, round(n * 0.75))  # bottom quartile

    raw_w = []
    for i in range(n):
        if i < q1_cut:
            raw_w.append(3.0)   # top quartile — highest conviction
        elif i < q3_cut:
            raw_w.append(1.8)   # middle
        else:
            raw_w.append(1.0)   # bottom quartile

    total_rw = sum(raw_w)
    weights = [w / total_rw for w in raw_w]

    wizard_proj = round(sum(w * ret20 for (_, _, ret20, *_), w in zip(picks_raw, weights)), 2)

    positions, picks = [], []
    for i, (sym, score, ret20, ret60, sharpe, dist) in enumerate(picks_raw):
        w     = weights[i]
        alloc = starting_capital * w
        price = prices.get(sym, 0)
        shares = alloc / price if price > 0 else 0
        positions.append({
            "symbol":      sym,
            "shares":      round(shares, 6),
            "entry_price": round(price, 4),
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
        f"Top {len(picks)} quality compounders for the month. "
        f"Quartile-weighted (top names get largest allocation). "
        f"60d quality filter applied — no negative long-term trends. "
        f"Sector cap 35%. Stop flag at -12% intra-month."
    )
    return positions, picks, rationale, wizard_proj


# ── Signals ──────────────────────────────────────────────────────────────────────
def generate_signals(prices, prev_closes, hist_data):
    """
    Enhanced signal generator — combines day momentum with trend context.
    Strong signals require both day move AND multi-day trend alignment.
    """
    today_iso = dt.date.today().isoformat()
    recs    = []
    summary = {"STRONG BUY": 0, "BUY": 0, "HOLD": 0, "SELL": 0, "STRONG SELL": 0}

    for sym in UNIVERSE:
        p  = prices.get(sym, 0)
        pc = prev_closes.get(sym, p)
        if not p:
            continue
        pct = (p / pc - 1) * 100 if pc > 0 else 0

        # Trend context from history
        info   = hist_data.get(sym, {})
        closes = info.get("closes", [])
        trend_positive = True
        if len(closes) >= 5:
            p5 = closes[-5]
            trend_positive = p > p5   # above 5d ago = uptrend

        # Signal with trend confirmation
        if pct >= 3.0 and trend_positive:
            signal = "STRONG BUY";  reason = f"Up {pct:+.2f}% with uptrend — strong confirmed momentum."
        elif pct >= 1.0 and trend_positive:
            signal = "BUY";         reason = f"Up {pct:+.2f}% with trend support — positive momentum."
        elif pct >= 1.0 and not trend_positive:
            signal = "HOLD";        reason = f"Up {pct:+.2f}% but against 5d trend — wait for confirmation."
        elif pct <= -3.0:
            signal = "STRONG SELL"; reason = f"Down {pct:+.2f}% — sharp decline, avoid."
        elif pct <= -1.0:
            signal = "SELL";        reason = f"Down {pct:+.2f}% — negative momentum."
        else:
            signal = "HOLD";        reason = f"Flat {pct:+.2f}% — no clear edge today."

        summary[signal] += 1
        recs.append({
            "symbol":     sym,
            "action":     signal,
            "confidence": round(min(abs(pct) / 5.0, 1.0), 2),
            "reason":     reason,
            "price":      round(p, 2),
            "upside_pct": round(pct, 2),
            "sector":     SECTORS.get(sym, ""),
            "date":       today_iso,
        })

    recs.sort(key=lambda r: -abs(r["upside_pct"]))
    return {
        "recommendations": recs,
        "summary":         summary,
        "generated_at":    dt.datetime.now().isoformat(timespec="seconds"),
    }


# ── News ─────────────────────────────────────────────────────────────────────────
# wallstbots is STOCK-MARKET ONLY. We restrict to financial publications and
# reject any article that mentions crypto, NFT, blockchain, or web3 — per spec.

# Per-sector queries are focused on the names actually in our stock universe.
SECTOR_QUERIES = {
    "AI & Quantum": '("artificial intelligence" OR "AI chip" OR "quantum computing" OR Nvidia OR AMD OR Anthropic OR OpenAI OR Palantir OR IonQ OR Rigetti OR "AI stocks")',
    "Biotech":      '(biotech OR mRNA OR CRISPR OR "gene therapy" OR "FDA approval" OR Moderna OR BioNTech OR Vertex OR Regeneron OR "drug trial")',
    "Energy":       '("oil prices" OR LNG OR renewables OR "energy stocks" OR Exxon OR Chevron OR ConocoPhillips OR "First Solar" OR "Saudi Aramco")',
    "Defense":      '(defense OR Lockheed OR Raytheon OR "Northrop Grumman" OR "L3Harris" OR "General Dynamics" OR "defense contractor" OR hypersonic)',
    "Finance":      '(JPMorgan OR Goldman OR "Bank of America" OR Wells Fargo OR Visa OR Mastercard OR "Federal Reserve" OR "earnings report" OR "stock market")',
    "Tech & Comms": '(Apple OR Microsoft OR Amazon OR Alphabet OR Meta OR "tech earnings" OR Tesla OR Netflix OR Salesforce)',
    "Industrials":  '(Boeing OR Caterpillar OR "General Electric" OR "Honeywell" OR "Lockheed" OR Deere OR "industrial stocks")',
}

# Whitelist of trusted financial publications. NewsAPI accepts up to 20 comma-separated domains.
WALLSTBOTS_DOMAINS = ",".join([
    "reuters.com", "bloomberg.com", "wsj.com", "cnbc.com", "marketwatch.com",
    "finance.yahoo.com", "seekingalpha.com", "barrons.com", "ft.com",
    "investors.com", "fool.com", "thestreet.com", "businessinsider.com",
    "forbes.com", "morningstar.com",
])

# Drop any article whose title contains a crypto term — these slip in even with
# clean queries (e.g., "AI chip news ... bitcoin mining"). wallstbots is stocks-only.
CRYPTO_BLOCK_TERMS = (
    "bitcoin", "btc", "ethereum", "eth", "crypto", "cryptocurrenc",
    "nft", "blockchain", "web3", "altcoin", "defi", "stablecoin",
    "binance", "coinbase", "tether", "ripple", "solana", "dogecoin",
)

def _has_blocked_term(text, terms):
    """Case-insensitive substring check for any blocked term."""
    if not text:
        return False
    t = text.lower()
    return any(term in t for term in terms)

def fetch_news(api_key):
    """Fetch STOCK-MARKET-ONLY news from NewsAPI.org, filtered to trusted financial sources."""
    if _requests is None:
        print("  [news] requests not available — skipping")
        return []
    if not api_key:
        print("  [news] no NewsAPI key — skipping")
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
                    "domains":   WALLSTBOTS_DOMAINS,  # restrict to financial outlets
                    "apiKey":    api_key,
                },
                timeout=15,
            )
            if r.status_code == 200:
                data = r.json()
                count = 0
                skipped_crypto = 0
                for a in data.get("articles", []):
                    title       = (a.get("title") or "").split(" - ")[0].strip()
                    description = a.get("description") or ""
                    key         = title[:80].lower()
                    if not title or key in seen or "[Removed]" in title:
                        continue
                    # Exclude crypto-tinged articles — wallstbots is stocks-only
                    if _has_blocked_term(title, CRYPTO_BLOCK_TERMS) or _has_blocked_term(description, CRYPTO_BLOCK_TERMS):
                        skipped_crypto += 1
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
                if skipped_crypto:
                    msg += f" ({skipped_crypto} crypto-filtered)"
                print(msg)
            else:
                print(f"  [news] {sector} HTTP {r.status_code}: {r.text[:120]}")
        except Exception as e:
            print(f"  [news] {sector} error: {e}")

    all_items.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    all_items = all_items[:30]
    print(f"  [news] fetched {len(all_items)} total stock-market articles")
    return all_items


BACKEND_URL = "https://wallstbots-backend-868128114349.us-east1.run.app"

def push_to_api(data_type, data, secrets):
    """Push any data_type (state/signals/news/reports) to the backend tracker API."""
    if _requests is None:
        return
    api_url      = secrets.get("api_url") or os.environ.get("TRACKER_API_URL", BACKEND_URL)
    internal_key = secrets.get("internal_api_key") or os.environ.get("INTERNAL_API_KEY", "")
    if not internal_key:
        print(f"  [push:{data_type}] no INTERNAL_API_KEY — skipping")
        return
    try:
        r = _requests.post(
            f"{api_url}/internal/tracker/push",
            json={"platform": "lvl13", "data_type": data_type, "data": data},
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
    """Tell the backend to compute per-portfolio daily performance snapshots."""
    if _requests is None:
        return
    api_url      = secrets.get("api_url") or os.environ.get("TRACKER_API_URL", BACKEND_URL)
    internal_key = secrets.get("internal_api_key") or os.environ.get("INTERNAL_API_KEY", "")
    if not internal_key:
        print("  [snapshots] no INTERNAL_API_KEY — skipping portfolio snapshots")
        return
    try:
        r = _requests.post(
            f"{api_url}/internal/portfolio-fund-snapshots/refresh",
            json={"platform": "lvl13"},
            headers={"x-internal-key": internal_key},
            timeout=30,
        )
        if r.status_code == 200:
            result = r.json()
            print(f"  [snapshots] OK — {result.get('portfolios_updated', 0)} portfolios updated, "
                  f"{result.get('prices_available', 0)} prices used")
        else:
            print(f"  [snapshots] HTTP {r.status_code}: {r.text[:120]}")
    except Exception as e:
        print(f"  [snapshots] error: {e}")


# ── Git push ──────────────────────────────────────────────────────────────────────
def git_push(msg):
    git_root = Path(__file__).resolve().parents[2]
    try:
        subprocess.run(["git", "-C", str(git_root), "add",
                        "Frontends/lvl13.tech/data/"], check=True)
        subprocess.run(["git", "-C", str(git_root), "commit",
                        "-m", f"auto: {msg} [{dt.datetime.now().strftime('%Y-%m-%d %H:%M')}]"],
                       check=True)
        subprocess.run(["git", "-C", str(git_root), "push"], check=True)
        print("[git] pushed to GitHub OK")
    except subprocess.CalledProcessError as e:
        print(f"[git] push failed: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--push", action="store_true")
    args = parser.parse_args()

    secrets     = load_secrets()
    newsapi_key = secrets.get("newsapi_key") or os.environ.get("NEWSAPI_KEY", "")

    print("[wallstbots] loading state.json...")
    raw        = json.loads(STATE_FILE.read_text())
    state_data = raw.get("data", raw)
    funds      = state_data.get("funds", {})
    snapshots  = list(state_data.get("snapshots", []))
    sc_global  = float(state_data.get("starting_capital") or 55000)

    today      = dt.date.today()
    today_iso  = today.isoformat()
    now_iso    = dt.datetime.now().isoformat(timespec="seconds")
    week_str   = today.isocalendar()[0:2].__str__()    # (year, week)
    month_str  = today.strftime("%Y-%m")

    # ── Determine which bots need full recompute ─────────────────────────────
    is_monday       = today.weekday() == 0
    is_month_start  = today.day <= 3   # 1st-3rd trading day = month boundary

    # Force scoring on first run — no positions means never deployed yet
    oracle_needs_seed = not funds.get("oracle", {}).get("value", {}).get("positions")
    wizard_needs_seed = not funds.get("wizard", {}).get("value", {}).get("positions")

    # ── Fetch live prices ────────────────────────────────────────────────────
    need_syms = set(UNIVERSE)
    for fid, fund in funds.items():
        for pos in fund.get("value", {}).get("positions", []):
            s = pos.get("symbol")
            if s:
                need_syms.add(s)

    print(f"[wallstbots] fetching prices for {len(need_syms)} symbols...")
    prices, prev_closes = get_live_prices(sorted(need_syms))
    if not prices:
        print("[wallstbots] WARNING: zero prices returned — positions will not update but continuing.")

    # ── Fetch historical data for strategy scoring ───────────────────────────
    hist_data = get_hist_data(list(need_syms))

    # ── BOT13 decision ───────────────────────────────────────────────────────
    print(f"[lvl13] running BOT13 decision (phase: {_engine_session_phase(EQUITY_CFG)})...")
    prev_b13_strategy = funds.get("bot13", {}).get("current_strategy")
    # Use the fund's current running total so gains compound day-over-day
    prev_b13_total = float(funds.get("bot13", {}).get("value", {}).get("total") or sc_global)
    # day_open = value at start of today; persists across intraday refreshes so day_pnl is cumulative
    b13_day_open = (
        float(funds.get("bot13", {}).get("value", {}).get("day_open") or prev_b13_total)
        if (prev_b13_strategy or {}).get("day") == today_iso
        else prev_b13_total   # new day: yesterday's close becomes today's open
    )
    # Respect inception date: do not trade before bot13's inception day
    b13_inception    = funds.get("bot13", {}).get("inception", today_iso)
    stored_positions = funds.get("bot13", {}).get("value", {}).get("positions", [])

    _stop_internal = EQUITY_CFG["stop_internal"]   # 1.35% — internal trigger (vs 1.5% display)

    # Account-level daily drawdown kill switch
    drawdown_hit = check_drawdown(EQUITY_CFG, b13_day_open, stored_positions, prices)

    # Check if any held position has triggered stop-loss (>_stop_internal% down from entry)
    stops_triggered = any(
        float(p.get("entry_price") or 0) > 0 and
        (float(prices.get(p["symbol"], float(p.get("entry_price", 0)))) /
         float(p.get("entry_price", 1)) - 1) * 100 < -_stop_internal
        for p in stored_positions if p.get("symbol")
    )

    # Guard: if positions already exist for today AND no stops hit, just re-price
    same_day_trade = (
        (prev_b13_strategy or {}).get("day") == today_iso
        and (prev_b13_strategy or {}).get("decision") == "TRADE"
        and bool(stored_positions)
        and not stops_triggered
    )
    if b13_inception > today_iso:
        b13_decision, b13_positions, b13_picks, b13_rationale, b13_log, b13_proj = "HOLD", [], [], "Pre-inception hold", [], 0.0
        prev_b13_total = sc_global  # reset to SC so tomorrow starts clean
        print(f"  BOT13: HOLD (pre-inception, starts {b13_inception})")
    elif drawdown_hit:
        b13_decision  = "HOLD"
        b13_positions = []
        b13_picks     = []
        b13_rationale = (f"Account drawdown kill switch: portfolio has fallen >{EQUITY_CFG['max_daily_drawdown']*100:.1f}% "
                         f"from today's open (${b13_day_open:,.2f}). No new entries until tomorrow.")
        b13_log       = (prev_b13_strategy or {}).get("session_log", [])
        b13_proj      = 0.0
        print(f"  BOT13: HOLD (daily drawdown limit hit — protecting capital)")
    elif stops_triggered:
        # Stop-loss triggered — mark stopped positions, then re-enter fresh picks
        now_exit = __import__("datetime").datetime.utcnow().isoformat(timespec="seconds") + "Z"
        for p in stored_positions:
            sym = p.get("symbol")
            if sym:
                cur = prices.get(sym, float(p.get("entry_price", 0)))
                ep  = float(p.get("entry_price") or 0)
                if ep > 0 and (cur / ep - 1) * 100 < -_stop_internal:
                    p["stop_triggered"] = True
                    p["exit_reason"]    = f"stop_loss (>{STOP_LOSS_PCT}% loss)"
                    p["exit_time"]      = now_exit
        print(f"  BOT13: stop-loss triggered — closing stopped positions, re-picking...")
        b13_decision, b13_positions, b13_picks, b13_rationale, b13_log, b13_proj = run_bot13_equity(
            EQUITY_CFG, UNIVERSE, prices, prev_closes, hist_data, b13_day_open, today_iso, prev_b13_strategy
        )
        print(f"  BOT13: re-entered with {len(b13_picks)} new picks after stop-loss")
    elif same_day_trade:
        # Re-use existing positions — only re-price, don't resize
        b13_positions = stored_positions
        b13_decision  = "TRADE"
        b13_picks     = (prev_b13_strategy or {}).get("picks", [])
        b13_rationale = (prev_b13_strategy or {}).get("rationale", "")
        b13_log       = (prev_b13_strategy or {}).get("session_log", [])
        b13_proj      = float((prev_b13_strategy or {}).get("projected_return", 0.0))
        print(f"  BOT13: same-day re-price ({len(b13_positions)} existing positions)")
    else:
        b13_decision, b13_positions, b13_picks, b13_rationale, b13_log, b13_proj = run_bot13_equity(
            EQUITY_CFG, UNIVERSE, prices, prev_closes, hist_data, b13_day_open, today_iso, prev_b13_strategy
        )
        print(f"  BOT13: {b13_decision} ({len(b13_picks)} picks)")

    # ── ORACLE decision (Monday only, otherwise keep existing positions) ──────
    oracle_new_positions = None
    oracle_new_picks     = None
    oracle_new_rationale = None
    oracle_new_proj      = 0.0
    if (is_monday or oracle_needs_seed) and hist_data:
        print(f"[wallstbots] {'Monday' if is_monday else 'first run'} — running ORACLE recompute...")
        oracle_new_positions, oracle_new_picks, oracle_new_rationale, oracle_new_proj = run_oracle_decision(
            prices, prev_closes, hist_data, sc_global, week_str
        )
        if oracle_new_picks:
            print(f"  ORACLE: {len(oracle_new_picks)} new picks")
        else:
            print("  ORACLE: scoring returned no picks — keeping existing")

    # ── WIZARD decision (1st trading days only) ───────────────────────────────
    wizard_new_positions = None
    wizard_new_picks     = None
    wizard_new_rationale = None
    wizard_new_proj      = 0.0
    if (is_month_start or wizard_needs_seed) and hist_data:
        print(f"[wallstbots] {'Month start' if is_month_start else 'first run'} ({today_iso}) — running WIZARD recompute...")
        wizard_new_positions, wizard_new_picks, wizard_new_rationale, wizard_new_proj = run_wizard_decision(
            prices, prev_closes, hist_data, sc_global, month_str
        )
        if wizard_new_picks:
            print(f"  WIZARD: {len(wizard_new_picks)} new picks")
        else:
            print("  WIZARD: scoring returned no picks — keeping existing")

    # ── Enrich all fund positions ─────────────────────────────────────────────
    print("[wallstbots] enriching positions...")
    funds_out = {}

    for fid in FUND_ORDER:
        fund = funds.get(fid)
        if not fund:
            continue
        sc = float(fund.get("starting_capital") or sc_global)

        if fid == "bot13":
            if b13_decision == "TRADE":
                enriched  = [enrich_position(p, prices, prev_closes) for p in b13_positions]
                sum_pnl   = sum(p["pnl"]   for p in enriched)  # receipts: sum of position P&L
                pos_val   = sum(p["value"] for p in enriched)
                total     = b13_day_open + sum_pnl              # day_open + receipts = true total
                cash      = 0.0
            else:
                # HOLD/CASH: no positions — empty holdings, today's P&L = 0
                enriched  = []
                pos_val   = 0.0
                total     = b13_day_open
                cash      = b13_day_open

            pnl           = total - sc                              # total gain since inception
            pnl_pct       = (pnl / sc * 100) if sc else 0
            day_pnl_total = total - b13_day_open                   # full day's accumulated gain
            day_pct       = (day_pnl_total / b13_day_open * 100) if b13_day_open else 0

            # holding_cash: true whenever bot13 is not actively in positions
            window_open  = _engine_window_open(EQUITY_CFG)
            holding_cash = (b13_decision != "TRADE") or not window_open

            value    = {"total": round(total,2), "cash": round(cash,2), "pos_val": round(pos_val,2),
                        "pnl": round(pnl,2), "pnl_pct": round(pnl_pct,2),
                        "day_pnl": round(day_pnl_total,2), "day_pct": round(day_pct,2),
                        "day_open": round(b13_day_open,2), "holding_cash": holding_cash,
                        "window_open":     window_open,
                        "session_open_et": "9:30",
                        "session_close_et": "16:00",
                        "positions": enriched}
            strategy = {
                "day":              today_iso,
                "decision":         b13_decision,
                "rationale":        b13_rationale,
                "picks":            b13_picks,
                "stop_pct":         -1.5,
                "target_pct":       3.0,
                "session_log":      b13_log,
                "projected_return": round(b13_proj, 2),
            }

        elif fid == "oracle":
            if oracle_new_positions:
                raw_pos  = oracle_new_positions
                strategy = {
                    "week":             today_iso,
                    "decision":         "TRADE",
                    "rationale":        oracle_new_rationale,
                    "picks":            oracle_new_picks,
                    "projected_return": round(oracle_new_proj, 2),
                }
                # Update stored positions with new entries
                fund_copy = dict(fund)
                fund_copy["value"] = dict(fund.get("value", {}))
                fund_copy["value"]["positions"] = raw_pos
                fund = fund_copy
            else:
                strategy = fund.get("current_strategy")

            raw_pos  = fund.get("value", {}).get("positions", [])
            # On inception day, reset entry prices to prev_close so pnl starts at 0
            if fund.get("inception") == today_iso:
                raw_pos = [{**p, "entry_price": prev_closes.get(p["symbol"], p.get("entry_price", 0))}
                           if prev_closes.get(p["symbol"], 0) > 0 else p for p in raw_pos]
            enriched = [enrich_position(p, prices, prev_closes) for p in raw_pos]
            pos_val  = sum(p["value"]   for p in enriched)
            pnl      = sum(p["pnl"]     for p in enriched)   # always matches table sum
            total    = sc + pnl                               # true economic value
            cash     = max(0.0, total - pos_val)              # undeployed capital, never negative
            pnl_pct  = (pnl / sc * 100) if sc else 0
            day_pnl  = sum(p["day_pnl"] for p in enriched)
            day_pct  = (day_pnl / (total - day_pnl)) * 100 if (total - day_pnl) else 0

            # holding_cash for oracle: true on weekends (no active management until Monday)
            oracle_holding_cash = et_now().weekday() >= 5  # Sat=5, Sun=6

            value    = {"total": round(total,2), "cash": round(cash,2), "pos_val": round(pos_val,2),
                        "pnl": round(pnl,2), "pnl_pct": round(pnl_pct,2),
                        "day_pnl": round(day_pnl,2), "day_pct": round(day_pct,2),
                        "holding_cash": oracle_holding_cash, "positions": enriched}

        elif fid == "wizard":
            if wizard_new_positions:
                raw_pos  = wizard_new_positions
                strategy = {
                    "month":            month_str,
                    "decision":         "TRADE",
                    "rationale":        wizard_new_rationale,
                    "picks":            wizard_new_picks,
                    "projected_return": round(wizard_new_proj, 2),
                }
                fund_copy = dict(fund)
                fund_copy["value"] = dict(fund.get("value", {}))
                fund_copy["value"]["positions"] = raw_pos
                fund = fund_copy
            else:
                # Intra-month: check for -12% stop flags
                strategy = fund.get("current_strategy")

            raw_pos  = fund.get("value", {}).get("positions", [])
            # On inception day, reset entry prices to prev_close so pnl starts at 0
            if fund.get("inception") == today_iso:
                raw_pos = [{**p, "entry_price": prev_closes.get(p["symbol"], p.get("entry_price", 0))}
                           if prev_closes.get(p["symbol"], 0) > 0 else p for p in raw_pos]
            enriched = []
            for p in raw_pos:
                ep = enrich_position(p, prices, prev_closes)
                # Flag any position beyond stop-loss threshold
                if ep["pnl_pct"] < -STOP_LOSS_PCT:
                    ep["stop_triggered"] = True
                enriched.append(ep)
            pos_val  = sum(p["value"]   for p in enriched)
            pnl      = sum(p["pnl"]     for p in enriched)   # always matches table sum
            total    = sc + pnl                               # true economic value
            cash     = max(0.0, total - pos_val)              # undeployed capital, never negative
            pnl_pct  = (pnl / sc * 100) if sc else 0
            day_pnl  = sum(p["day_pnl"] for p in enriched)
            day_pct  = (day_pnl / (total - day_pnl)) * 100 if (total - day_pnl) else 0
            value    = {"total": round(total,2), "cash": round(cash,2), "pos_val": round(pos_val,2),
                        "pnl": round(pnl,2), "pnl_pct": round(pnl_pct,2),
                        "day_pnl": round(day_pnl,2), "day_pct": round(day_pct,2), "positions": enriched}

        else:
            # Equalizer + Titan — mark-to-market; auto-seed on first run
            raw_pos  = fund.get("value", {}).get("positions", [])

            if not raw_pos and fid == "equalizer" and prices:
                per_stock = sc / len(UNIVERSE)
                for sym in UNIVERSE:
                    price = prev_closes.get(sym) or prices.get(sym, 0)
                    if price > 0:
                        raw_pos.append({
                            "symbol":      sym,
                            "shares":      round(per_stock / price, 6),
                            "entry_price": round(price, 4),
                            "cost_basis":  round(per_stock, 2),
                        })
                print(f"  EQUALIZER: seeded {len(raw_pos)} positions at ${per_stock:.0f}/stock")

            elif not raw_pos and fid == "titan" and prices:
                top10    = fund.get("top10") or []
                per_top  = float(fund.get("per_top_dollars") or 0)
                per_rest = float(fund.get("per_rest_dollars") or 0)
                rest     = [s for s in UNIVERSE if s not in top10]
                for sym in top10:
                    price = prev_closes.get(sym) or prices.get(sym, 0)
                    if price > 0 and per_top > 0:
                        raw_pos.append({"symbol": sym, "shares": round(per_top / price, 6),
                                        "entry_price": round(price, 4), "cost_basis": round(per_top, 2)})
                for sym in rest:
                    price = prev_closes.get(sym) or prices.get(sym, 0)
                    if price > 0 and per_rest > 0:
                        raw_pos.append({"symbol": sym, "shares": round(per_rest / price, 6),
                                        "entry_price": round(price, 4), "cost_basis": round(per_rest, 2)})
                print(f"  TITAN: seeded {len(raw_pos)} positions (top10 ${per_top:.0f} / rest ${per_rest:.0f})")

            # On inception day, reset entry prices to prev_close so pnl starts at 0
            if fund.get("inception") == today_iso:
                raw_pos = [{**p, "entry_price": prev_closes.get(p["symbol"], p.get("entry_price", 0))}
                           if prev_closes.get(p["symbol"], 0) > 0 else p for p in raw_pos]
            enriched = [enrich_position(p, prices, prev_closes) for p in raw_pos]
            pos_val  = sum(p["value"]   for p in enriched)
            pnl      = sum(p["pnl"]     for p in enriched)   # always matches table sum
            total    = sc + pnl                               # true economic value
            cash     = max(0.0, total - pos_val)              # undeployed capital, never negative
            pnl_pct  = (pnl / sc * 100) if sc else 0
            day_pnl  = sum(p["day_pnl"] for p in enriched)
            day_pct  = (day_pnl / (total - day_pnl)) * 100 if (total - day_pnl) else 0
            value    = {"total": round(total,2), "cash": round(cash,2), "pos_val": round(pos_val,2),
                        "pnl": round(pnl,2), "pnl_pct": round(pnl_pct,2),
                        "day_pnl": round(day_pnl,2), "day_pct": round(day_pct,2), "positions": enriched}
            strategy = fund.get("current_strategy")

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

    # ── Snapshots ─────────────────────────────────────────────────────────────
    today_snap = {"date": today_iso}
    for fid in FUND_ORDER:
        if fid in funds_out:
            today_snap[fid] = funds_out[fid]["value"]["total"]
    snapshots = [s for s in snapshots if s.get("date") != today_iso]
    snapshots.append(today_snap)
    snapshots.sort(key=lambda s: s.get("date", ""))
    snapshots = snapshots[-90:]

    # ── Leaderboards ──────────────────────────────────────────────────────────
    week_start = today - dt.timedelta(days=today.weekday())
    week_cands = [s for s in snapshots if s.get("date", "") <= week_start.isoformat()]
    week_snap  = week_cands[-1] if week_cands else None

    wk_lb, all_lb = [], []
    for fid in FUND_ORDER:
        if fid not in funds_out:
            continue
        v   = funds_out[fid]["value"]
        sc  = funds_out[fid]["starting_capital"]
        sv  = (week_snap or {}).get(fid, sc)
        wp  = v["total"] - sv
        wpc = (v["total"] / sv - 1) * 100 if sv else 0
        wk_lb.append({"fund": fid, "week_pnl": round(wp,2), "week_pct": round(wpc,2), "week_grade": grade(wpc)})
        all_lb.append({"fund": fid, "all_pnl": v["pnl"], "all_pct": v["pnl_pct"],
                        "overall_grade": grade_overall(v["pnl_pct"], funds_out[fid].get("inception", today_iso), today)})
    wk_lb.sort(key=lambda r: -r["week_pct"])
    all_lb.sort(key=lambda r: -r["all_pct"])


    # ── Build state payload ───────────────────────────────────────────────────
    state_data = {
        "starting_capital": sc_global,
        "last_refresh":     now_iso,
        "snapshots":        snapshots,
        "funds":            funds_out,
        "leaderboards":     {"week": wk_lb, "all": all_lb},
    }
    # Write local file (backup) + push to backend API
    STATE_FILE.write_text(json.dumps({"data": state_data}, indent=2))
    print(f"[wallstbots] state — {len(funds_out)} funds, {len(snapshots)} snapshots")
    push_to_api("state", state_data, secrets)

    # ── Signals ───────────────────────────────────────────────────────────────
    signals = generate_signals(prices, prev_closes, hist_data)
    signals_data = signals
    (DATA_DIR / "signals.json").write_text(json.dumps({"data": signals_data}, indent=2))
    n_sig = len(signals["recommendations"])
    print(f"[wallstbots] signals — {n_sig} signals")
    push_to_api("signals", signals_data, secrets)

    # ── News ──────────────────────────────────────────────────────────────────
    print("[lvl13] fetching news...")
    news_items = fetch_news(newsapi_key)
    news_data = {
        "items":        news_items,
        "sectors":      sorted({it["sector"] for it in news_items}) if news_items else [],
        "generated_at": dt.datetime.utcnow().isoformat() + "Z",
    }
    print(f"[lvl13] news — {len(news_items)} articles")
    push_to_api("news", news_data, secrets)

    # ── Reports (placeholder — keeps API consistent) ──────────────────────────
    push_to_api("reports", {"reports": [], "generated_at": now_iso}, secrets)

    # ── Portfolio performance snapshots ───────────────────────────────────────
    trigger_portfolio_snapshots(secrets)

    # ── Git push (optional — static files as backup) ─────────────────────────
    if args.push:
        git_push("lvl13.tech data refresh")

    print("\n[lvl13] ALL DONE")


if __name__ == "__main__":
    main()