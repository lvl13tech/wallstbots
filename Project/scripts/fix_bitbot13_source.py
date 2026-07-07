#!/usr/bin/env python3
"""
fix_bitbot13_source.py -- RETIRED (2026-07-07 root-cause audit). DO NOT USE.

This was the one-time 2026-06 fix for the JUP price-inflation bug. It writes
Frontends/bitbot13.tech/data/state.json and pushes to the backend -- meaning if it
were ever run again it would inject old-era data over the live state. The bug it
fixed is permanently closed at the source now (bad-data price guards in the engine
+ the audit's price/entry sanity band), and the ONE correct reset path is:

    python Project/scripts/full_reset_all.py --platform bitbot13

Owner rule (2026-07-07): resets and day-1 code must never read or write prior-day
data -- retired tools that can do so refuse to run.
"""
import sys

print(__doc__)
print("REFUSED: retired. Use  python Project/scripts/full_reset_all.py --platform bitbot13")
sys.exit(1)
