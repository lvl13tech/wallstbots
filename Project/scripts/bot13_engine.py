#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bot13_engine.py  -  Unified Bot13 Decision Engine
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

# +==============================================================================+
# |  PLATFORM CONFIGS                                                             |
# +==============================================================================+

EQUITY_CFG = {
    "market_type":        "equity",
    "session_start":      (9, 30),          # (hour, minute) ET
    "session_end":        (16, 0),
    "close_out":          (15, 30),         # BOT13 force-flattens all positions at this ET time
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
    "close_out":          (21, 0),          # BOT13 force-flattens all positions at this ET time
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


# +==============================================================================+
# |  TIME & SESSION HELPERS                                                       |
# +==============================================================================+

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


# US stock-market holidays (NYSE/Nasdaq) -- dates the EQUITY market is CLOSED.
# Uses OBSERVED dates (holiday on Sat -> observed Fri; on Sun -> observed Mon).
# Crypto trades 365 days, so these apply to equity only (see is_market_holiday).
US_MARKET_HOLIDAYS = {
    # 2026
    "2026-01-01",  # New Year's Day
    "2026-01-19",  # Martin Luther King Jr. Day
    "2026-02-16",  # Presidents' Day
    "2026-04-03",  # Good Friday
    "2026-05-25",  # Memorial Day
    "2026-06-19",  # Juneteenth
    "2026-07-03",  # Independence Day (observed -- Jul 4 is a Saturday)
    "2026-09-07",  # Labor Day
    "2026-11-26",  # Thanksgiving Day
    "2026-12-25",  # Christmas Day
    # 2027
    "2027-01-01",  # New Year's Day
    "2027-01-18",  # Martin Luther King Jr. Day
    "2027-02-15",  # Presidents' Day
    "2027-03-26",  # Good Friday
    "2027-05-31",  # Memorial Day
    "2027-06-18",  # Juneteenth (observed -- Jun 19 is a Saturday)
    "2027-07-05",  # Independence Day (observed -- Jul 4 is a Sunday)
    "2027-09-06",  # Labor Day
    "2027-11-25",  # Thanksgiving Day
    "2027-12-24",  # Christmas Day (observed -- Dec 25 is a Saturday)
}


def is_market_holiday(cfg, d=None):
    """True if date d (ET) is a US stock-market holiday. Crypto never has holidays."""
    if cfg.get("market_type") == "crypto":
        return False
    if d is None:
        d = et_now().date()
    return d.isoformat() in US_MARKET_HOLIDAYS


def is_trading_day(cfg, d=None):
    """True only if date d is a REAL trading day for this market: an allowed weekday AND
    (for equity) not a US market holiday. Crypto trades every day. This is the single
    gate that keeps funds from seeding/trading/snapshotting on weekends or holidays."""
    if d is None:
        d = et_now().date()
    if d.weekday() not in cfg["trading_days"]:
        return False
    return not is_market_holiday(cfg, d)


def next_trading_day(cfg, d=None):
    """The next REAL trading day strictly AFTER date d (ET). Crypto -> tomorrow; equity ->
    the next weekday that is not a US market holiday. Used to tell users exactly when a
    freshly created portfolio (or a just-reset fund) will begin trading -- nothing trades on
    its creation/reset day; it holds starting capital flat and opens at the next session."""
    import datetime as _dt
    if d is None:
        d = et_now().date()
    nd = d + _dt.timedelta(days=1)
    for _ in range(14):   # safety cap
        if is_trading_day(cfg, nd):
            return nd
        nd = nd + _dt.timedelta(days=1)
    return nd


def window_open(cfg):
    """Return True if the market is OPEN right now: a real trading day (weekday, not a
    holiday) AND inside the platform's session hours."""
    now = et_now()
    sh, sm = cfg["session_start"]
    eh, em = cfg["session_end"]
    if not is_trading_day(cfg, now.date()):   # weekend OR US market holiday -> closed
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


def past_close_out(cfg, now=None):
    """Return True once current ET time has reached the platform's daily
    BOT13 close-out cutoff (EQUITY_CFG/CRYPTO_CFG "close_out").

    This is intentionally separate from window_open()/session_end -- session_end
    only gates whether BOT13 may open NEW positions. past_close_out() answers a
    different question: has the moment arrived where BOT13 must force-flatten
    any positions it is still holding, so every position is closed same-day and
    every SELL gets a real, same-moment exit_time instead of being inferred the
    next time the picks list changes.
    """
    now = now or et_now()
    ch, cm = cfg["close_out"]
    return (now.hour * 60 + now.minute) >= (ch * 60 + cm)


# +==============================================================================+
# |  MATH HELPERS                                                                  |
# +==============================================================================+

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


# +==============================================================================+
# |  PORTFOLIO HELPERS                                                             |
# +==============================================================================+

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



def fmt_et_human(iso_str):
    """Format an ISO datetime string as 'Jun 19, 2026 4:19 PM ET'.
    Returns '' for falsy input so callers/frontends can show a fallback.
    Times produced by this codebase are already US/Eastern (see et_now), so
    we just relabel them ET -- we do not re-convert.
    """
    if not iso_str:
        return ""
    s = str(iso_str).replace("Z", "").strip()
    try:
        d = dt.datetime.fromisoformat(s)
    except Exception:
        try:
            d = dt.datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")
        except Exception:
            return str(iso_str)
    try:
        return d.strftime("%b %-d, %Y %-I:%M %p ET")
    except Exception:
        return d.strftime("%b %d, %Y %I:%M %p ET")


def stamp_and_log(prev_positions, new_positions, trade_log, now_iso, max_entries=200):
    """Transparency engine: stamp immutable entry_time on opens and append an
    append-only trade ledger of every BUY / SELL / RESIZE.

    Diff is by symbol:
      * symbol present now but not before -> BUY  (shares, entry price)
      * symbol present before but not now -> SELL (shares, exit price, reason,
                                                   realized P&L)
      * share count changed > 2 percent   -> BUY/SELL resize event
    Append-only: prior trade_log is carried forward, never rewritten.
    new_positions is mutated in place to stamp entry_time on fresh opens.

    Timestamp-ordering guarantee: a SELL's logged "ts" must never be earlier
    than the "ts" of the BUY that opened the lot it's closing. The engine
    doesn't always know the real wall-clock close moment (a symbol can sit
    untouched across several intraday ticks before a later run notices it's
    gone), so SELL falls back to now_iso -- but now_iso is clamped forward to
    the BUY's timestamp if it would otherwise read earlier. This fixes
    same-day BUY-before-SELL inversions without changing any trade decision
    logic or the trade-log table's render order.
    Returns the updated (capped) trade_log.
    """
    log = list(trade_log or [])
    prev = {p.get("symbol"): p for p in (prev_positions or []) if p.get("symbol")}
    new  = {p.get("symbol"): p for p in (new_positions or []) if p.get("symbol")}

    # Most recent BUY/opened timestamp on record per symbol, used as the floor
    # for any SELL of that symbol's lot below.
    last_buy_ts = {}
    for entry in log:
        if entry.get("action") == "BUY" and entry.get("symbol") and entry.get("ts"):
            last_buy_ts[entry["symbol"]] = entry["ts"]

    def _not_before(sym, candidate_ts):
        """Return candidate_ts, or the symbol's last BUY ts if that is later."""
        floor = last_buy_ts.get(sym)
        if floor and candidate_ts and str(floor) > str(candidate_ts):
            return floor
        return candidate_ts

    for sym, p in new.items():
        if not p.get("entry_time") and sym not in prev:
            p["entry_time"] = now_iso

    for sym, p in new.items():
        shares = float(p.get("shares") or 0)
        price  = float(p.get("entry_price") or p.get("price") or 0)
        if sym not in prev:
            buy_ts = p.get("entry_time") or now_iso
            log.append({
                "ts":     buy_ts,
                "action": "BUY",
                "symbol": sym,
                "shares": round(shares, 6),
                "price":  round(price, 4),
                "reason": "opened",
            })
            last_buy_ts[sym] = buy_ts
        else:
            old_sh = float(prev[sym].get("shares") or 0)
            if old_sh > 0 and abs(shares - old_sh) / old_sh > 0.02:
                cur = float(p.get("price") or price)
                is_buy = shares > old_sh
                log.append({
                    "ts":     now_iso if is_buy else _not_before(sym, now_iso),
                    "action": "BUY" if is_buy else "SELL",
                    "symbol": sym,
                    "shares": round(abs(shares - old_sh), 6),
                    "price":  round(cur, 4),
                    "reason": "added to position" if is_buy else "trimmed position",
                })

    for sym, p in prev.items():
        if sym not in new:
            old_sh = float(p.get("shares") or 0)
            entry  = float(p.get("entry_price") or 0)
            exitpx = float(p.get("price") or p.get("current_price") or entry)
            realized = round((exitpx - entry) * old_sh, 2) if entry else 0.0
            sell_ts = _not_before(sym, p.get("exit_time") or now_iso)
            log.append({
                "ts":       sell_ts,
                "action":   "SELL",
                "symbol":   sym,
                "shares":   round(old_sh, 6),
                "price":    round(exitpx, 4),
                "reason":   p.get("exit_reason") or "closed",
                "realized": realized,
            })

    return log[-max_entries:]


def _price_dp(p):
    """Receipt precision: a recorded price must never lose information (audit
    2026-07-20: SHIB/XEC receipts rounded to $0.0000 by hardcoded 4dp).
    8dp under 1 cent, 6dp under $1, else 4dp — matches Display Spec v1 storage."""
    p = abs(float(p or 0))
    return 8 if p < 0.01 else (6 if p < 1 else 4)


def reconcile_bot13_log(held_book, real_now, trade_log, today_iso, session_end, prices, now_iso):
    """THE LEDGER IS THE ONLY AUTHORITY (2026-07-16, owner order: "no patch fixes").

    History: the old design diffed an in-memory 'held_book' against the new positions.
    That book does NOT survive between runs (fresh runners, and the backend never
    persisted it), so runs re-diffed against amnesia — producing duplicate BUYs and,
    on 2026-07-16, a DOUBLE SELL of the same MANTA lot. Timestamp-dedupe couldn't stop
    it because each phantom got a fresh timestamp. Symptom patches are hereby dead.

    New law — every row is validated against the PERSISTED trade log itself
    (the one store that survives every run):
      * OPEN LOT = a BUY in today's log with no later SELL for that symbol.
      * A SELL may ONLY be recorded for an open lot; realized P&L is computed from
        the LEDGER's own entry price. No open lot -> no SELL. A double-sell is now
        structurally impossible, not merely filtered.
      * A BUY may ONLY be recorded when the ledger shows NO open lot for the symbol.
        A double-buy is likewise impossible. A genuine re-entry (BUY-SELL-BUY) still
        works because the first lot is closed in the ledger.
      * DAY ROLL: if the log belongs to a prior day, that day's still-open lots are
        closed at that day's session close (from the LEDGER's entries), then today
        starts fresh. No position crosses midnight.
    'held_book' is advisory only (exit_time/exit_reason hints). Returns
    (today_only_log, real_now) — same contract as before.
    """
    eh, em = session_end
    log = list(trade_log or [])

    def _open_lots(entries):
        lots = {}
        for e in entries:
            s = e.get("symbol"); a = str(e.get("action", "")).upper()
            if not s:
                continue
            if a == "BUY":
                lots[s] = e
            elif a == "SELL":
                lots.pop(s, None)
        return lots

    # --- DAY ROLL: close a prior day's open lots at that day's close, from the ledger ---
    log_day = str(log[-1].get("ts", ""))[:10] if log else ""
    if log and log_day and log_day < today_iso:
        for s, b in sorted(_open_lots(log).items()):
            d = str(b.get("ts", ""))[:10] or log_day
            ts = f"{d}T{eh:02d}:{em:02d}:00"
            entry = float(b.get("price") or 0)
            sh    = float(b.get("shares") or 0)
            px    = float(prices.get(s, entry) or entry)
            log.append({"ts": ts, "action": "SELL", "symbol": s, "shares": round(sh, 6),
                        "price": round(px, _price_dp(px)), "reason": "daily close-out",
                        "realized": round((px - entry) * sh, 2) if entry else 0.0})
    log = [e for e in log if str(e.get("ts", ""))[:10] == today_iso]   # today-only

    lots = _open_lots(log)                                   # ledger truth, right now
    now  = {p["symbol"]: dict(p) for p in (real_now or []) if p.get("symbol")}
    held = {p.get("symbol"): p for p in (held_book or []) if p.get("symbol")}

    # SELLs: open in the LEDGER, no longer held. Entry price & shares come from the ledger.
    for s, b in sorted(lots.items()):
        if s not in now:
            entry = float(b.get("price") or 0)
            sh    = float(b.get("shares") or 0)
            px    = float(prices.get(s, entry) or entry)
            hb = held.get(s) or {}
            ts = hb.get("exit_time") or now_iso
            if str(b.get("ts", "")) > str(ts):               # SELL never predates its BUY
                ts = str(b.get("ts"))
            log.append({"ts": ts, "action": "SELL", "symbol": s, "shares": round(sh, 6),
                        "price": round(px, _price_dp(px)), "reason": hb.get("exit_reason") or "closed",
                        "realized": round((px - entry) * sh, 2) if entry else 0.0})
    # BUYs: held now, but the LEDGER shows no open lot.
    for s, p in sorted(now.items()):
        if s not in lots:
            entry = float(p.get("entry_price") or p.get("price") or 0)
            sh    = float(p.get("shares") or 0)
            ts = p.get("entry_time") or now_iso
            log.append({"ts": ts, "action": "BUY", "symbol": s, "shares": round(sh, 6),
                        "price": round(entry, _price_dp(entry)), "reason": "opened"})
    return log[-200:], list(real_now or [])


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


# +==============================================================================+
# |  BOT13 EQUITY ENGINE                                                           |
# |                                                                                |
# |  Used by: wallstbots.tech  (broad-market universe)                             |
# |           lvl13.tech       (AI & quantum universe)                             |
# |                                                                                |
# |  Philosophy: Strike fast on confirmed intraday leadership. Only trade when     |
# |  conditions are clearly favorable. When in doubt — stay in cash.               |
# |                                                                                |
# |  Entry Rules:                                                                  |
# |  - Stock must be up >1.0% from previous close (1.5% on high-ATR days)         |
# |  - At least 3 qualified candidates required (breadth confirmation)             |
# |  - No more than 33% of universe down >2% (market health check)                |
# |  - Account drawdown < 1.5% from day_open (kill switch)                        |
# |                                                                                |
# |  Risk: Internal stop -1.35% (buffer for slippage). Displayed as -1.5%.        |
# |        Profit target: +3.0%. ATR filter tightens entry on volatile days.      |
# +==============================================================================+

def resolve_edge_score(prev_strategy, fresh_proj, picks, today_iso, session_ended):
    """
    Projected Edge Score = the number BOT13 computed WHEN IT DECIDED (trade if it exceeds the
    1.74% threshold, else hold cash). NOT the live day return. We record ONE score per genuine
    DECISION -- the day's open call, or an intraday rotation into a DIFFERENT set of names --
    never once per refresh, so it can never drift into Today's Change. During the session we show
    the latest decision's score; after the session ends we show the AVERAGE of the day's decision
    scores. Used by all 3 site engines + the member script so public and member stay identical.

    Returns (display_score, proj_samples, proj_last_set). Persist proj_samples + proj_last_set on
    the strategy dict so the day's decisions survive across refreshes.
    """
    prev    = prev_strategy or {}
    fresh   = round(float(fresh_proj or 0.0), 2)
    samples = [float(x) for x in (prev.get("proj_samples") or [])]
    last_set = list(prev.get("proj_last_set") or [])
    cur_set = sorted([p.get("symbol") for p in (picks or []) if p.get("symbol")])

    if prev.get("day") != today_iso:
        samples, last_set = [fresh], cur_set              # first decision of a new day
    elif cur_set and cur_set != sorted(last_set):
        samples, last_set = samples + [fresh], cur_set    # genuine rotation into new names
    # else: same names (or none) -> no new decision -> keep the day's samples (no drift)

    if not samples:
        samples = [fresh]
    display = round(sum(samples) / len(samples), 2) if session_ended else round(samples[-1], 2)
    return display, [round(x, 2) for x in samples], last_set


def _run_open_market(cfg, universe, prices, prev_closes, hist_data, intraday_data,
                     starting_capital, today_iso, prev_strategy=None, atr_scale=1.0):
    """BOT13 OPEN-MARKET EDGE v1 — THE ONE DECISION PIPELINE, ALL PLATFORMS
    (owner-defined 2026-07-16; adopted platform-wide 2026-07-17, pre-reset).

    THE OWNER'S DEFINITION GOVERNS: the Projected Edge Score is the return BOT13
    projects it can STILL earn from here today. At or under proj_threshold (1.74%)
    it sits the day out. Movers that already spent their move are REJECTED by the
    STILL-IN-PLAY test instead of shrinking the universe:
      * FADED        — price below 90% of today's high
      * STALLED      — latest bar below the prior bar (buyers gone quiet)
      * OVERSTRETCHED— day move > 4x the name's own ATR14 (a gap, not a trend)
    Then gold sizing (dampening, top 5, cfg weight clamps) and the forward edge:
    edge = sum(weight x 0.5 x pick's own ATR14%). Opening read: no first decision in
    the first 15 minutes after session start. Entries at LIVE prices (copy-trade law).
    intraday_data: {sym:{"closes":[...]}} bars if the caller has them (crypto passes
    hourly bars); equity callers pass None and the shortlist's 15-min bars are
    fetched here (top 40 only — tiny load)."""
    now        = et_now()
    phase      = session_phase(cfg)
    time_label = f"{now.hour}:{now.minute:02d} {'AM' if now.hour < 12 else 'PM'}"

    def _ret(decision, reason, action, detail, proj=0.0, positions=None, picks=None):
        entry = {"time": time_label, "phase": phase.upper(), "action": action, "detail": detail}
        slog = _append_log(prev_strategy, today_iso, entry)
        return decision, positions or [], picks or [], reason, slog, round(float(proj or 0.0), 2)

    # -- opening read: the in-play test needs real tape; skip the first 15 minutes --
    sh, sm = cfg["session_start"]
    first_ok = sh * 60 + sm + 15
    already_decided = bool(prev_strategy and prev_strategy.get("day") == today_iso
                           and prev_strategy.get("picks"))
    if not already_decided and (now.hour * 60 + now.minute) < first_ok:
        return _ret("HOLD", f"Opening read — BOT13 watches the first 15 minutes before deciding. "
                            f"First decision at {first_ok//60}:{first_ok%60:02d} ET.",
                    "OPENING READ", "Waiting for real tape before the first decision.")

    # -- day moves + breadth veto (owner-restored 2026-07-13) ------------------------
    day, n_red, n_priced = {}, 0, 0
    for s in universe:
        p, pc = prices.get(s, 0), prev_closes.get(s, 0)
        if p <= 0 or pc <= 0:
            continue
        pct = (p / pc - 1) * 100
        if abs(pct) > cfg.get("sane_move_cap_pct", 40.0):
            continue
        day[s] = pct
        n_priced += 1
        if pct <= -2.0:
            n_red += 1
    if not n_priced:
        return _ret("CASH", "CASH — no clean prices this session.", "CASH", "No prices.")
    if n_red / n_priced > 0.33:
        r = (f"CASH — broad selling pressure ({int(n_red/n_priced*100)}% of the universe "
             "down >2%). Protecting capital.")
        return _ret("CASH", r, "CASH — MARKET HEALTH FAIL", r)

    # -- entry hurdle (gold ATR rule) ------------------------------------------------
    hurdle = 1.0
    if cfg.get("atr_volatility_cap", 0) > 0 and hist_data:
        atrs = [compute_atr_pct((hist_data.get(s) or {}).get("closes", []))
                for s in universe if len((hist_data.get(s) or {}).get("closes", [])) >= 5]
        if atrs and sum(atrs) / len(atrs) > cfg["atr_volatility_cap"]:
            hurdle = cfg["atr_high_threshold"]

    movers = sorted(((s, p) for s, p in day.items() if p >= hurdle), key=lambda x: -x[1])[:40]
    if len(movers) < cfg["min_picks"]:
        r = f"CASH — only {len(movers)} name(s) cleared the {hurdle:g}% hurdle. Sitting out."
        return _ret("CASH", r, "CASH — INSUFFICIENT BREADTH", r)

    # -- STILL-IN-PLAY test (intraday bars) ------------------------------------------
    bars_map = {}
    if intraday_data:
        bars_map = {s: (intraday_data.get(s) or {}).get("closes") or [] for s, _ in movers}
    else:
        try:
            import yfinance as yf
            df = yf.download([s for s, _ in movers], period="1d", interval="15m",
                             progress=False, group_by="ticker", threads=True, auto_adjust=True)
            for s, _ in movers:
                try:
                    sub = df[s].dropna() if len(movers) > 1 else df.dropna()
                    bars_map[s] = [float(x) for x in sub["Close"]]
                except Exception:
                    bars_map[s] = []
        except Exception:
            bars_map = {}
    survivors, rej = [], {"faded": 0, "stalled": 0, "stretched": 0, "nodata": 0}
    for s, pct in movers:
        bars = (bars_map.get(s) or [])[-26:]          # today's tape (or latest bars)
        if len(bars) < 2:
            rej["nodata"] += 1; continue
        day_high, last, prev_bar = max(bars), bars[-1], bars[-2]
        # atr_scale converts intraday-bar ATR to daily terms when the caller's
        # history is hourly (crypto: sqrt(24) ≈ 4.9). Equity passes daily bars, scale 1.
        hcloses = (hist_data.get(s) or {}).get("closes", []) if hist_data else []
        # "normal range" must be measured BEFORE today's move — otherwise the very
        # spike being tested inflates the ATR and every gap looks normal. Daily
        # history: drop the latest bar. Hourly history (crypto): drop the last 24.
        prior = hcloses[:-1] if atr_scale == 1.0 else hcloses[:-24]
        if len(prior) < 15:
            # can't measure the name's normal range -> can't honestly judge
            # "still in play" or project a forward return. Reject, never guess.
            rej["nodata"] += 1; continue
        atrp = compute_atr_pct(prior) * atr_scale
        if last < 0.90 * day_high:
            rej["faded"] += 1; continue
        if last < prev_bar:
            rej["stalled"] += 1; continue
        if atrp > 0 and pct > 4.0 * atrp:
            rej["stretched"] += 1; continue
        survivors.append((s, pct, atrp or 1.0, last))
    n_rej = sum(rej.values())
    if len(survivors) < cfg["min_picks"]:
        r = (f"CASH — {len(movers)} strong movers found, but only {len(survivors)} still in play "
             f"(rejected {rej['faded']} faded, {rej['stalled']} stalled, {rej['stretched']} "
             "overstretched). A move already taken can't be copied. Sitting out.")
        return _ret("CASH", r, "CASH — NOTHING STILL IN PLAY", r)

    # -- gold sizing + THE OWNER'S FORWARD EDGE ---------------------------------------
    scored = sorted(((s, p, p * (0.55 if p > 8 else 0.80 if p > 5 else 1.0), a, px)
                     for s, p, a, px in survivors), key=lambda x: -x[2])
    top = scored[:5]
    tot = sum(x[2] for x in top)
    raw = [x[2] / tot for x in top]
    cl  = [max(cfg["weight_min"], min(cfg["weight_max"], w)) for w in raw]
    weights = [c / sum(cl) for c in cl]
    proj = round(sum(w * (0.5 * x[3]) for x, w in zip(top, weights)), 2)
    if proj <= cfg["proj_threshold"]:
        r = (f"HOLD — projected remaining return {proj:.2f}% ≤ {cfg['proj_threshold']}% threshold. "
             f"{len(survivors)} names still in play, but not enough left in the tank. "
             "No edge, no trade, no risk.")
        return _ret("HOLD", r, f"HOLD — INSUFFICIENT EDGE ({proj:.2f}%)", r, proj)

    stop_display, target_pct = cfg["stop_display"], cfg["target_pct"]
    positions, picks = [], []
    for (s, pct, strength, atrp, last), w in zip(top, weights):
        entry  = float(last) if last > 0 else float(prices.get(s, 0))   # LIVE fill
        alloc  = starting_capital * w
        shares = alloc / entry if entry > 0 else 0
        positions.append({
            "symbol": s, "shares": round(shares, 6), "entry_price": round(entry, _price_dp(entry)),
            "current_price": round(entry, _price_dp(entry)), "cost_basis": round(alloc, 2),
            "price": round(entry, _price_dp(entry)), "value": round(shares * entry, 2),
            "pnl": 0.0, "pnl_pct": 0.0, "day_pnl": 0.0, "day_pct": round(pct, 2),
            "stop_pct": -stop_display, "target_pct": target_pct,
            "entry_time": now.isoformat(timespec="seconds"),
            "stop_triggered": False, "exit_reason": None,
        })
        picks.append({
            "symbol": s, "weight": round(w, 4), "score": round(strength * 10, 1),
            "rationale": (f"{s}: up {pct:+.2f}% and STILL IN PLAY — holding its highs, buyers "
                          f"active, {pct/atrp:.1f}x its normal range. Projected {0.5*atrp:.2f}% "
                          f"more from here — {w*100:.0f}% allocation (${alloc:,.0f}). "
                          f"Stop: -{stop_display}% | Target: +{target_pct}%."),
        })
    r = (f"Deployed into {len(top)} names still in play — projected {proj:.2f}% more from here "
         f"(cleared the {cfg['proj_threshold']}% bar). Screened {n_priced:,} names, {len(movers)} "
         f"strong movers, rejected {n_rej} that had already spent their move "
         f"({rej['faded']} faded, {rej['stalled']} stalled, {rej['stretched']} overstretched). "
         f"Stop -{stop_display}% | Target +{target_pct}%.")
    return _ret("TRADE", r, f"ENTERED {len(top)} positions",
                f"{', '.join(f'{x[0]} {x[1]:+.2f}%' for x in top)}. Projected +{proj:.2f}% remaining.",
                proj, positions, picks)


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
    # >>> OPEN-MARKET EDGE v1 IS THE ACTIVE PIPELINE (owner order 2026-07-17,
    # all platforms, pre-reset). Everything below this return is the legacy
    # momentum body — DEAD CODE kept for reference only. Do not resurrect it
    # without an explicit owner order.
    return _run_open_market(cfg, universe, prices, prev_closes, hist_data, None,
                            starting_capital, today_iso, prev_strategy)

    phase      = session_phase(cfg)
    now        = et_now()
    time_label = f"{now.hour}:{now.minute:02d} {'AM' if now.hour < 12 else 'PM'}"

    stop_internal = cfg["stop_internal"]
    stop_display  = cfg["stop_display"]
    target_pct    = cfg["target_pct"]

    def _cash_return(reason_str, log_action, log_detail, proj=0.0):
        log_entry  = {"time": time_label, "phase": phase.upper(), "action": log_action, "detail": log_detail}
        slog       = _append_log(prev_strategy, today_iso, log_entry)
        return "CASH", [], [], reason_str, slog, round(float(proj or 0.0), 2)

    def _hold_return(reason_str, log_action, log_detail, proj=0.0):
        log_entry  = {"time": time_label, "phase": phase.upper(), "action": log_action, "detail": log_detail}
        slog       = _append_log(prev_strategy, today_iso, log_entry)
        return "HOLD", [], [], reason_str, slog, round(float(proj or 0.0), 2)

    # -- ATR-based pre-session volatility filter ------------------------------
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

    # -- Market health check --------------------------------------------------
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

    # -- 2026-07-13 OWNER REVERT: Option 3 (2026-07-11) produced results the owner
    #    rejected after its first live session. The FULL market-health veto is
    #    restored: broad selling pressure = 100% CASH day. Owner's words: "I'd rather
    #    hold cash than lose money." Do not soften this again without an explicit
    #    owner order.
    eff_threshold = cfg["proj_threshold"]
    breadth_note  = ""
    if sell_pressure > 0.33:
        return _cash_return(
            f"CASH — broad selling pressure ({int(sell_pressure*100)}% of stocks down >2%). No trades today.",
            "CASH — MARKET HEALTH FAIL",
            f"{int(sell_pressure*100)}% of universe down >2%. Broad selling pressure detected — protecting capital.",
        )

    # -- Score each candidate -------------------------------------------------
    scored = []
    for sym in universe:
        p  = prices.get(sym, 0)
        pc = prev_closes.get(sym, p)
        if p <= 0 or pc <= 0:
            continue
        day_pct = (p / pc - 1) * 100

        # -- BAD-DATA GUARD: a stock doesn't legitimately move hundreds of % in
        #    a day; such a reading means a garbage price feed. Reject it so bad
        #    data never becomes a trade (mirrors the crypto engine guard).
        if abs(day_pct) > cfg.get("sane_move_cap_pct", 40.0):
            continue

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

    # -- Size proportionally to signal strength -------------------------------
    total_strength = sum(s for _, _, s in top_picks)
    raw_weights    = [s / total_strength for _, _, s in top_picks]
    clamped        = [max(cfg["weight_min"], min(cfg["weight_max"], w)) for w in raw_weights]
    total_c        = sum(clamped)
    weights        = [c / total_c for c in clamped]

    # -- Projected portfolio return gate --------------------------------------
    projected_return = round(
        sum(w * day_pct for (_, day_pct, _), w in zip(top_picks, weights)), 2
    )
    if projected_return <= eff_threshold:
        return _hold_return(
            f"HOLD — calculated edge score {projected_return:.2f}% ≤ {eff_threshold:g}% threshold. "
            "Not enough edge today." + breadth_note,
            f"HOLD — INSUFFICIENT EDGE ({projected_return:.2f}%)",
            f"Calculated edge score {projected_return:.2f}% ≤ {eff_threshold:g}% threshold. "
            "Not enough edge to justify risk today. Holding for the day." + breadth_note,
            projected_return,
        )

    # -- Build positions & picks ----------------------------------------------
    positions, picks = [], []
    for i, (sym, day_pct, strength) in enumerate(top_picks):
        w      = weights[i]
        alloc  = starting_capital * w
        price  = prices.get(sym, 0)
        prev   = prev_closes.get(sym, price)
        # COPY-TRADE INTEGRITY (2026-07-10, Rule 0): entry = the LIVE price at decision
        # time — the fill a member copying this trade right now would actually get.
        # prev_close remains the SIGNAL baseline only; it is never a fill price.
        entry  = price if price > 0 else prev
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
            "entry_time":     et_now().isoformat(timespec="seconds"),
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

    # -- Build session log entry ----------------------------------------------
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
        f"Deployed into {len(picks)} high-conviction names ({pos_summary}). "
        f"Market breadth: {breadth_label}. "
        f"Weighted by signal strength. Stop -{stop_display}% | Target +{target_pct}%."
        + breadth_note
    )
    return "TRADE", positions, picks, rationale, session_log, projected_return


# +==============================================================================+
# |  BOT13 CRYPTO ENGINE                                                           |
# |                                                                                |
# |  Used by: bitbot13.tech  (50-coin universe)                                    |
# |                                                                                |
# |  Philosophy: 7-day market. Score 1h + 4h + 24h momentum with volume           |
# |  confirmation. Filters out low-volume fakeouts. Equal-weighted positions.      |
# |                                                                                |
# |  Entry Rules:                                                                  |
# |  - Positive composite momentum (1h×0.45 + 4h×0.35 + 24h×0.20)                |
# |  - Volume confirmation ≥ normal (rejects thin/suspicious moves)                |
# |  - Positive 1h momentum (no fading entries)                                   |
# |  - Account drawdown < 1.5% from day_open (kill switch)                        |
# |                                                                                |
# |  Risk: Internal stop -1.35% (slippage buffer). Displayed as -1.5%.            |
# +==============================================================================+

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
    # >>> OPEN-MARKET EDGE v1 IS THE ACTIVE PIPELINE (owner order 2026-07-17,
    # all platforms, pre-reset). Crypto passes its hourly bars as the intraday
    # tape for the still-in-play test. Legacy composite body below is DEAD CODE
    # kept for reference only.
    return _run_open_market(cfg, universe, prices, prev_closes,
                            intraday_data or {}, intraday_data,
                            starting_capital, today_iso, prev_strategy,
                            atr_scale=4.9)   # hourly bars -> daily ATR (sqrt(24))

    now_iso    = et_now().isoformat(timespec="seconds")
    now        = et_now()
    time_label = f"{now.hour}:{now.minute:02d} {'AM' if now.hour < 12 else 'PM'}"
    phase      = session_phase(cfg)

    stop_internal = cfg["stop_internal"]
    stop_display  = cfg["stop_display"]
    target_pct    = cfg["target_pct"]

    def _hold_return(reason_str, log_action, log_detail, proj=0.0):
        log_entry  = {"time": time_label, "phase": phase.upper(), "action": log_action, "detail": log_detail}
        slog       = _append_log(prev_strategy, today_iso, log_entry)
        return "HOLD", [], [], reason_str, slog, round(float(proj or 0.0), 2)

    # -- Score each coin ------------------------------------------------------
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

        # -- BAD-DATA GUARD ---------------------------------------------------
        # A real coin does not legitimately move hundreds of percent in 24h (or
        # in 1h/4h). Such a reading means the price feed gave a garbage value
        # (e.g. a near-zero prev close), which previously caused BOT13 to deploy
        # 100% into a junk pick at a fake +1629% "edge". Reject any coin whose
        # momentum exceeds a sane sanity cap so bad data never becomes a trade.
        SANE_MOVE_CAP = cfg.get("sane_move_cap_pct", 60.0)  # % move beyond this = bad data
        if (abs(mom_24h) > SANE_MOVE_CAP or abs(mom_1h) > SANE_MOVE_CAP
                or abs(mom_4h) > SANE_MOVE_CAP):
            continue

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

    # -- Projected portfolio return gate --------------------------------------
    projected_return = round(
        sum(mom_24h for _, _, _, _, mom_24h, _ in top_picks) / len(top_picks), 2
    )
    if projected_return <= cfg["proj_threshold"]:
        return _hold_return(
            f"HOLD — calculated edge score {projected_return:.2f}% ≤ {cfg['proj_threshold']}% threshold. "
            "Not enough edge today.",
            f"HOLD — INSUFFICIENT EDGE ({projected_return:.2f}%)",
            f"Calculated edge score {projected_return:.2f}% ≤ {cfg['proj_threshold']}% threshold. "
            "Not enough edge to justify risk. Standing down.",
            projected_return,
        )

    # -- Build positions & picks (equal-weight) -------------------------------
    per       = starting_capital / len(top_picks)
    positions, picks = [], []
    for sym, composite, mom_1h, mom_4h, mom_24h, vol_signal in top_picks:
        price = prices.get(sym, 0)
        prev  = prev_closes.get(sym, price)
        if price <= 0:
            continue
        # COPY-TRADE INTEGRITY (2026-07-10, Rule 0): entry = the LIVE price at decision
        # time — never the prior close. Members copying the trade get this same fill.
        entry    = price
        shares   = per / entry
        pnl      = shares * price - per
        pnl_pct  = (price / entry - 1) * 100 if entry > 0 else 0
        day_pnl  = shares * (price - entry)
        price_dp = 8 if price < 0.01 else (6 if price < 1 else (4 if price < 10 else 2))  # storage tiers match refresh_portfolios._entry_dp (audit 2026-07-11: $1-$10 coins at 2dp shifted real P&L%)

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

    # -- Session log ----------------------------------------------------------
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
        f"Deployed into {len(picks)} coins with momentum + volume confirmation ({syms_summary}). "
        f"Equal-weight ${per:,.0f}/coin. "
        f"Stop -{stop_display}% (internal -{stop_internal}%) | Target +{target_pct}%."
    )
    return "TRADE", positions, picks, rationale, session_log, projected_return


# ============================================================================
# SHARED DISPLAY MATH (2026-07-06 de-duplication)
# One copy of the number calculations, used by ALL THREE refresh engines.
# Rule: an engine may differ only by asset class (crypto flag) -- never by
# formula. Each function reproduces the engines' existing output shape
# EXACTLY; nothing new appears on any page.
# ============================================================================

def mark_position(pos, prices, prev_closes, crypto=False):
    """Mark-to-market one stored position. THE single copy of this math.

    crypto=False (wallstbots/aistocks): 4dp prices, includes current_price,
        preserves stop_pct/target_pct + entry_time/stop_triggered/exit_reason.
    crypto=True  (bitbot13): dynamic decimals for tiny coins, preserves the
        crypto receipt fields (momentum/volume) as well.
    """
    from datetime import datetime as _dt  # local to avoid import-order surprises
    sym        = pos["symbol"]
    shares     = float(pos.get("shares") or 0)
    entry      = float(pos.get("entry_price") or pos.get("entry") or 0)
    price      = prices.get(sym, entry)
    # BAD-DATA MARK GUARD (2026-07-10, Rule 0 / copy-trade): a >8x or <0.125x print
    # vs entry while held is a garbage feed price, not profit. Clamp the bad MARK by
    # keeping the last good price — NEVER rewrite the recorded entry_price or shares.
    # A member copied the trade at the recorded entry; receipts are immutable.
    if entry > 0 and price > 0:
        _ratio = price / entry
        if _ratio > 8.0 or _ratio < 0.125:
            price = float(pos.get("price") or pos.get("current_price") or entry)
            pos["shares"]      = shares
    cost_basis = shares * entry  # always recompute; stored cost may be stale
    prev       = prev_closes.get(sym, price)
    # A lot OPENED TODAY was not held overnight: its day baseline is its real
    # entry price, not yesterday's close (keeps Holdings summing to the box).
    _et_today = str(pos.get("entry_time") or "")[:10]
    if _et_today and _et_today == et_now().date().isoformat() and entry > 0:
        prev = entry
    value   = shares * price
    pnl     = value - cost_basis
    pnl_pct = (price / entry - 1) * 100 if entry > 0 else 0
    day_pnl = shares * (price - prev)
    day_pct = (price / prev - 1) * 100 if prev > 0 else 0
    if crypto:
        price_dp = 8 if price < 0.01 else (6 if price < 1 else (4 if price < 10 else 2))  # storage tiers match refresh_portfolios._entry_dp (audit 2026-07-11: $1-$10 coins at 2dp shifted real P&L%)
        out = {
            "symbol":      sym,
            "shares":      round(shares, 6),
            "entry_price": round(entry, price_dp),
            "cost_basis":  round(cost_basis, 2),
            "price":       round(price, price_dp),
            "value":       round(value, 2),
            "pnl":         round(pnl, 2),
            "pnl_pct":     round(pnl_pct, 2),
            "day_pnl":     round(day_pnl, 2),
            "day_pct":     round(day_pct, 2),
        }
        for field in ("entry_time", "momentum_1h", "momentum_4h", "volume_signal",
                      "stop_triggered", "exit_reason"):
            if field in pos:
                out[field] = pos[field]
        return out
    out = {
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
    if "stop_pct" in pos:
        out["stop_pct"]   = pos["stop_pct"]
    if "target_pct" in pos:
        out["target_pct"] = pos["target_pct"]
    for field in ("entry_time", "stop_triggered", "exit_reason"):
        if field in pos:
            out[field] = pos[field]
    return out


def build_day_reference(state_data, snapshots, today_iso, prev_closes, tag=""):
    """ONE CLOCK: resolve the day-reference price map for display math.

    Returns the stored day_boundary prices (the prices yesterday's snapshot was
    actually written from) when they exist for the most recent prior snapshot
    date; otherwise falls back to the feed's prev_closes. Trading signals must
    keep using feed prev_closes -- this is for DISPLAY math only.
    """
    _boundary = (state_data or {}).get("day_boundary") or {}
    _prior = [s.get("date") for s in (snapshots or []) if s.get("date") and s.get("date") < today_iso]
    _prev_snap_date = max(_prior) if _prior else None
    if _boundary.get("date") == _prev_snap_date and isinstance(_boundary.get("prices"), dict) and _boundary.get("prices"):
        day_ref = dict(prev_closes)
        for _s, _v in _boundary["prices"].items():
            try:
                if _v and float(_v) > 0:
                    day_ref[_s] = float(_v)
            except Exception:
                pass
        print(f"[{tag}] day reference = boundary prices from {_boundary['date']} ({len(_boundary['prices'])} assets)")
        return day_ref
    print(f"[{tag}] day reference = feed prev_closes (no stored boundary for yesterday yet)")
    return prev_closes


def day_boundary_payload(prices, today_iso):
    """The day_boundary block each engine stores with its state push."""
    return {"date": today_iso,
            "prices": {s: round(float(v), 8) for s, v in prices.items() if v}}


def reset_occurred_mid_run(platform, loaded_inceptions, api_url):
    """RESET-COLLISION GUARD (2026-07-06, root-cause fix -- shared by all 3 engines).

    An engine loads state at the start of a run, computes for minutes, and pushes at
    the end. If a FULL RESET runs in that window, the engine's end-of-run push would
    overwrite the reset with pre-reset data -- this resurrected 'corrupt' numbers the
    morning after every reset for a week (bitbot13 refreshes 24/7, so a reset there
    almost always collided with an in-flight run).

    A reset stamps every fund's inception with the reset date. Just before pushing,
    the engine calls this with the inceptions it LOADED at run start; if the backend
    now reports a different inception for any fund, a reset happened mid-run and the
    caller must ABANDON the run (no disk write, no push). The next scheduled run
    starts from the clean post-reset state. Fails OPEN (allows the push) only when
    the backend cannot be reached -- the same condition under which a reset could
    not have completed either.
    """
    import urllib.request as _url, json as _json
    from datetime import datetime as _dt
    try:
        u = (f"{api_url}/public/tracker/state?platform={platform}"
             f"&_rg={_dt.now().strftime('%H%M%S%f')}")   # cache-buster: must see LIVE state
        req = _url.Request(u, headers={"Cache-Control": "no-cache"})
        cur = _json.load(_url.urlopen(req, timeout=15))
        cur_funds = ((cur or {}).get("data") or {}).get("funds") or {}
    except Exception as e:
        print(f"  [reset-guard] could not verify backend inception ({e}) -- allowing push")
        return False
    for fid, loaded_inc in (loaded_inceptions or {}).items():
        cur_inc = (cur_funds.get(fid) or {}).get("inception")
        if cur_inc and loaded_inc and str(cur_inc) != str(loaded_inc):
            print(f"  [reset-guard] {fid}: inception changed {loaded_inc} -> {cur_inc} while this "
                  f"run was in flight -- a RESET happened. ABANDONING this run so its stale "
                  f"pre-reset data never overwrites the reset.")
            return True
    return False


def hold_fund_totals(fund, sc, enriched, pos_val, new_positions, deploy_capital, strategy, tag):
    """THE single copy of the oracle/wizard total/cash math (compounding +
    residual cash). Returns (cash, total, pnl, pnl_pct, strategy).

    RESIDUAL CASH IS REAL MONEY: score-weighted sizing leaves a small rounding
    remainder undeployed at every rotation -- it stays in the fund as cash.
    Rotations record strategy.deployed_capital so the residual is exact; a
    capped one-time restore recovers remainders lost by pre-fix seeds.
    Total P&L is SINCE LAUNCH (vs sc) and compounds across rotations.
    """
    _prev_total = float((fund.get("value", {}) or {}).get("total") or sc)
    if new_positions:
        cash = round(max(0.0, deploy_capital - sum(p["cost_basis"] for p in enriched)), 2)
        strategy["deployed_capital"] = round(deploy_capital, 2)
    else:
        cash = float((fund.get("value", {}) or {}).get("cash") or 0)
        if cash == 0 and enriched:
            # RESTORE LOST RESIDUAL (Phase 0 fix, 2026-07-10): the remainder is real
            # money whether or not deployed_capital was recorded. Reference = recorded
            # deployed_capital when present (exact), else sc (pre-fix seeds). The old
            # None-only condition left bitbot13 oracle/wizard $21.62/$23.06 short
            # (VANISHED CASH audit failure) because their seeds DID record 50000.
            _ref   = float((strategy or {}).get("deployed_capital") or sc)
            _resid = round(_ref - sum(p["cost_basis"] for p in enriched), 2)
            if 0 < _resid <= max(50.0, sc * 0.001):
                print(f"  {tag}: restoring ${_resid} rounding residual lost at seed")
                cash = _resid
    total   = (pos_val + cash) if enriched else _prev_total
    pnl     = round(total - sc, 2)
    pnl_pct = (pnl / sc * 100) if sc else 0
    return cash, total, pnl, pnl_pct, strategy


def bot13_bank_flat_day(value, today_iso, day_open, sc):
    """LEDGER IS THE ACCOUNT: when BOT13 finishes a traded day FLAT, bank
    total = day_open + sum(today's SELL realized) -- the exact numbers Trade
    History shows -- and re-derive every dependent field. Mutates and returns
    the value dict. THE single copy of this banking, used by all 3 engines."""
    _tl = value.get("trade_log") or []
    _sold_today = any(str(e.get("action", "")).upper() == "SELL"
                      and str(e.get("ts", ""))[:10] == today_iso for e in _tl)
    if not _sold_today:
        return value
    _realized = round(sum(float(e.get("realized") or 0) for e in _tl
                          if str(e.get("action", "")).upper() == "SELL"
                          and str(e.get("ts", ""))[:10] == today_iso), 2)
    _bank = round(day_open + _realized, 2)
    if abs(_bank - float(value.get("total") or 0)) > 0.005:
        print(f"  [bot13] LEDGER RECONCILE: total {value.get('total')} -> {_bank} "
              f"(day_open {round(day_open,2)} + realized {_realized})")
    value["total"]   = _bank
    value["cash"]    = _bank
    value["pos_val"] = 0.0
    value["pnl"]     = round(_bank - sc, 2)
    value["pnl_pct"] = round((_bank - sc) / sc * 100, 2) if sc else 0
    value["day_pnl"] = round(_bank - day_open, 2)
    value["day_pct"] = round((_bank - day_open) / day_open * 100, 2) if day_open else 0
    return value


def fund_day_fields(total, fid, sc, snapshots, today_iso):
    """THE single copy of the fund-level Today's Change math.

    day_open = the fund's most recent snapshot value strictly before today
    (the reset baseline == sc on day 1, so day_pnl == pnl exactly -- the
    owner's one-day rule). Returns (day_open, day_pnl, day_pct). Used by
    oracle/wizard/equalizer/titan in ALL THREE engines -- this exact formula
    previously existed as nine separate copies.
    """
    _prior = sorted([s for s in (snapshots or [])
                     if s.get("date", "") < today_iso and s.get(fid) is not None],
                    key=lambda s: s.get("date", ""))
    day_open = float(_prior[-1].get(fid)) if _prior else sc
    day_pnl  = total - day_open
    day_pct  = (day_pnl / day_open * 100) if day_open else 0
    return day_open, day_pnl, day_pct
