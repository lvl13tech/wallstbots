#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diag_email.py — read-only email troubleshooting.

Reads api_url + internal_api_key from Project/config/secrets.json, calls the live
backend, and reports whether the owner is returned as an enabled subscriber, the
aistocks data, and (if RESEND_API_KEY is set in the environment) does a real
Resend test send so the actual API response is visible.

Run from repo root:  python Project/scripts/diag_email.py
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
secrets = {}
sp = ROOT / "Project" / "config" / "secrets.json"
if sp.exists():
    secrets = json.loads(sp.read_text())

BACKEND = (secrets.get("api_url") or os.environ.get("BACKEND_URL", "")).rstrip("/")
KEY     = secrets.get("internal_api_key") or os.environ.get("INTERNAL_API_KEY", "")

print("=== CONFIG ===")
print("BACKEND_URL:", BACKEND or "(MISSING)")
print("INTERNAL_API_KEY present:", "yes" if KEY else "NO")
print()

print("=== STEP 1: /admin/email-subscribers ===")
subs = []
try:
    req = urllib.request.Request(BACKEND + "/admin/email-subscribers",
                                 headers={"X-Internal-Key": KEY})
    r = urllib.request.urlopen(req, timeout=30)
    data = json.load(r)
    subs = data.get("subscribers", [])
    print("HTTP 200 | subscriber count:", len(subs))
    for s in subs:
        print(" -", s.get("email"),
              "| email_daily=", s.get("email_daily"),
              "| bot13_alerts=", s.get("email_bot13_alerts"),
              "| holdings wsb/btc/ai=",
              len(s.get("holdings_wallstbots", [])),
              len(s.get("holdings_bitbot13", [])),
              len(s.get("holdings_lvl13", [])))
        for plat in ("wallstbots", "bitbot13", "lvl13"):
            act = s.get("bot13_activity_" + plat) or {}
            if act:
                print("      ", plat, "traded=", act.get("traded_today"),
                      "closed=", act.get("closed_out"),
                      "rows=", len(act.get("trade_log", [])))
    if not subs:
        print("!! ZERO SUBSCRIBERS -> this alone explains zero emails.")
except urllib.error.HTTPError as e:
    print("HTTP ERROR", e.code)
    try:
        print("BODY:", e.read().decode()[:500])
    except Exception:
        pass
    print("!! The subscriber endpoint is failing -> get_subscribers() returns [] -> no emails.")
except Exception as e:
    print("ERROR:", repr(e))
print()

print("=== STEP 2: aistocks data from backend ===")
for dt in ("state", "signals"):
    try:
        r = urllib.request.urlopen(BACKEND + f"/public/tracker/{dt}?platform=aistocks", timeout=20)
        d = json.load(r).get("data", {})
        if dt == "state":
            print("  state funds:", list((d.get("funds") or {}).keys()),
                  "| last_refresh:", d.get("last_refresh"))
        else:
            print("  signals:", len((d or {}).get("recommendations", [])))
    except Exception as e:
        print(f"  {dt} ERROR:", repr(e))
print()

print("=== STEP 3: live Resend test send ===")
rkey = os.environ.get("RESEND_API_KEY", "")
if not rkey:
    print("  RESEND_API_KEY not set in env — skipping live send.")
    print("  To test delivery: set RESEND_API_KEY=re_xxxx  then re-run.")
else:
    to = subs[0]["email"] if subs else os.environ.get("TEST_TO", "")
    if not to:
        print("  No recipient available (no subscribers, no TEST_TO).")
    else:
        body = json.dumps({
            "from": "Wall St. Bots <info@lvl13.tech>",
            "to": [to],
            "subject": "WallStBots email diagnostic",
            "html": "<p>Diagnostic test send — if you got this, Resend delivery works.</p>",
        }).encode()
        req = urllib.request.Request("https://api.resend.com/emails", data=body,
              headers={"Authorization": "Bearer " + rkey, "Content-Type": "application/json"})
        try:
            r = urllib.request.urlopen(req, timeout=20)
            print("  RESEND OK:", r.status, r.read().decode()[:200])
            print("  -> Resend delivery works. If scheduled emails still don't arrive, the")
            print("     cause is the workflow not running the email step (check Actions logs).")
        except urllib.error.HTTPError as e:
            print("  RESEND REJECTED:", e.code)
            try:
                print("  BODY:", e.read().decode()[:400])
            except Exception:
                pass
            print("  -> This is why no emails arrive (often: domain not verified).")
        except Exception as e:
            print("  RESEND ERROR:", repr(e))
print()
print("=== DONE ===")
