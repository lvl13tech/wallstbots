"""
deploy_bot13_fix.py
-------------------
Deploys the BOT13 same-day-guard fix:
  1. Git add/commit/push  → Cloudflare auto-deploys bitbot13.tech & wallstbots.tech
  2. FTP upload           → pushes lvl13.tech frontend HTML to HostGator (if changed)

Run this once from any terminal:
    python "C:/Users/temps/OneDrive/Desktop/Claude/Websites/WallStBots/Project/scripts/deploy_bot13_fix.py"
"""

import subprocess
import sys
import os

REPO_DIR = r"C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"
COMMIT_MSG = "Fix BOT13: same-day guard + correct total formula (day_open + sum_pnl)"

def run(cmd, cwd=None):
    print(f"\n> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())
    return result.returncode == 0

print("=" * 60)
print("  BOT13 Fix Deployment")
print("=" * 60)

# ── 1. Git push (Cloudflare auto-deploys from this) ──────────────
print("\n[1/2] Committing and pushing to GitHub...")

run(["git", "add", "-A"], cwd=REPO_DIR)

# Check if there's anything to commit
status = subprocess.run(["git", "status", "--porcelain"], cwd=REPO_DIR,
                        capture_output=True, text=True)
if status.stdout.strip():
    ok = run(["git", "commit", "-m", COMMIT_MSG], cwd=REPO_DIR)
    if not ok:
        print("  ERROR: git commit failed — check output above")
        sys.exit(1)
else:
    print("  Nothing new to commit (already clean)")

ok = run(["git", "push", "origin", "master"], cwd=REPO_DIR)
if ok:
    print("\n  ✓ Pushed to GitHub — Cloudflare will auto-deploy bitbot13.tech and wallstbots.tech")
else:
    print("\n  ERROR: git push failed. Try running manually:")
    print(f'    cd "{REPO_DIR}" && git push origin master')

# ── 2. FTP upload for lvl13.tech ─────────────────────────────────
# The lvl13 refresh_data.py runs locally — no FTP needed for script changes.
# Data files (fund_*.json) are uploaded by the refresh script itself on each run.
# If you need to redeploy the lvl13.tech frontend HTML, use the FTP refresh script.
print("\n[2/2] lvl13.tech note:")
print("  - refresh_data.py runs locally → fix is live on next scheduled run")
print("  - To force a fresh data push, run the lvl13 refresh script manually")

print("\n" + "=" * 60)
print("  Done! On the next refresh run, BOT13 will:")
print("  • Size positions using day_open as capital (not inflated total)")
print("  • Never re-create positions mid-day (same_day guard active)")
print("  • Total = day_open + sum(holdings P&L) — matches receipts exactly")
print("=" * 60)
