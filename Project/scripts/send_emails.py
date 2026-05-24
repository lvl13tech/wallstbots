"""
send_emails.py
--------------
Dispatch script — run after each refresh to send email notifications.

Usage (GitHub Actions):
  python Project/scripts/send_emails.py --platform wallstbots [--weekly] [--monthly]

Environment variables required:
  RESEND_API_KEY      — from Resend dashboard
  INTERNAL_API_KEY    — same key used by refresh scripts to call backend
  BACKEND_URL         — e.g. https://wallstbots-api-xxxx.run.app

The script:
  1. Reads the platform's state.json + signals.json from Frontends/
  2. Calls the backend /admin/email-subscribers to get all opted-in users
  3. Sends daily signals to all, weekly on Mondays, monthly on the 1st
  4. For paid members, includes their personal portfolio signals
"""

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

import requests

# Add scripts dir to path so we can import email_service
sys.path.insert(0, str(Path(__file__).parent))
from email_service import (
    send_batch,
    build_daily_signals_email,
    build_bot13_alert_email,
    build_weekly_email,
    build_monthly_email,
    SITE_NAMES,
)

BACKEND_URL      = os.environ.get("BACKEND_URL", "").rstrip("/")
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")

PLATFORM_DATA_PATHS = {
    "wallstbots": Path("Frontends/wallstbots.tech/data"),
    "bitbot13":   Path("Frontends/bitbot13.tech/data"),
    "lvl13":      Path("Frontends/lvl13.tech/data"),
}


def load_data(platform: str) -> tuple[dict, dict]:
    """Load state.json and signals.json for a platform."""
    base = PLATFORM_DATA_PATHS[platform]
    state   = json.loads((base / "state.json").read_text())["data"]
    signals_raw = json.loads((base / "signals.json").read_text())
    signals = signals_raw.get("data", {}).get("recommendations", [])
    return state, signals


def get_subscribers(platform: str) -> list[dict]:
    """
    Fetch all opted-in email subscribers from backend.
    Returns list of dicts: {email, first_name, tier, email_source,
                             email_daily, email_bot13, email_weekly, email_monthly,
                             portfolio_holdings: [symbol, ...]}
    """
    if not BACKEND_URL or not INTERNAL_API_KEY:
        print("[send_emails] WARNING: BACKEND_URL or INTERNAL_API_KEY not set — skipping subscriber fetch")
        return []
    try:
        resp = requests.get(
            f"{BACKEND_URL}/admin/email-subscribers",
            params={"platform": platform},
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


def match_portfolio_signals(holdings: list[str], all_signals: list[dict]) -> list[dict]:
    """Return signals that match the user's portfolio holdings."""
    sym_set = {s.upper() for s in holdings}
    return [s for s in all_signals if s.get("symbol","").upper() in sym_set]


def run(platform: str, is_weekly: bool = False, is_monthly: bool = False):
    today = date.today()
    print(f"[send_emails] {platform} | {today} | weekly={is_weekly} monthly={is_monthly}")

    state, all_signals = load_data(platform)
    funds      = state.get("funds", {})
    leaderboard = state.get("leaderboards", {}).get("week", [])

    bot13_strategy  = funds.get("bot13", {}).get("current_strategy", {})
    oracle_strategy = funds.get("oracle", {}).get("current_strategy", {})
    wizard_strategy = funds.get("wizard", {}).get("current_strategy", {})

    subscribers = get_subscribers(platform)
    print(f"[send_emails] {len(subscribers)} subscriber(s) found")

    if not subscribers:
        print("[send_emails] No subscribers — done.")
        return

    daily_recipients  = []
    bot13_recipients  = []
    weekly_recipients = []
    monthly_recipients = []

    bot13_traded = bot13_strategy.get("decision") == "TRADE"

    for sub in subscribers:
        if not sub.get("email"):
            continue

        # Attach personal portfolio signals
        holdings = sub.get("portfolio_holdings", [])
        sub["portfolio_signals"] = match_portfolio_signals(holdings, all_signals)

        if sub.get("email_daily", True):
            daily_recipients.append(sub)
        if sub.get("email_bot13", True) and bot13_traded:
            bot13_recipients.append(sub)
        if is_weekly and sub.get("email_weekly", True):
            weekly_recipients.append(sub)
        if is_monthly and sub.get("email_monthly", True):
            monthly_recipients.append(sub)

    site_name = SITE_NAMES[platform]

    # ── Daily signals ──────────────────────────────────────────────
    if daily_recipients:
        print(f"[send_emails] Sending daily signals to {len(daily_recipients)} subscriber(s)...")
        result = send_batch(
            daily_recipients,
            f"{site_name} · Daily Signals — {today.strftime('%b %d')}",
            lambda r: build_daily_signals_email(
                platform, all_signals, bot13_strategy, leaderboard, r
            ),
        )
        print(f"[send_emails] Daily: sent={result['sent']} failed={result['failed']}")

    # ── Bot13 trade alert ──────────────────────────────────────────
    if bot13_recipients:
        picks = bot13_strategy.get("picks", [])
        n_pos = len(picks)
        print(f"[send_emails] Sending Bot13 trade alert to {len(bot13_recipients)} subscriber(s)...")
        result = send_batch(
            bot13_recipients,
            f"BOT13 TRADE ALERT · {n_pos} position{'s' if n_pos!=1 else ''} entered",
            lambda r: build_bot13_alert_email(platform, bot13_strategy, r),
        )
        print(f"[send_emails] Bot13 alert: sent={result['sent']} failed={result['failed']}")

    # ── Weekly picks ───────────────────────────────────────────────
    if weekly_recipients:
        print(f"[send_emails] Sending weekly picks to {len(weekly_recipients)} subscriber(s)...")
        result = send_batch(
            weekly_recipients,
            f"{site_name} · Oracle's Weekly Picks — {today.strftime('%b %d')}",
            lambda r: build_weekly_email(platform, oracle_strategy, leaderboard, r),
        )
        print(f"[send_emails] Weekly: sent={result['sent']} failed={result['failed']}")

    # ── Monthly picks ──────────────────────────────────────────────
    if monthly_recipients:
        print(f"[send_emails] Sending monthly picks to {len(monthly_recipients)} subscriber(s)...")
        result = send_batch(
            monthly_recipients,
            f"{site_name} · Wizard's Monthly Picks — {today.strftime('%B %Y')}",
            lambda r: build_monthly_email(platform, wizard_strategy, leaderboard, r),
        )
        print(f"[send_emails] Monthly: sent={result['sent']} failed={result['failed']}")

    print("[send_emails] Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", required=True, choices=["wallstbots","bitbot13","lvl13"])
    parser.add_argument("--weekly",  action="store_true", help="Also send Oracle weekly picks")
    parser.add_argument("--monthly", action="store_true", help="Also send Wizard monthly picks")
    args = parser.parse_args()

    today = date.today()
    is_monday = today.weekday() == 0   # auto-detect Monday for weekly
    is_first  = today.day == 1         # auto-detect 1st of month for monthly

    run(
        platform  = args.platform,
        is_weekly = args.weekly or is_monday,
        is_monthly = args.monthly or is_first,
    )
