#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_bot13_traded_today.py

Prints "YES" only when BOT13 recorded a NEW buy or sell on THIS refresh run,
otherwise "NO". Used by the refresh workflows to decide whether an intraday run
should send a buy/sell alert email.

Why "new this run" (not "any trade today"):
  With 15-minute refreshes a position bought in the morning stays in the
  trade_log all day. Emailing whenever the log merely CONTAINS a trade would
  send an email every 15 minutes. Instead we compare the freshly written
  state.json against a snapshot of the PREVIOUS run's state and only fire when
  the count of BUY/SELL events actually went up.

Usage:
    python check_bot13_traded_today.py <new-state.json> [<prev-state.json>]

If <prev-state.json> is omitted we fall back to `git show HEAD:<new-state.json>`,
but the workflow passes an explicit pre-refresh snapshot (/tmp/prev_state.json)
because the commit step may run before this check.
"""
import json
import subprocess
import sys


def _buysell_count(text):
    try:
        d = json.loads(text)
    except Exception:
        return None
    d = d.get("data", d)
    bot13 = (d.get("funds", {}) or {}).get("bot13", {}) or {}
    value = bot13.get("value", bot13) or {}
    log = value.get("trade_log", []) or []
    return sum(1 for e in log
               if str(e.get("action", "")).upper() in ("BUY", "SELL"))


def main():
    if len(sys.argv) < 2:
        print("NO")
        return
    path = sys.argv[1]
    prev_path = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        with open(path) as f:
            now_count = _buysell_count(f.read())
    except Exception:
        print("NO")
        return
    if now_count is None:
        print("NO")
        return

    prev_count = None
    if prev_path:
        try:
            with open(prev_path) as f:
                prev_count = _buysell_count(f.read())
        except Exception:
            prev_count = None
    else:
        try:
            prev_text = subprocess.run(
                ["git", "show", "HEAD:" + path],
                capture_output=True, text=True, timeout=20
            ).stdout
            prev_count = _buysell_count(prev_text)
        except Exception:
            prev_count = None

    if prev_count is None:
        print("YES" if now_count > 0 else "NO")
        return

    print("YES" if now_count > prev_count else "NO")


if __name__ == "__main__":
    main()
