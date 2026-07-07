#!/usr/bin/env python3
"""
full_reset_bitbot13.py -- SUPERSEDED (2026-07-06 root-cause audit). DO NOT USE.

This script carried the exact bug that re-corrupted member data after every daily
reset: it wrote the PLATFORM's $50,000 starting capital into every member portfolio
(lines that read `"total_value": START_CAP, "entry_cost": START_CAP`) instead of the
member's own N holdings x $1,000. Keeping two reset tools means two places for that
bug to live -- so this one now refuses to run.

The ONE correct reset path is:

    python Project/scripts/full_reset_all.py --platform bitbot13
    python Project/scripts/full_reset_all.py --all

full_reset_all.py resets every layer correctly:
  - backend cache zeroed, snapshots hard-deleted, one clean baseline row
  - stale day_boundary block removed (day 1 references NO prior-day data)
  - DISK state.json written clean for ALL 3 platforms (every engine reads disk first)
  - member portfolios reset at their OWN N x $1,000 in the engine's PENDING shape
    (first real entries at the next session -- the engines honor PENDING)
  - engines carry a reset-collision guard, so an in-flight refresh can never
    overwrite a reset with pre-reset data
"""
import sys

print(__doc__)
print("REFUSED: superseded. Use  python Project/scripts/full_reset_all.py --platform bitbot13")
sys.exit(1)
