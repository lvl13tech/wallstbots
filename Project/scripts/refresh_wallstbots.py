#!/usr/bin/env python3
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
DATA_DIR   = ROOT / "Frontends" / "wallstbots.tech" / "data"
STATE_FILE = DATA_DIR / "state.json"

# ── Universe ────────────────────────────────────────────────────────────────────
UNIVERSE = [
    "XOM","CVX","COP","FANG","OKLO",
    "LIN","SHW","FCX","APD","ALB",
    "CAT","RTX","HON","GE","ACHR",
    "AMZN","TSLA","HD","IBTA","BIRK",
    "WMT","PG","COST","CART","KR",
    "LLY","JNJ","UNH","GRAL","SMMT",
    "BRK.B","JPM","V","SOFI","AFRM",
    "NVDA","AAPL","MSFT","ARM","ALAB",
    "RBRK","GOOGL","META","NFLX","RDDT",
    "SPOT","NEE","SO","DUK","VST",
    "PLD","WELL","AMT","LINE","EQIX",
]

YF_OVERRIDE = {"BRK.B": "BRK-B"}
YF_TO_STATE = {"BRK-B": "BRK.B"}

SECTORS = {
    "XOM":"ENERGY","CVX":"ENERGY","COP":"ENERGY","FANG":"ENERGY",
    "OKLO":"UTILITIES",
    "LIN":"MATERIALS","SHW":"MATERIALS","FCX":"MATERIALS","APD":"MATERIALS","ALB":"MATERIALS",
    "CAT":"INDUSTRIALS","RTX":"INDUSTRIALS","HON":"INDUSTRIALS","GE":"INDUSTRIALS","ACHR":"INDUSTRIALS",
    "AMZN":"CONSUMER DISCRETIONARY","TSLA":"CONSUMER DISCRETIONARY",
    "HD":"CONSUMER DISCRETIONARY","IBTA":"CONSUMER DISCRETIONARY","BIRK":"CONSUMER DISCRETIONARY",
    "WMT":"CONSUMER STAPLES","PG":"CONSUMER STAPLES","COST":"CONSUMER STAPLES",
    "CART":"CONSUMER STAPLES","KR":"CONSUMER STAPLES",
    "LLY":"HEALTH CARE","JNJ":"HEALTH CARE","UNH":"HEALTH CARE","GRAL":"HEALTH CARE","SMMT":"HEALTH CARE",
    "BRK.B":"FINANCIALS","JPM":"FINANCIALS","V":"FINANCIALS","SOFI":"FINANCIALS","AFRM":"FINANCIALS",
    "NVDA":"IT","AAPL":"IT","MSFT":"IT","ARM":"IT","ALAB":"IT","RBRK":"IT",
    "GOOGL":"COMMUNICATION SERVICES","META":"COMMUNICATION SERVICES",
    "NFLX":"COMMUNICATION SERVICES","RDDT":"COMMUNICATION SERVICES","SPOT":"COMMUNICATION SERVICES",
    "NEE":"UTILITIES","SO":"UTILITIES","DUK":"UTILITIES","VST":"UTILITIES",
    "PLD":"REAL ESTATE","WELL":"REAL ESTATE","AMT":"REAL ESTATE","LINE":"REAL ESTATE","EQIX":"REAL ESTATE",
}

FUND_ORDER = ["bot13", "oracle", "wizard", "equalizer", "titan"]

# ── Helpers ─────────────────────────────────────────────────────────────────────
def load_secrets():
    if SECRETS.exists():
        return json.loads(SECRETS.read_text())
    return {}


def grade(pct):
    if pct >= 5:   return "A+"
    if pct >= 3:   return "A"
    if pct >= 1.5: return "B"
    if pct >= 0:   return "C"
    if pct >= -2:  return "D"
    return "F"


def grade_overall(pct, inception_iso, today):
    try:
        inception = dt.date.fromisoformat(str(inception_iso)[:10])
        weeks = max((today - inception).days / 7, 1)
        return grade(pct / weeks)
    except Exception:
        return grade(pct)


def et_hour():
    """Return current hour in US Eastern time (EDT = UTC-4, EST = UTC-5)."""
    now_utc = dt.datetime.utcnow()
    # Simple DST approximation: EDT (UTC-4) March-Nov, EST (UTC-5) Nov-Mar
    if 3 <= now_utc.month <= 11:
        offset = -4
    else:
        offset = -5
    et = now_utc + dt.timedelta(hours=offset)
    return et.hour, et.minute


def session_phase():
    """Return 'morning' | 'midday' | 'close' based on ET time."""
    h, m = et_hour()
    if h < 11:
        return "morning"
    if h < 14:
        return "midday"
    return "close"


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
    yf_syms     = [YF_OVERRIDE.get(s, s) for s in symbols]
    prices      = {}
    prev_closes = {}
    print(f"  [yfinance] fetching {len(yf_syms)} tickers (live prices)...")
    for yf_sym in yf_syms:
        state_sym = YF_TO_STATE.get(yf_sym, yf_sym)
        try:
            t  = yf.Ticker(yf_sym)
            fi = getattr(t, "fast_info", None) or {}
            p  = float(fi.get("last_price") or 0)
            pc = float(fi.get("previous_close") or 0)
            if p > 0:
                prices[state_sym]      = round(p, 4)
                prev_closes[state_sym] = round(pc if pc > 0 else p, 4)
        except Exception as e:
            print(f"    [warn] {yf_sym}: {e}")
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
    entry      = float(pos.get("entry_price") or 0)
    cost_basis = float(pos.get("cost_basis") or (shares * entry))
    price      = prices.get(sym, entry)
    prev       = prev_closes.get(sym, price)
    value      = shares * price
    pnl        = value - cost_basis
    pnl_pct    = (price / entry - 1) * 100 if entry > 0 else 0
    day_pnl    = shares * (price - prev)
    day_pct    = (price / prev - 1) * 100 if prev > 0 else 0
    result = {
        "symbol":      sym,
        "shares":      round(shares, 6),
        "entry_price": round(entry, 4),
        "cost_basis":  round(cost_basis, 2),
        "price":       round(price, 4),
        "value":       round(value, 2),
        "pnl":         round(pnl, 2),
        "pnl_pct":     round(pnl_pct, 2),
        "day_pnl":     round(day_pnl, 2),
        "day_pct":     round(day_pct, 2),
    }
    # Preserve stop/target if present
    if "stop_pct" in pos:
        result["stop_pct"]   = pos["stop_pct"]
    if "target_pct" in pos:
        result["target_pct"] = pos["target_pct"]
    return result


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  BOT13 — Precision Intraday Momentum                                        ║
# ║                                                                              ║
# ║  Philosophy: Strike fast on confirmed intraday leadership. Only trade when   ║
# ║  conditions are clearly favorable. When in doubt — stay in cash.             ║
# ║                                                                              ║
# ║  Entry Rules:                                                                ║
# ║  - Stock must be up >1.0% from previous close (confirmed strength, not noise)║
# ║  - At least 3 qualifying candidates required (breadth confirmation)          ║
# ║  - Market health check: no more than 33% of universe down >2%               ║
# ║                                                                              ║
# ║  Sizing: Proportional to signal strength — stronger move = larger position   ║
# ║          Min 12% per name, max 33% per name. Top 5 names only.              ║
# ║                                                                              ║
# ║  Risk Management (embedded in each pick):                                   ║
# ║  - Hard stop-loss: -1.5% from entry (protects capital on reversals)         ║
# ║  - Profit target: +3.0% from entry (locks in gains before fade)             ║
# ║                                                                              ║
# ║  Overextension guard: stocks up >8% are heavily penalized in scoring        ║
# ║  (buying into a parabola is how you get caught at the top)                  ║
# ║                                                                              ║
# ║  Cash conditions: <3 qualified names, OR broad selling pressure >33%         ║
# ║  Bot13 never holds overnight — all positions conceptually close at 3:50 PM  ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

def run_bot13_decision(prices, prev_closes, starting_capital, today_iso, prev_strategy=None):
    """
    Compute BOT13's intraday position or cash decision.
    Incorporates session-phase awareness and cumulative session logging.
    """
    phase = session_phase()
    h, mn = et_hour()
    time_label = f"{h}:{mn:02d} {'AM' if h < 12 else 'PM'}"

    # ── Market health check ──────────────────────────────────────────────────
    n_green  = 0  # up >0.5%
    n_red    = 0  # down >2%  (selling pressure signal)
    n_priced = 0
    for sym in UNIVERSE:
        p  = prices.get(sym, 0)
        pc = prev_closes.get(sym, p)
        if p <= 0:
            continue
        n_priced += 1
        pct = (p / pc - 1) * 100 if pc > 0 else 0
        if pct >= 0.5:
            n_green += 1
        if pct <= -2.0:
            n_red += 1

    breadth_pct  = n_green / n_priced if n_priced else 0
    sell_pressure = n_red / n_priced if n_priced else 0

    # Cash condition: broad selling pressure
    if sell_pressure > 0.33:
        log_entry = {
            "time":   time_label,
            "phase":  phase.upper(),
            "action": "CASH — MARKET HEALTH FAIL",
            "detail": (f"{int(sell_pressure*100)}% of universe down >2%. "
                       "Broad selling pressure detected — protecting capital."),
        }
        session_log = _append_log(prev_strategy, today_iso, log_entry)
        return "CASH", [], [], (
            f"CASH — broad selling pressure ({int(sell_pressure*100)}% of stocks down >2%). "
            "No trades today."
        ), session_log

    # ── Score each candidate ─────────────────────────────────────────────────
    scored = []
    for sym in UNIVERSE:
        p  = prices.get(sym, 0)
        pc = prev_closes.get(sym, p)
        if p <= 0 or pc <= 0:
            continue
        day_pct = (p / pc - 1) * 100

        # Must be up >1.0% to qualify
        if day_pct < 1.0:
            continue

        # Signal strength — reward clean momentum, penalize parabolic gaps
        if day_pct > 8.0:
            strength = day_pct * 0.55   # heavily overextended — reversal risk high
        elif day_pct > 5.0:
            strength = day_pct * 0.80   # strong but watch for fade
        else:
            strength = day_pct          # clean momentum zone

        scored.append((sym, day_pct, strength))

    # Need at least 3 to have a tradeable session
    if len(scored) < 3:
        log_entry = {
            "time":   time_label,
            "phase":  phase.upper(),
            "action": "CASH — INSUFFICIENT BREADTH",
            "detail": (f"Only {len(scored)} stock(s) up >1.0%. "
                       "Need minimum 3 qualified names. Sitting out."),
        }
        session_log = _append_log(prev_strategy, today_iso, log_entry)
        return "CASH", [], [], (
            f"CASH — only {len(scored)} stock(s) cleared the 1.0% entry hurdle. "
            "Need at least 3 qualified names for a tradeable session."
        ), session_log

    # Sort by signal strength, cap at 5 picks
    scored.sort(key=lambda x: -x[2])
    top_picks = scored[:5]

    # ── Size proportionally to signal strength ───────────────────────────────
    total_strength = sum(s for _, _, s in top_picks)
    raw_weights = [s / total_strength for _, _, s in top_picks]

    # Clamp 12% min / 33% max, then renormalize
    clamped = [max(0.12, min(0.33, w)) for w in raw_weights]
    total_c = sum(clamped)
    weights = [c / total_c for c in clamped]

    positions, picks = [], []
    for i, (sym, day_pct, strength) in enumerate(top_picks):
        w      = weights[i]
        alloc  = starting_capital * w
        price  = prices.get(sym, 0)
        prev   = prev_closes.get(sym, price)
        shares = alloc / price
        day_pnl = shares * (price - prev)

        if day_pct >= 5.0:
            intensity = "STRONG momentum"
        elif day_pct >= 2.5:
            intensity = "solid momentum"
        else:
            intensity = "emerging momentum"

        positions.append({
            "symbol":      sym,
            "shares":      round(shares, 6),
            "entry_price": round(price, 4),
            "cost_basis":  round(alloc, 2),
            "price":       round(price, 4),
            "value":       round(shares * price, 2),
            "pnl":         0.0,
            "pnl_pct":     0.0,
            "day_pnl":     round(day_pnl, 2),
            "day_pct":     round(day_pct, 2),
            "stop_pct":    -1.5,
            "target_pct":  3.0,
        })
        picks.append({
            "symbol":    sym,
            "weight":    round(w, 4),
            "score":     round(strength * 10, 1),
            "rationale": (f"{sym}: {intensity} +{day_pct:.2f}% — "
                          f"{w*100:.0f}% allocation (${alloc:,.0f}). "
                          f"Stop: -1.5% | Target: +3.0%."),
        })

    # ── Build session log entry ──────────────────────────────────────────────
    pos_summary = ", ".join(
        f"{sym} {day_pct:+.2f}%" for sym, day_pct, _ in top_picks
    )
    breadth_label = f"{n_green}/{n_priced} green"
    if phase == "morning":
        action = f"ENTERED {len(picks)} position{'s' if len(picks) > 1 else ''}"
        detail = (f"{pos_summary}. "
                  f"Breadth: {breadth_label}. "
                  f"Stops at -1.5%, targets at +3.0%. Capital deployed.")
    elif phase == "midday":
        action = "MIDDAY CHECK — positions reviewed"
        detail = (f"Current positions: {pos_summary}. "
                  f"Breadth: {breadth_label}. "
                  "Monitoring for stop/target triggers. "
                  "Any position through -1.5% would be exited immediately.")
    else:
        action = "CLOSE — session complete"
        day_total = sum(p["day_pnl"] for p in positions)
        detail = (f"Final session positions: {pos_summary}. "
                  f"Day P&L: ${day_total:+,.0f}. "
                  f"Breadth: {breadth_label}. "
                  "All positions conceptually closed at 3:50 PM.")

    log_entry = {"time": time_label, "phase": phase.upper(), "action": action, "detail": detail}
    session_log = _append_log(prev_strategy, today_iso, log_entry)

    rationale = (
        f"Deployed into {len(picks)} high-conviction names ({pos_summary}). "
        f"Market breadth: {breadth_label}. "
        f"Weighted by signal strength. Stop -1.5% | Target +3.0%."
    )
    return "TRADE", positions, picks, rationale, session_log


def _append_log(prev_strategy, today_iso, new_entry):
    """Carry forward today's session log and append a new entry."""
    existing = []
    if prev_strategy and isinstance(prev_strategy, dict):
        if prev_strategy.get("day") == today_iso:
            existing = list(prev_strategy.get("session_log") or [])
    # Replace any entry for same phase
    phase = new_entry["phase"]
    existing = [e for e in existing if e.get("phase") != phase]
    existing.append(new_entry)
    return existing


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
        return None, None, None

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
        return None, None, None

    # Weight by score, clamp 12-35%, renormalize
    total_score = sum(s for _, s, *_ in picks_raw)
    raw_w = [max(0.12, min(0.35, s / total_score)) for _, s, *_ in picks_raw]
    total_rw = sum(raw_w)
    weights = [w / total_rw for w in raw_w]

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
        f"Top {len(picks)} names by composite momentum. "
        f"Score-weighted (not equal weight). "
        f"Sector cap enforced (max 2 per sector). "
        f"Quality gate: 20d momentum positive required."
    )
    return positions, picks, rationale


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
        return None, None, None

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
        return None, None, None

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
        f"Top {len(picks)} quality compounders for the month. "
        f"Quartile-weighted (top names get largest allocation). "
        f"60d quality filter applied — no negative long-term trends. "
        f"Sector cap 35%. Stop flag at -12% intra-month."
    )
    return positions, picks, rationale


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
            "ticker":     sym,
            "signal":     signal,
            "confidence": round(min(abs(pct) / 5.0, 1.0), 2),
            "reason":     reason,
            "price":      round(p, 2),
            "change_pct": round(pct, 2),
            "sector":     SECTORS.get(sym, ""),
            "date":       today_iso,
        })

    recs.sort(key=lambda r: -abs(r["change_pct"]))
    return {
        "recommendations": recs,
        "summary":         summary,
        "generated_at":    dt.datetime.now().isoformat(timespec="seconds"),
    }


# ── News ─────────────────────────────────────────────────────────────────────────
SECTOR_QUERIES = {
    "AI & Quantum": '("artificial intelligence" OR "quantum computing" OR "AI chip" OR "qubit" OR Nvidia OR Anthropic OR OpenAI OR IonQ OR Quantinuum OR Rigetti)',
    "Biotech":      '(biotech OR mRNA OR CRISPR OR "gene therapy" OR "FDA approval" OR clinical OR Moderna OR BioNTech OR Vertex)',
    "Energy":       '(oil OR LNG OR renewables OR solar OR "energy storage" OR Aramco OR Exxon OR Chevron OR "First Solar")',
    "Defense":      '(defense OR Lockheed OR Raytheon OR "Northrop Grumman" OR BAE OR hypersonic OR "missile defense")',
    "Finance":      '(JPMorgan OR Goldman OR "Bank of America" OR Visa OR Mastercard OR "Federal Reserve" OR earnings)',
}

def fetch_news(api_key):
    """Fetch financial news from NewsAPI.org — same pattern as lvl13.tech."""
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
                    "q": query, "from": from_date, "language": "en",
                    "sortBy": "publishedAt", "pageSize": 8, "apiKey": api_key,
                },
                timeout=15,
            )
            if r.status_code == 200:
                data = r.json()
                count = 0
                for a in data.get("articles", []):
                    title = (a.get("title") or "").split(" - ")[0].strip()
                    key   = title[:80].lower()
                    if not title or key in seen or "[Removed]" in title:
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
                print(f"  [news] {sector}: {count} articles")
            else:
                print(f"  [news] {sector} HTTP {r.status_code}: {r.text[:120]}")
        except Exception as e:
            print(f"  [news] {sector} error: {e}")

    all_items.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    all_items = all_items[:30]
    print(f"  [news] fetched {len(all_items)} total articles")
    return all_items


def push_news_to_api(items, secrets):
    """Push news items to the backend tracker API (platform=wallstbots)."""
    if _requests is None:
        print("  [news-push] requests not available — skipping")
        return
    api_url      = secrets.get("api_url") or os.environ.get("TRACKER_API_URL", "")
    internal_key = secrets.get("internal_api_key") or os.environ.get("INTERNAL_API_KEY", "")
    if not api_url or not internal_key:
        print("  [news-push] missing api_url or internal_api_key — skipping push")
        return

    payload = {
        "platform":  "wallstbots",
        "data_type": "news",
        "data": {
            "items":        items,
            "sectors":      sorted({it["sector"] for it in items}),
            "generated_at": dt.datetime.utcnow().isoformat() + "Z",
        },
    }
    try:
        r = _requests.post(
            f"{api_url}/internal/tracker/push",
            json=payload,
            headers={"internal_api_key": internal_key},
            timeout=20,
        )
        if r.status_code == 200:
            print(f"  [news-push] ✓ pushed {len(items)} articles to backend API")
        else:
            print(f"  [news-push] HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"  [news-push] error: {e}")


# ── Git push ──────────────────────────────────────────────────────────────────────
def git_push(msg):
    git_root = Path(__file__).resolve().parents[2]
    try:
        subprocess.run(["git", "-C", str(git_root), "add",
                        "Frontends/wallstbots.tech/data/"], check=True)
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
        print("[wallstbots] ERROR: zero prices returned.")
        sys.exit(1)

    # ── Fetch historical data for strategy scoring ───────────────────────────
    hist_data = get_hist_data(list(need_syms))

    # ── BOT13 decision ───────────────────────────────────────────────────────
    print(f"[wallstbots] running BOT13 decision (phase: {session_phase()})...")
    prev_b13_strategy = funds.get("bot13", {}).get("current_strategy")
    b13_decision, b13_positions, b13_picks, b13_rationale, b13_log = run_bot13_decision(
        prices, prev_closes, sc_global, today_iso, prev_b13_strategy
    )
    print(f"  BOT13: {b13_decision} ({len(b13_picks)} picks)")

    # ── ORACLE decision (Monday only, otherwise keep existing positions) ──────
    oracle_new_positions = None
    oracle_new_picks     = None
    oracle_new_rationale = None
    if is_monday and hist_data:
        print("[wallstbots] Monday — running ORACLE recompute...")
        oracle_new_positions, oracle_new_picks, oracle_new_rationale = run_oracle_decision(
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
    if is_month_start and hist_data:
        print(f"[wallstbots] Month start ({today_iso}) — running WIZARD recompute...")
        wizard_new_positions, wizard_new_picks, wizard_new_rationale = run_wizard_decision(
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
                enriched = b13_positions
                cash     = 0.0
            else:
                enriched = []
                cash     = sc

            pos_val = sum(p["value"] for p in enriched)
            total   = pos_val + cash
            pnl     = total - sc
            pnl_pct = (total / sc - 1) * 100 if sc else 0
            day_pnl = sum(p.get("day_pnl", 0) for p in enriched)
            n_pos   = len(enriched)
            day_pct = sum(p.get("day_pct", 0) for p in enriched) / n_pos if n_pos else 0

            value    = {"total": round(total,2), "cash": round(cash,2), "pos_val": round(pos_val,2),
                        "pnl": round(pnl,2), "pnl_pct": round(pnl_pct,2),
                        "day_pnl": round(day_pnl,2), "day_pct": round(day_pct,2), "positions": enriched}
            strategy = {
                "day":         today_iso,
                "decision":    b13_decision,
                "rationale":   b13_rationale,
                "picks":       b13_picks,
                "session_log": b13_log,
            }

        elif fid == "oracle":
            if oracle_new_positions:
                raw_pos  = oracle_new_positions
                strategy = {
                    "week":      today_iso,
                    "decision":  "TRADE",
                    "rationale": oracle_new_rationale,
                    "picks":     oracle_new_picks,
                }
                # Update stored positions with new entries
                fund_copy = dict(fund)
                fund_copy["value"] = dict(fund.get("value", {}))
                fund_copy["value"]["positions"] = raw_pos
                fund = fund_copy
            else:
                strategy = fund.get("current_strategy")

            raw_pos  = fund.get("value", {}).get("positions", [])
            enriched = [enrich_position(p, prices, prev_closes) for p in raw_pos]
            cash     = float(fund.get("value", {}).get("cash") or 0)
            pos_val  = sum(p["value"] for p in enriched)
            total    = pos_val + cash
            pnl      = total - sc
            pnl_pct  = (total / sc - 1) * 100 if sc else 0
            day_pnl  = sum(p["day_pnl"] for p in enriched)
            day_pct  = (day_pnl / (total - day_pnl)) * 100 if (total - day_pnl) else 0
            value    = {"total": round(total,2), "cash": round(cash,2), "pos_val": round(pos_val,2),
                        "pnl": round(pnl,2), "pnl_pct": round(pnl_pct,2),
                        "day_pnl": round(day_pnl,2), "day_pct": round(day_pct,2), "positions": enriched}

        elif fid == "wizard":
            if wizard_new_positions:
                raw_pos  = wizard_new_positions
                strategy = {
                    "month":     month_str,
                    "decision":  "TRADE",
                    "rationale": wizard_new_rationale,
                    "picks":     wizard_new_picks,
                }
                fund_copy = dict(fund)
                fund_copy["value"] = dict(fund.get("value", {}))
                fund_copy["value"]["positions"] = raw_pos
                fund = fund_copy
            else:
                # Intra-month: check for -12% stop flags
                strategy = fund.get("current_strategy")

            raw_pos  = fund.get("value", {}).get("positions", [])
            enriched = []
            for p in raw_pos:
                ep = enrich_position(p, prices, prev_closes)
                # Flag any position beyond -12% stop
                if ep["pnl_pct"] < -12.0:
                    ep["stop_triggered"] = True
                enriched.append(ep)
            cash     = float(fund.get("value", {}).get("cash") or 0)
            pos_val  = sum(p["value"] for p in enriched)
            total    = pos_val + cash
            pnl      = total - sc
            pnl_pct  = (total / sc - 1) * 100 if sc else 0
            day_pnl  = sum(p["day_pnl"] for p in enriched)
            day_pct  = (day_pnl / (total - day_pnl)) * 100 if (total - day_pnl) else 0
            value    = {"total": round(total,2), "cash": round(cash,2), "pos_val": round(pos_val,2),
                        "pnl": round(pnl,2), "pnl_pct": round(pnl_pct,2),
                        "day_pnl": round(day_pnl,2), "day_pct": round(day_pct,2), "positions": enriched}

        else:
            # Equalizer + Titan — mark-to-market only
            raw_pos  = fund.get("value", {}).get("positions", [])
            enriched = [enrich_position(p, prices, prev_closes) for p in raw_pos]
            cash     = float(fund.get("value", {}).get("cash") or 0)
            pos_val  = sum(p["value"] for p in enriched)
            total    = pos_val + cash
            pnl      = total - sc
            pnl_pct  = (total / sc - 1) * 100 if sc else 0
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


    # ── Write state.json ──────────────────────────────────────────────────────
    state_out = {"data": {
        "starting_capital": sc_global,
        "last_refresh":     now_iso,
        "snapshots":        snapshots,
        "funds":            funds_out,
        "leaderboards":     {"week": wk_lb, "all": all_lb},
    }}
    STATE_FILE.write_text(json.dumps(state_out, indent=2))
    print(f"[wallstbots] state.json written — {len(funds_out)} funds, {len(snapshots)} snapshots")

    # ── Write signals.json ────────────────────────────────────────────────────
    signals = generate_signals(prices, prev_closes, hist_data)
    (DATA_DIR / "signals.json").write_text(json.dumps({"data": signals}, indent=2))
    n_sig = len(signals["recommendations"])
    print(f"[wallstbots] signals.json — {n_sig} signals")

    # ── Fetch news + push to backend API ─────────────────────────────────────
    print("[wallstbots] fetching news...")
    news_items = fetch_news(newsapi_key)
    if news_items:
        push_news_to_api(news_items, secrets)
    else:
        print("  [news] 0 articles — skipping push")
    print(f"[wallstbots] news done — {len(news_items)} articles")

    # ── Git push ──────────────────────────────────────────────────────────────
    if args.push:
        git_push("wallstbots.tech data refresh")

    print("\n[wallstbots] ALL DONE")


if __name__ == "__main__":
    main()
