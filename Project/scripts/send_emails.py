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
from zoneinfo import ZoneInfo

def _et_today():
    """Current date in US/Eastern (DST-aware). Use instead of date.today()."""
    return datetime.now(ZoneInfo("America/New_York")).date()
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from email_service import (
    send_batch,
    build_consolidated_email,
    build_open_email,
    build_trade_alert_email,
    build_closeout_email,
    SITE_NAMES,
)

BACKEND_URL      = os.environ.get("BACKEND_URL", "").rstrip("/")
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")
FORCE_SEND       = os.environ.get("FORCE_SEND", "").lower() in ("1", "true", "yes")

# -- Once-per-ET-day markers (per email kind) ----------------------------------
# Each daily-cadence email (open digest, stock close-out, crypto close-out) must
# go out exactly ONCE per ET day, on the first qualifying run -- regardless of
# which trigger fires it (GitHub cron, cron-job.org backup, or a re-run). We
# record the ET date of the last successful send per kind in a small committed
# file; later runs that day see the marker and skip. This replaces the old
# fragile "HOUR==13 && MIN<45" gate that depended on a single cron tick.
# (Intraday trade alerts are NOT date-gated -- they fire per new-activity run.)
_MARKER_DIR = Path("Frontends/wallstbots.tech/data")
MARKERS = {
    "open":         _MARKER_DIR / ".email_open_sent",
    "close-stock":  _MARKER_DIR / ".email_closestock_sent",
    "close-crypto": _MARKER_DIR / ".email_closecrypto_sent",
}


def _already_sent_today(kind: str) -> bool:
    m = MARKERS.get(kind)
    if not m:
        return False
    try:
        return m.read_text().strip() == _et_today().isoformat()
    except Exception:
        return False


def _mark_sent_today(kind: str) -> None:
    m = MARKERS.get(kind)
    if not m:
        return
    try:
        m.parent.mkdir(parents=True, exist_ok=True)
        m.write_text(_et_today().isoformat())
        print(f"[send_emails] marker written: {kind} = {_et_today().isoformat()}")
    except Exception as e:
        print(f"[send_emails] WARNING: could not write {kind} marker: {e}")

PLATFORM_DATA_PATHS = {
    "wallstbots": Path("Frontends/wallstbots.tech/data"),
    "bitbot13":   Path("Frontends/bitbot13.tech/data"),
    # NOTE: the "lvl13" email section is the AI/quantum site, now aistocks.tech.
    # After the lvl13->aistocks migration aistocks data lives ONLY in the backend
    # API (no committed JSON), so it is fetched over HTTP below, not from disk.
}

# The AI/quantum section ("lvl13" key) reads from the backend, keyed by this platform.
AISTOCKS_PLATFORM = "aistocks"


def _load_platform_from_backend(platform: str) -> dict:
    """Fetch state + signals for a platform from the backend tracker API.
    Used for aistocks, whose data is no longer committed as local JSON."""
    if not BACKEND_URL:
        print(f"[send_emails] WARNING: BACKEND_URL not set; cannot load {platform} from backend")
        return {"funds": {}, "leaderboard": [], "signals": [], "is_fresh": False, "last_updated": "unknown"}
    try:
        sr = requests.get(f"{BACKEND_URL}/public/tracker/state?platform={platform}", timeout=20)
        nr = requests.get(f"{BACKEND_URL}/public/tracker/signals?platform={platform}", timeout=20)
        state   = (sr.json().get("data", {}) if sr.status_code == 200 else {}) or {}
        signals = []
        if nr.status_code == 200:
            signals = (nr.json().get("data", {}) or {}).get("recommendations", []) or []
        ts_str = state.get("last_refresh") or state.get("last_updated")
        is_fresh = True
        if ts_str:
            try:
                is_fresh = (datetime.fromisoformat(ts_str).date() == _et_today())
            except Exception:
                pass
        if not is_fresh and FORCE_SEND:
            is_fresh = True
        return {
            "funds":        state.get("funds", {}),
            "leaderboard":  state.get("leaderboards", {}).get("week", []),
            "signals":      signals,
            "is_fresh":     is_fresh,
            "last_updated": ts_str or "unknown",
        }
    except Exception as e:
        print(f"[send_emails] WARNING: could not load {platform} from backend: {e}")
        return {"funds": {}, "leaderboard": [], "signals": [], "is_fresh": False, "last_updated": "unknown"}


def load_platform_data(platform: str) -> dict:
    """Load state.json + signals.json for a platform. Returns a normalised dict.
    The AI/quantum section (key "lvl13") is read from the aistocks backend API,
    since that data is no longer committed to disk after the migration."""
    if platform == "lvl13":
        return _load_platform_from_backend(AISTOCKS_PLATFORM)
    base = PLATFORM_DATA_PATHS[platform]
    try:
        state_raw   = json.loads((base / "state.json").read_text())
        signals_raw = json.loads((base / "signals.json").read_text())
    except Exception as e:
        print(f"[send_emails] WARNING: could not load {platform} data: {e}")
        return {"funds": {}, "leaderboard": [], "signals": [], "is_fresh": False, "last_updated": "unknown"}

    state   = state_raw.get("data", state_raw)
    signals = signals_raw.get("data", {}).get("recommendations", [])

    # -- Staleness check -------------------------------------------------------
    # wallstbots / lvl13 use "last_refresh"; bitbot13 uses "last_updated".
    # Compare the data's date to today (UTC). If it's from a prior day the
    # platform section is suppressed so stale Friday data never appears in a
    # weekend email.
    ts_str   = state.get("last_refresh") or state.get("last_updated")
    is_fresh = True   # default: assume fresh if we can't parse the timestamp
    if ts_str:
        try:
            data_date = datetime.fromisoformat(ts_str).date()
            is_fresh  = (data_date == _et_today())
        except Exception:
            pass
    if not is_fresh:
        if FORCE_SEND:
            is_fresh = True  # override staleness on manual/forced runs
            print(f"[send_emails] {platform}: data is stale but FORCE_SEND=true — sending anyway")
        else:
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


def _is_weekend() -> bool:
    return _et_today().weekday() >= 5  # Sat=5, Sun=6


def _platforms_for_today():
    """Site platforms whose markets are open today (email-content keys)."""
    if _is_weekend():
        return ["bitbot13"]                      # crypto only on weekends
    return ["wallstbots", "lvl13", "bitbot13"]   # lvl13 key == aistocks section


def _prep_subscribers(platform_data):
    """Fetch subscribers and attach matched signals + per-member bot13 activity."""
    subscribers = get_subscribers()
    print(f"[send_emails] {len(subscribers)} subscriber(s) found")
    out = []
    for sub in subscribers:
        if not sub.get("email"):
            continue
        for plat in ("wallstbots", "bitbot13", "lvl13"):
            holdings = sub.get(f"holdings_{plat}", [])
            signals  = platform_data[plat]["signals"]
            sub[f"portfolio_signals_{plat}"] = match_signals(holdings, signals)
        out.append(sub)
    return out


def _site_closed_out(platform_data, platforms) -> bool:
    """True if BOT13 has closed out (window closed AND flat) on any given platform
    today. Used to gate the close-out emails so they only fire after the real close."""
    for plat in platforms:
        pdata = platform_data.get(plat, {})
        funds = pdata.get("funds", {})
        b13   = funds.get("bot13") or {}
        val   = b13.get("value") or b13
        window_open  = val.get("window_open", True)
        traded_today = val.get("traded_today", False)
        holding_cash = val.get("holding_cash", False)
        # Closed out = market window is closed, it traded today, now in cash.
        if (window_open is False) and traded_today and holding_cash:
            return True
    return False


def _member_has_activity(sub, platforms, want_closeout=False) -> bool:
    """True if this member's BOT13 traded (or closed out) on any of `platforms`."""
    for plat in platforms:
        act = sub.get(f"bot13_activity_{plat}") or {}
        if want_closeout:
            if act.get("closed_out"):
                return True
        else:
            if act.get("traded_today"):
                return True
    return False


def run(kind: str = "open", is_weekly: bool = False, is_monthly: bool = False,
        weekend_only: bool = False):
    today   = _et_today()
    weekend = _is_weekend()
    print(f"[send_emails] kind={kind} | {today} | weekend={weekend} | weekly={is_weekly} monthly={is_monthly} | force={FORCE_SEND}")

    platform_data = {p: load_platform_data(p) for p in ("wallstbots", "bitbot13", "lvl13")}
    subscribers   = _prep_subscribers(platform_data)
    if not subscribers:
        print("[send_emails] No subscribers — done.")
        return

    # ---- OPEN digest (A weekday / B weekend) --------------------------------
    if kind == "open":
        if weekend_only and not weekend:
            print("[send_emails] open: weekend-only run on a weekday — skipping (wallstbots owns weekday open).")
            return
        if _already_sent_today("open") and not FORCE_SEND:
            print("[send_emails] open email already sent today — skipping.")
            return
        recipients = [s for s in subscribers if s.get("email_daily", True)]
        if not recipients:
            print("[send_emails] open: no daily recipients."); return
        label   = today.strftime('%b %d')
        subject = (f"Weekend Crypto Signals — {label}" if weekend
                   else f"Your Daily Trading Signals — {label}")
        result = send_batch(
            recipients, subject,
            lambda r: build_open_email(r, platform_data, weekend, is_weekly, is_monthly),
        )
        print(f"[send_emails] open: sent={result['sent']} failed={result['failed']}")
        if result["sent"] > 0:
            _mark_sent_today("open")
        else:
            print("[send_emails] open: nothing sent — marker NOT written; will retry.")
        return

    # ---- INTRADAY trade alert (C) -- not date-gated, per new activity --------
    if kind == "trade":
        platforms = ["bitbot13"] if weekend else ["wallstbots", "lvl13", "bitbot13"]
        recipients = [s for s in subscribers
                      if s.get("email_bot13_alerts", True)
                      and _member_has_activity(s, platforms, want_closeout=False)]
        if not recipients:
            print("[send_emails] trade: no members with new BOT13 activity this run — skipping.")
            return
        subject = f"BOT13 Trade Alert — {today.strftime('%b %d')}"
        result = send_batch(
            recipients, subject,
            lambda r: build_trade_alert_email(r, platform_data, platforms),
        )
        print(f"[send_emails] trade: sent={result['sent']} failed={result['failed']}")
        return

    # ---- STOCK close-out (D) -- wallstbots + aistocks -----------------------
    if kind == "close-stock":
        if weekend:
            print("[send_emails] close-stock: weekend — stocks don't trade; skipping.")
            return
        if _already_sent_today("close-stock") and not FORCE_SEND:
            print("[send_emails] close-stock already sent today — skipping.")
            return
        platforms = ["wallstbots", "lvl13"]
        if not _site_closed_out(platform_data, platforms) and not FORCE_SEND:
            print("[send_emails] close-stock: stocks not closed out yet — skipping.")
            return
        recipients = [s for s in subscribers if s.get("email_daily", True)]
        result = send_batch(
            recipients, f"Markets Closed — BOT13 Stock Positions Flat — {today.strftime('%b %d')}",
            lambda r: build_closeout_email(r, platform_data, platforms, "stock"),
        )
        print(f"[send_emails] close-stock: sent={result['sent']} failed={result['failed']}")
        if result["sent"] > 0:
            _mark_sent_today("close-stock")
        return

    # ---- CRYPTO close-out (E) -- bitbot13 -----------------------------------
    if kind == "close-crypto":
        if _already_sent_today("close-crypto") and not FORCE_SEND:
            print("[send_emails] close-crypto already sent today — skipping.")
            return
        platforms = ["bitbot13"]
        if not _site_closed_out(platform_data, platforms) and not FORCE_SEND:
            print("[send_emails] close-crypto: crypto not closed out yet — skipping.")
            return
        recipients = [s for s in subscribers if s.get("email_daily", True)]
        result = send_batch(
            recipients, f"BitBot13 Session Closed — Positions Flat — {today.strftime('%b %d')}",
            lambda r: build_closeout_email(r, platform_data, platforms, "crypto"),
        )
        print(f"[send_emails] close-crypto: sent={result['sent']} failed={result['failed']}")
        if result["sent"] > 0:
            _mark_sent_today("close-crypto")
        return

    print(f"[send_emails] Unknown kind '{kind}' — nothing sent.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", default="open",
                        choices=["open", "trade", "close-stock", "close-crypto"],
                        help="which email to dispatch")
    parser.add_argument("--weekly",  action="store_true")
    parser.add_argument("--monthly", action="store_true")
    parser.add_argument("--force",   action="store_true",
                        help="bypass once-per-day markers (manual/test sends)")
    parser.add_argument("--weekend-only", action="store_true",
                        help="for --kind open: only send on Sat/Sun (bitbot13 weekend owner)")
    args = parser.parse_args()
    if args.force:
        FORCE_SEND = True  # noqa: F841  (module-level flag read by the gates)

    today     = _et_today()
    is_monday = today.weekday() == 0
    is_first  = today.day == 1

    run(
        kind         = args.kind,
        is_weekly    = args.weekly  or is_monday,
        is_monthly   = args.monthly or is_first,
        weekend_only = args.weekend_only,
    )
