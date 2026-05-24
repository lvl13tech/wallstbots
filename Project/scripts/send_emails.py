"""
send_emails.py
--------------
Consolidated daily email dispatch — ONE email per user covering all three sites.

Usage (GitHub Actions — called only from refresh-wallstbots.yml):
  python Project/scripts/send_emails.py [--weekly] [--monthly]

Environment variables required:
  RESEND_API_KEY      — from Resend dashboard
  INTERNAL_API_KEY    — same key used by refresh scripts to call backend
  BACKEND_URL         — e.g. https://wallstbots-api-xxxx.run.app

The email structure (user-controllable):
  1. Portfolio signals  — the user's own holdings across all platforms
  2. Wall St. Bots      — stocks/market BOT13 decision + top signals
  3. BitBot13           — crypto BOT13 decision + top signals
  4. Level XIII         — AI/quantum BOT13 decision + top signals
"""

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from email_service import (
    send_batch,
    build_consolidated_email,
    SITE_NAMES,
)

BACKEND_URL      = os.environ.get("BACKEND_URL", "").rstrip("/")
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")

PLATFORM_DATA_PATHS = {
    "wallstbots": Path("Frontends/wallstbots.tech/data"),
    "bitbot13":   Path("Frontends/bitbot13.tech/data"),
    "lvl13":      Path("Frontends/lvl13.tech/data"),
}


def load_platform_data(platform: str) -> dict:
    """Load state.json + signals.json for a platform. Returns a normalised dict."""
    base = PLATFORM_DATA_PATHS[platform]
    try:
        state_raw   = json.loads((base / "state.json").read_text())
        signals_raw = json.loads((base / "signals.json").read_text())
    except Exception as e:
        print(f"[send_emails] WARNING: could not load {platform} data: {e}")
        return {"funds": {}, "leaderboard": [], "signals": [], "is_fresh": False, "last_updated": "unknown"}

    state   = state_raw.get("data", state_raw)
    signals = signals_raw.get("data", {}).get("recommendations", [])

    # ── Staleness check ───────────────────────────────────────────────────────
    # wallstbots / lvl13 use "last_refresh"; bitbot13 uses "last_updated".
    # Compare the data's date to today (UTC). If it's from a prior day the
    # platform section is suppressed so stale Friday data never appears in a
    # weekend email.
    ts_str   = state.get("last_refresh") or state.get("last_updated")
    is_fresh = True   # default: assume fresh if we can't parse the timestamp
    if ts_str:
        try:
            data_date = datetime.fromisoformat(ts_str).date()
            is_fresh  = (data_date == date.today())
        except Exception:
            pass
    if not is_fresh:
        print(f"[send_emails] {platform}: data is stale (last updated {ts_str}) — section will be suppressed")

    return {
        "funds":        state.get("funds", {}),
        "leaderboard":  state.get("leaderboards", {}).get("week", []),
        "signals":      signals,
        "is_fresh":     is_fresh,
        "last_updated": ts_str or "unknown",
    }


def get_subscribers() -> list[dict]:
    """Fetch all opted-in subscribers from backend (platform-agnostic)."""
    if not BACKEND_URL or not INTERNAL_API_KEY:
        print("[send_emails] WARNING: BACKEND_URL or INTERNAL_API_KEY not set — skipping")
        return []
    try:
        resp = requests.get(
            f"{BACKEND_URL}/admin/email-subscribers",
            headers={"X-Internal-Key": INTERNAL_API_KEY},
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"[send_emails] backend returned {resp.status_code}: {resp.text[:200]}")
            return []
        return resp.json().get("subscribers", [])
    except Exception as e:
        print(f"[send_emails] Failed to fetch subscribers: {e}")
        return []


def match_signals(holdings: list[str], all_signals: list[dict]) -> list[dict]:
    """Return signals that match the user's portfolio holdings."""
    sym_set = {s.upper() for s in holdings}
    return [s for s in all_signals if s.get("symbol", "").upper() in sym_set]


def run(is_weekly: bool = False, is_monthly: bool = False):
    today = date.today()
    print(f"[send_emails] consolidated | {today} | weekly={is_weekly} monthly={is_monthly}")

    # Load all three platforms
    platform_data = {p: load_platform_data(p) for p in ("wallstbots", "bitbot13", "lvl13")}

    subscribers = get_subscribers()
    print(f"[send_emails] {len(subscribers)} subscriber(s) found")
    if not subscribers:
        print("[send_emails] No subscribers — done.")
        return

    daily_recipients   = []
    weekly_recipients  = []
    monthly_recipients = []

    for sub in subscribers:
        if not sub.get("email"):
            continue

        # Attach per-platform portfolio signals
        for plat in ("wallstbots", "bitbot13", "lvl13"):
            holdings = sub.get(f"holdings_{plat}", [])
            signals  = platform_data[plat]["signals"]
            sub[f"portfolio_signals_{plat}"] = match_signals(holdings, signals)

        if sub.get("email_daily", True):
            daily_recipients.append(sub)
        if is_weekly and sub.get("email_weekly", True):
            weekly_recipients.append(sub)
        if is_monthly and sub.get("email_monthly", True):
            monthly_recipients.append(sub)

    # ── Daily consolidated email ───────────────────────────────────────────────
    if daily_recipients:
        print(f"[send_emails] Sending consolidated daily email to {len(daily_recipients)} subscriber(s)...")
        subject = f"Your Daily Trading Signals — {today.strftime('%b %d')}"
        result = send_batch(
            daily_recipients,
            subject,
            lambda r: build_consolidated_email(r, platform_data, is_weekly, is_monthly),
        )
        print(f"[send_emails] Daily: sent={result['sent']} failed={result['failed']}")

    print("[send_emails] Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--weekly",  action="store_true")
    parser.add_argument("--monthly", action="store_true")
    args = parser.parse_args()

    today      = date.today()
    is_monday  = today.weekday() == 0
    is_first   = today.day == 1

    run(
        is_weekly  = args.weekly  or is_monday,
        is_monthly = args.monthly or is_first,
    )
