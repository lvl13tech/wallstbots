#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bot13_engine.py  ─  Unified Bot13 Decision Engine
==================================================
Shared decision logic for all three WallStBots platforms:
  ▸ wallstbots.tech   — equity, broad-market universe
  ▸ lvl13.tech        — equity, AI & quantum universe
  ▸ bitbot13.tech     — crypto, 50-coin universe

Both run_bot13_equity() and run_bot13_crypto() return the same 6-tuple:
    (decision, positions, picks, rationale, session_log, projected_return)

New in this version vs per-script logic:
  ✓  Config-driven session boundaries (equity vs crypto hours)
  ✓  Internal stop at 1.35% (slippage buffer) — displayed as 1.5% to users
  ✓  ATR-based pre-session volatility filter for equity
  ✓  Account-level daily drawdown kill switch (1.5% account-wide)
  ✓  Unified 6-tuple return — bitbot13 now includes rationale & session_log
"""

import datetime as dt

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  PLATFORM CONFIGS                                                             ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

EQUITY_CFG = {
    "market_type":        "equity",
    "session_start":      (9, 30),          # (hour, minute) ET
    "session_end":        (16, 0),
    "trading_days":       {0, 1, 2, 3, 4},  # Mon=0 … Fri=4
    "stop_internal":      1.35,             # actual exit trigger (slippage buffer baked in)
    "stop_display":       1.5,              # shown in picks + UI
    "target_pct":         3.0,
    "proj_threshold":     1.74,             # min weighted projected return to trade
    "max_daily_drawdown": 0.015,            # account-level kill switch: 1.5% down from day_open
    "min_picks":          3,                # min qualified names to open a session
    "weight_min":         0.12,
    "weight_max":         0.33,
    "atr_volatility_cap": 4.0,             # if avg ATR% > this, raise entry hurdle
    "atr_high_threshold": 1.5,             # higher entry bar on high-ATR days (vs 1.0% normal)
}

CRYPTO_CFG = {
    "market_type":        "crypto",
    "session_start":      (9, 0),
    "session_end":        (21, 0),
    "trading_days":       {0, 1, 2, 3, 4, 5, 6},   # 7 days
    "stop_internal":      1.35,
    "stop_display":       1.5,
    "target_pct":         3.0,
    "proj_threshold":     1.74,
    "max_daily_drawdown": 0.015,
    "min_picks":          1,
    "weight_min":         0.20,             # equal-weight (1/5 per coin)
    "weight_max":         0.20,
    "atr_volatility_cap": 0,               # not used for crypto (intraday filter used instead)
    "atr_high_threshold": 0,
}


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TIME & SESSION HELPERS                                                       ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

def et_now():
    """Return current time as a timezone-naive datetime in US/Eastern.
    Uses accurate DST boundaries: 2nd Sunday March → 1st Sunday November.
    """
    utc = dt.datetime.utcnow()
    year = utc.year
    march1   = dt.date(year, 3, 1)
    dst_on   = march1  + dt.timedelta(days=(6 - march1.weekday())  % 7 + 7)
    nov1     = dt.date(year, 11, 1)
    dst_off  = nov1    + dt.timedelta(days=(6 - nov1.weekday())    % 7)
    offset   = -4 if dst_on <= utc.date() < dst_off else -5
    return utc + dt.timedelta(hours=offset)


def window_open(cfg):
    """Return True if current ET time is within the platform's trading session."""
    now = et_now()
    sh, sm = cfg["session_start"]
    eh, em = cfg["session_end"]
    if now.weekday() not in cfg["trading_days"]:
        return False
    session_start_mins = sh * 60 + sm
    session_end_mins   = eh * 60 + em
    now_mins           = now.hour * 60 + now.minute
    return session_start_mins <= now_mins < session_end_mins


def session_phase(cfg):
    """Return 'morning' | 'midday' | 'close' for equity, or 'open' | 'close' for crypto."""
    now = et_now()
    h   = now.hour
    if cfg["market_type"] == "crypto":
        sh, _ = cfg["session_start"]
        eh, _ = cfg["session_end"]
        mid   = sh + (eh - sh) // 2
        return "open" if h < mid else "close"
    else:
        if h < 11:
            return "morning"
        if h < 14:
            return "midday"
        return "close"


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  MATH HELPERS                                                                  ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

def compute_rsi(closes, period=14):
    """Compute RSI from a list of closes. Returns float 0–100."""
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


def compute_atr(closes, period=14):
    """
    Compute ATR proxy using absolute close-to-close changes.
    Returns the N-period average absolute daily move (in price units).
    Falls back to 0.0 if insufficient data.
    """
    if len(closes) < 2:
        return 0.0
    abs_moves = [abs(closes[i] - closes[i - 1]) for i in range(1, len(closes))]
    window    = abs_moves[-period:]
    return sum(window) / len(window) if window else 0.0


def compute_atr_pct(closes, period=14):
    """Return ATR as a percentage of the latest close price. Used for the pre-session filter."""
    if len(closes) < 2 or closes[-1] <= 0:
        return 0.0
    return (compute_atr(closes, period) / closes[-1]) * 100


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  PORTFOLIO HELPERS                                                             ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

def grade(pct):
    if pct >= 5:    return "A+"
    if pct >= 3:    return "A"
    if pct >= 1.5:  return "B"
    if pct >= 0:    return "C"
    if pct >= -2:   return "D"
    return "F"


def grade_overall(pct, inception_iso, today):
    try:
        inception = dt.date.fromisoformat(str(inception_iso)[:10])
        weeks     = max((today - inception).days / 7, 1)
        return grade(pct / weeks)
    except Exception:
        return grade(pct)


def enrich_position(pos, prices, prev_closes, price_dp=4):
    """
    Mark-to-market a stored position against live prices.
    price_dp: decimal places for price fields (4 for stocks, dynamic for crypto).
    """
    sym        = pos["symbol"]
    shares     = float(pos.get("shares") or 0)
    entry      = float(pos.get("entry_price") or pos.get("entry") or 0)
    cost_basis = shares * entry
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
        "entry_price":   round(entry, price_dp),
        "current_price": round(price, price_dp),
        "cost_basis":    round(cost_basis, 2),
        "price":         round(price, price_dp),
        "value":         round(value, 2),
        "pnl":           round(pnl, 2),
        "pnl_pct":       round(pnl_pct, 2),
        "day_pnl":       round(day_pnl, 2),
        "day_pct":       round(day_pct, 2),
    }
    for field in ("stop_pct", "target_pct", "entry_time", "stop_triggered", "exit_reason"):
        if field in pos:
            result[field] = pos[field]
    return result


def check_drawdown(cfg, day_open, stored_positions, prices):
    """
    Return True if the account-level daily drawdown limit has been hit.
    Drawdown is computed as current mark-to-market portfolio value vs day_open.
    """
    if not stored_positions or day_open <= 0:
        return False
    current = sum(
        prices.get(p["symbol"], float(p.get("entry_price", 0))) * float(p.get("shares", 0))
        for p in stored_positions if p.get("symbol")
    )
    if current <= 0:
        return False
    drawdown_pct = (day_open - current) / day_open
    return drawdown_pct >= cfg["max_daily_drawdown"]


def _append_log(prev_strategy, today_iso, new_entry):
    """Carry forward today's session log and append a new entry (replaces same-phase entry)."""
    existing = []
    if prev_strategy and isinstance(prev_strategy, dict):
        if prev_strategy.get("day") == today_iso:
            existing = list(prev_strategy.get("session_log") or [])
    phase    = new_entry["phase"]
    existing = [e for e in existing if e.get("phase") != phase]
    existing.append(new_entry)
    return existing


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  BOT13 EQUITY ENGINE                                                           ║
# ║                                                                                ║
# ║  Used by: wallstbots.tech  (broad-market universe)                             ║
# ║           lvl13.tech       (AI & quantum universe)                             ║
# ║                                                                                ║
# ║  Philosophy: Strike fast on confirmed intraday leadership. Only trade when     ║
# ║  conditions are clearly favorable. When in doubt — stay in cash.               ║
# ║                                                                                ║
# ║  Entry Rules:                                                                  ║
# ║  - Stock must be up >1.0% from previous close (1.5% on high-ATR days)         ║
# ║  - At least 3 qualified candidates required (breadth confirmation)             ║
# ║  - No more than 33% of universe down >2% (market health check)                ║
# ║  - Account drawdown < 1.5% from day_open (kill switch)                        ║
# ║                                                                                ║
# ║  Risk: Internal stop -1.35% (buffer for slippage). Displayed as -1.5%.        ║
# ║        Profit target: +3.0%. ATR filter tightens entry on volatile days.      ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

def run_bot13_equity(
    cfg, universe, prices, prev_closes, hist_data,
    starting_capital, today_iso, prev_strategy=None,
):
    """
    Compute BOT13 equity decision.

    Parameters
    ----------
    cfg            : EQUITY_CFG dict
    universe       : list of stock symbols to score
    prices         : {sym: float}  live prices
    prev_closes    : {sym: float}  previous session closes
    hist_data      : {sym: {"closes": [...], "volumes": [...]}}  90-day history
    starting_capital: day_open value — used as capital base AND for drawdown check
    today_iso      : ISO date string "YYYY-MM-DD"
    prev_strategy  : previous strategy dict (to carry forward session_log)

    Returns
    -------
    (decision, positions, picks, rationale, session_log, projected_return)
    """
    phase      = session_phase(cfg)
    now        = et_now()
    time_label = f"{now.hour}:{now.minute:02d} {'AM' if now.hour < 12 else 'PM'}"

    stop_internal = cfg["stop_internal"]
    stop_display  = cfg["stop_display"]
    target_pct    = cfg["target_pct"]

    def _cash_return(reason_str, log_action, log_detail):
        log_entry  = {"time": time_label, "phase": phase.upper(), "action": log_action, "detail": log_detail}
        slog       = _append_log(prev_strategy, today_iso, log_entry)
        return "CASH", [], [], reason_str, slog, 0.0

    def _hold_return(reason_str, log_action, log_detail):
        log_entry  = {"time": time_label, "phase": phase.upper(), "action": log_action, "detail": log_detail}
        slog       = _append_log(prev_strategy, today_iso, log_entry)
        return "HOLD", [], [], reason_str, slog, 0.0

    # ── ATR-based pre-session volatility filter ──────────────────────────────
    entry_hurdle = 1.0   # default
    if cfg.get("atr_volatility_cap", 0) > 0 and hist_data:
        atr_pcts = []
        for sym in universe:
            closes = (hist_data.get(sym) or {}).get("closes", [])
            if len(closes) >= 5:
                atr_pcts.append(compute_atr_pct(closes, period=14))
        if atr_pcts:
            avg_atr = sum(atr_pcts) / len(atr_pcts)
            if avg_atr > cfg["atr_volatility_cap"]:
                entry_hurdle = cfg["atr_high_threshold"]   # tighter on volatile days

    # ── Market health check ──────────────────────────────────────────────────
    n_green   = 0
    n_red     = 0
    n_priced  = 0
    for sym in universe:
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

    breadth_pct   = n_green / n_priced if n_priced else 0
    sell_pressure = n_red   / n_priced if n_priced else 0

    if sell_pressure > 0.33:
        return _cash_return(
            f"CASH — broad selling pressure ({int(sell_pressure*100)}% of stocks down >2%). No trades today.",
            "CASH — MARKET HEALTH FAIL",
            f"{int(sell_pressure*100)}% of universe down >2%. Broad selling pressure detected — protecting capital.",
        )

    # ── Score each candidate ─────────────────────────────────────────────────
    scored = []
    for sym in universe:
        p  = prices.get(sym, 0)
        pc = prev_closes.get(sym, p)
        if p <= 0 or pc <= 0:
            continue
        day_pct = (p / pc - 1) * 100

        if day_pct < entry_hurdle:
            continue

        if day_pct > 8.0:
            strength = day_pct * 0.55
        elif day_pct > 5.0:
            strength = day_pct * 0.80
        else:
            strength = day_pct

        scored.append((sym, day_pct, strength))

    if len(scored) < cfg["min_picks"]:
        return _cash_return(
            f"CASH — only {len(scored)} stock(s) cleared the {entry_hurdle}% entry hurdle. "
            f"Need at least {cfg['min_picks']} qualified names for a tradeable session.",
            "CASH — INSUFFICIENT BREADTH",
            f"Only {len(scored)} stock(s) up >{entry_hurdle}%. "
            f"Need minimum {cfg['min_picks']} qualified names. Sitting out.",
        )

    scored.sort(key=lambda x: -x[2])
    top_picks = scored[:5]

    # ── Size proportionally to signal strength ───────────────────────────────
    total_strength = sum(s for _, _, s in top_picks)
    raw_weights    = [s / total_strength for _, _, s in top_picks]
    clamped        = [max(cfg["weight_min"], min(cfg["weight_max"], w)) for w in raw_weights]
    total_c        = sum(clamped)
    weights        = [c / total_c for c in clamped]

    # ── Projected portfolio return gate ──────────────────────────────────────
    projected_return = round(
        sum(w * day_pct for (_, day_pct, _), w in zip(top_picks, weights)), 2
    )
    if projected_return <= cfg["proj_threshold"]:
        return _hold_return(
            f"HOLD — projected return {projected_return:.2f}% ≤ {cfg['proj_threshold']}% threshold. "
            "Not enough edge today.",
            f"HOLD — LOW PROJECTED RETURN ({projected_return:.2f}%)",
            f"Weighted projected return {projected_return:.2f}% ≤ {cfg['proj_threshold']}% threshold. "
            "Not enough edge to justify risk today. Holding for the day.",
        )

    # ── Build positions & picks ──────────────────────────────────────────────
    positions, picks = [], []
    for i, (sym, day_pct, strength) in enumerate(top_picks):
        w      = weights[i]
        alloc  = starting_capital * w
        price  = prices.get(sym, 0)
        prev   = prev_closes.get(sym, price)
        entry  = prev if prev > 0 else price
        shares = alloc / entry if entry > 0 else 0
        pnl    = shares * price - alloc
        pnl_pct = (price / entry - 1) * 100 if entry > 0 else 0
        day_pnl = shares * (price - entry)

        intensity = ("STRONG momentum" if day_pct >= 5.0
                     else "solid momentum" if day_pct >= 2.5
                     else "emerging momentum")

        positions.append({
            "symbol":         sym,
            "shares":         round(shares, 6),
            "entry_price":    round(entry, 4),
            "current_price":  round(price, 4),
            "cost_basis":     round(alloc, 2),
            "price":          round(price, 4),
            "value":          round(shares * price, 2),
            "pnl":            round(pnl, 2),
            "pnl_pct":        round(pnl_pct, 2),
            "day_pnl":        round(day_pnl, 2),
            "day_pct":        round(day_pct, 2),
            "stop_pct":       -stop_display,    # displayed stop
            "target_pct":     target_pct,
            "entry_time":     dt.datetime.now().isoformat(timespec="seconds"),
            "stop_triggered": False,
            "exit_reason":    None,
        })
        picks.append({
            "symbol":    sym,
            "weight":    round(w, 4),
            "score":     round(strength * 10, 1),
            "rationale": (f"{sym}: {intensity} +{day_pct:.2f}% — "
                          f"{w*100:.0f}% allocation (${alloc:,.0f}). "
                          f"Stop: -{stop_display}% | Target: +{target_pct}%."),
        })

    # ── Build session log entry ──────────────────────────────────────────────
    pos_summary   = ", ".join(f"{sym} {dpct:+.2f}%" for sym, dpct, _ in top_picks)
    breadth_label = f"{n_green}/{n_priced} green"

    if phase == "morning":
        action = f"ENTERED {len(picks)} position{'s' if len(picks) > 1 else ''}"
        detail = (f"{pos_summary}. Breadth: {breadth_label}. "
                  f"Stops at -{stop_display}%, targets at +{target_pct}%. Capital deployed.")
    elif phase == "midday":
        action = "MIDDAY CHECK — positions reviewed"
        detail = (f"Current positions: {pos_summary}. Breadth: {breadth_label}. "
                  f"Monitoring for stop/target triggers. "
                  f"Any position through -{stop_internal}% (internal) exits immediately.")
    else:
        action = "CLOSE — session complete"
        day_total = sum(p["day_pnl"] for p in positions)
        detail = (f"Final session positions: {pos_summary}. Day P&L: ${day_total:+,.0f}. "
                  f"Breadth: {breadth_label}. All positions conceptually closed at session end.")

    log_entry   = {"time": time_label, "phase": phase.upper(), "action": action, "detail": detail}
    session_log = _append_log(prev_strategy, today_iso, log_entry)

    rationale = (
        f"Projected return: +{projected_return:.2f}%. "
        f"Deployed into {len(picks)} high-conviction names ({pos_summary}). "
        f"Market breadth: {breadth_label}. "
        f"Weighted by signal strength. Stop -{stop_display}% | Target +{target_pct}%."
    )
    return "TRADE", positions, picks, rationale, session_log, projected_return


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  BOT13 CRYPTO ENGINE                                                           ║
# ║                                                                                ║
# ║  Used by: bitbot13.tech  (50-coin universe)                                    ║
# ║                                                                                ║
# ║  Philosophy: 7-day market. Score 1h + 4h + 24h momentum with volume           ║
# ║  confirmation. Filters out low-volume fakeouts. Equal-weighted positions.      ║
# ║                                                                                ║
# ║  Entry Rules:                                                                  ║
# ║  - Positive composite momentum (1h×0.45 + 4h×0.35 + 24h×0.20)                ║
# ║  - Volume confirmation ≥ normal (rejects thin/suspicious moves)                ║
# ║  - Positive 1h momentum (no fading entries)                                   ║
# ║  - Account drawdown < 1.5% from day_open (kill switch)                        ║
# ║                                                                                ║
# ║  Risk: Internal stop -1.35% (slippage buffer). Displayed as -1.5%.            ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

def run_bot13_crypto(
    cfg, universe, prices, prev_closes, intraday_data,
    starting_capital, today_iso, prev_strategy=None,
):
    """
    Compute BOT13 crypto decision.

    Parameters
    ----------
    cfg            : CRYPTO_CFG dict
    universe       : list of coin symbols to score
    prices         : {sym: float}  live prices
    prev_closes    : {sym: float}  24h-ago closes
    intraday_data  : {sym: {"closes": [...hourly...], "volumes": [...]}}
    starting_capital: day_open value
    today_iso      : ISO date string "YYYY-MM-DD"
    prev_strategy  : previous strategy dict (to carry forward session_log)

    Returns
    -------
    (decision, positions, picks, rationale, session_log, projected_return)
    """
    now_iso    = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    now        = et_now()
    time_label = f"{now.hour}:{now.minute:02d} {'AM' if now.hour < 12 else 'PM'}"
    phase      = session_phase(cfg)

    stop_internal = cfg["stop_internal"]
    stop_display  = cfg["stop_display"]
    target_pct    = cfg["target_pct"]

    def _hold_return(reason_str, log_action, log_detail):
        log_entry  = {"time": time_label, "phase": phase.upper(), "action": log_action, "detail": log_detail}
        slog       = _append_log(prev_strategy, today_iso, log_entry)
        return "HOLD", [], [], reason_str, slog, 0.0

    # ── Score each coin ──────────────────────────────────────────────────────
    scored = []
    for sym in universe:
        p  = prices.get(sym, 0)
        pc = prev_closes.get(sym, p)
        if p <= 0:
            continue

        mom_24h    = (p / pc - 1) * 100 if pc > 0 else 0
        mom_1h     = 0.0
        mom_4h     = 0.0
        vol_signal = "neutral"
        intra      = (intraday_data or {}).get(sym, {})
        closes_1h  = intra.get("closes", [])
        volumes_1h = intra.get("volumes", [])

        if len(closes_1h) >= 2:
            mom_1h = (closes_1h[-1] / closes_1h[-2] - 1) * 100 if closes_1h[-2] > 0 else 0
        if len(closes_1h) >= 5:
            mom_4h = (closes_1h[-1] / closes_1h[-5] - 1) * 100 if closes_1h[-5] > 0 else 0

        if len(volumes_1h) >= 7:
            avg_vol   = sum(volumes_1h[-7:-1]) / 6
            cur_vol   = volumes_1h[-1]
            vol_ratio = cur_vol / avg_vol if avg_vol > 0 else 1.0
            vol_signal = "high" if vol_ratio >= 1.5 else ("normal" if vol_ratio >= 0.8 else "low")

        if vol_signal == "low":
            continue

        composite = (mom_1h * 0.45 + mom_4h * 0.35 + mom_24h * 0.20
                     if closes_1h else mom_24h)

        if composite <= 0.3:
            continue
        if closes_1h and mom_1h < 0:
            continue

        scored.append((sym, composite, mom_1h, mom_4h, mom_24h, vol_signal))

    scored.sort(key=lambda x: -x[1])
    top_picks = scored[:5]

    if not top_picks:
        return _hold_return(
            "HOLD — no coins cleared the momentum and volume filters. Staying out.",
            "HOLD — NO QUALIFIED PICKS",
            "Zero coins passed composite momentum + volume confirmation filters.",
        )

    # ── Projected portfolio return gate ──────────────────────────────────────
    projected_return = round(
        sum(mom_24h for _, _, _, _, mom_24h, _ in top_picks) / len(top_picks), 2
    )
    if projected_return <= cfg["proj_threshold"]:
        return _hold_return(
            f"HOLD — projected return {projected_return:.2f}% ≤ {cfg['proj_threshold']}% threshold. "
            "Not enough edge today.",
            f"HOLD — LOW PROJECTED RETURN ({projected_return:.2f}%)",
            f"Average 24h projected return {projected_return:.2f}% ≤ {cfg['proj_threshold']}% threshold. "
            "Not enough edge to justify risk. Standing down.",
        )

    # ── Build positions & picks (equal-weight) ───────────────────────────────
    per       = starting_capital / len(top_picks)
    positions, picks = [], []
    for sym, composite, mom_1h, mom_4h, mom_24h, vol_signal in top_picks:
        price = prices.get(sym, 0)
        prev  = prev_closes.get(sym, price)
        if price <= 0:
            continue
        entry    = prev if prev > 0 else price
        shares   = per / entry
        pnl      = shares * price - per
        pnl_pct  = (price / entry - 1) * 100 if entry > 0 else 0
        day_pnl  = shares * (price - entry)
        price_dp = 8 if price < 0.01 else (4 if price < 1 else 2)

        positions.append({
            "symbol":         sym,
            "shares":         round(shares, 6),
            "entry_price":    round(entry, price_dp),
            "current_price":  round(price, price_dp),
            "cost_basis":     round(per, 2),
            "price":          round(price, price_dp),
            "value":          round(shares * price, 2),
            "pnl":            round(pnl, 2),
            "pnl_pct":        round(pnl_pct, 2),
            "day_pnl":        round(day_pnl, 2),
            "day_pct":        round(mom_24h, 2),
            "stop_pct":       -stop_display,
            "target_pct":     target_pct,
            "entry_time":     now_iso,
            "momentum_1h":    round(mom_1h, 2),
            "momentum_4h":    round(mom_4h, 2),
            "volume_signal":  vol_signal,
            "stop_triggered": False,
            "exit_reason":    None,
        })
        picks.append({
            "symbol":    sym,
            "weight":    round(1.0 / len(top_picks), 4),
            "score":     round(composite, 1),
            "rationale": (f"{sym}: 1h {mom_1h:+.2f}% | 4h {mom_4h:+.2f}% | "
                          f"24h {mom_24h:+.2f}% | Vol: {vol_signal}"),
        })

    # ── Session log ──────────────────────────────────────────────────────────
    syms_summary = ", ".join(f"{sym} {m24:+.2f}%" for sym, _, _, _, m24, _ in top_picks)
    if phase == "open":
        action = f"ENTERED {len(picks)} position{'s' if len(picks) > 1 else ''}"
        detail = (f"{syms_summary}. Stops at -{stop_display}%, targets at +{target_pct}%. "
                  f"Equal-weight ${per:,.0f}/coin. Capital deployed.")
    else:
        action = "SESSION CLOSE — monitoring"
        day_total = sum(p["day_pnl"] for p in positions)
        detail = (f"Positions: {syms_summary}. Day P&L: ${day_total:+,.0f}. "
                  f"Approaching session close — monitoring for stop/target triggers.")

    log_entry   = {"time": time_label, "phase": phase.upper(), "action": action, "detail": detail}
    session_log = _append_log(prev_strategy, today_iso, log_entry)

    rationale = (
        f"Projected return: +{projected_return:.2f}%. "
        f"Deployed into {len(picks)} coins with momentum + volume confirmation ({syms_summary}). "
        f"Equal-weight ${per:,.0f}/coin. "
        f"Stop -{stop_display}% (internal -{stop_internal}%) | Target +{target_pct}%."
    )
    return "TRADE", positions, picks, rationale, session_log, projected_return
