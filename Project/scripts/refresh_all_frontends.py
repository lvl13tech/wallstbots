#!/usr/bin/env python3
"""
refresh_all_frontends.py
=========================
Runs refresh_wallstbots.py + refresh_bitbot13.py then does a single
git commit+push so Cloudflare Pages deploys both sites at once.

Usage:
    python Project/scripts/refresh_all_frontends.py
    python Project/scripts/refresh_all_frontends.py --no-push   # write files only

Dependencies:
    pip install yfinance requests
"""

import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent

def run(script):
    print(f"\n{'='*60}")
    print(f"  Running {script.name}")
    print(f"{'='*60}")
    result = subprocess.run([sys.executable, str(script)], check=False)
    if result.returncode != 0:
        print(f"  [WARN] {script.name} exited with code {result.returncode}")

def git_push_all():
    git_root = Path(__file__).resolve().parents[2]
    msg = f"auto: wallstbots + bitbot13 data refresh [{dt.datetime.now().strftime('%Y-%m-%d %H:%M')}]"
    try:
        subprocess.run(["git", "-C", str(git_root), "add",
                        "Frontends/wallstbots.tech/data/",
                        "Frontends/bitbot13.tech/data/"], check=True)
        subprocess.run(["git", "-C", str(git_root), "commit", "-m", msg], check=True)
        subprocess.run(["git", "-C", str(git_root), "push"], check=True)
        print("\n[git] pushed both frontends to GitHub ✓")
        print("      Cloudflare Pages will redeploy wallstbots.tech + bitbot13.tech in ~60s")
    except subprocess.CalledProcessError as e:
        print(f"\n[git] push failed: {e}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-push", action="store_true", help="Write files but skip git push")
    args = parser.parse_args()

    run(HERE / "refresh_wallstbots.py")
    run(HERE / "refresh_bitbot13.py")

    if not args.no_push:
        git_push_all()
    else:
        print("\n[skip] --no-push flag set, skipping git push")
        print("       Run 'git add Frontends/*/data/ && git commit -m refresh && git push' manually")

if __name__ == "__main__":
    main()
