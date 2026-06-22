#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_bot13_traded_today.py

Prints "YES" if BOT13 recorded a real BUY or SELL *today* (ET) in its trade_log,
otherwise "NO". Used by the refresh workflows to decide whether a MIDDAY / CLOSE
run should send a trade-alert email.

The morning run always emails (day's signals + decision) and does NOT use this.
Only the later intraday runs gate on this so members are emailed ONLY when the
bot actually bought or sold -- never on a plain "still holding" refresh.

Reads the local data-dir state.json the refresh just wrote:
    <site>/data/state.json -> data.funds.bot13.value.trade_log[]
Each event looks like: {"ts": "2026-06-22T15:25:00", "action": "BUY"|"SELL", ...}
"ts" is ET (the codebase stamps ET via et_now()), so we compare its date to ET today.

Usage:  python check_bot13_traded_today.py <path-to-state.json>
"""
import json
import sys
import datetime as dt


def et_today_iso():
    """ET calendar date (DST-aware), matching bot13_engine.et_now()."""
    utc = dt.datetime.utcnow()
    year = utc.year
    march1 = dt.date(year, 3, 1)
    dst_on = march1 + dt.timedelta(days=(6 - march1.weekday()) % 7 + 7)
    nov1 = dt.date(year, 11, 1)
    dst_off = nov1 + dt.timedelta(days=(6 - nov1.weekday()) % 7)
    offset = -4 if dst_on <= utc.date() < dst_off else -5
    return (utc + dt.timedelta(hours=offset)).date().isoformat()


def main():
    if len(sys.argv) < 2:
        print("NO")
        return
    try:
        with open(sys.argv[1]) as f:
            d = json.load(f)
    except Exception:
        print("NO")
        return

    d = d.get("data", d)
    bot13 = (d.get("funds", {}) or {}).get("bot13", {}) or {}
    value = bot13.get("value", bot13) or {}
    log = value.get("trade_log", []) or []

    today = et_today_iso()
    for e in log:
        action = str(e.get("action", "")).upper()
        ts = str(e.get("ts", ""))[:10]
        if ts == today and action in ("BUY", "SELL"):
            print("YES")
            return
    print("NO")


if __name__ == "__main__":
    main()
