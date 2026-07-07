#!/usr/bin/env python3
"""
reset_lvl13.py -- RETIRED (2026-07-07 root-cause audit). DO NOT USE.

This tool predates the platform migration: the AI/quantum trading site moved from
lvl13.tech to aistocks.tech, and lvl13.tech is now STRICTLY the parent company
landing page (CLAUDE.md Rule 10: hands off lvl13). Running this would write a
trading state under the legacy 'lvl13' platform key -- stale-era data with no
consumer, and one more script capable of injecting old-shaped data into the system.

The ONE correct reset path for the product sites is:

    python Project/scripts/full_reset_all.py --platform <wallstbots|aistocks|bitbot13>
    python Project/scripts/full_reset_all.py --all
"""
import sys

print(__doc__)
print("REFUSED: retired. Use  python Project/scripts/full_reset_all.py")
sys.exit(1)
