#!/usr/bin/env python3
"""
seed_tracker_db.py
One-shot script: reads the existing JSON data files and pushes them
to the Cloud Run backend so the tracker_live_data table is populated.

Run from anywhere on your machine:
    python Project/scripts/seed_tracker_db.py
"""
import json
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' not installed. Run: pip install requests")
    sys.exit(1)

ROOT        = Path(__file__).resolve().parents[1]
DATA_DIR    = ROOT / "public_html" / "data"
SECRETS     = ROOT / "config" / "secrets.json"

# ── Load secrets ─────────────────────────────────────────────────────────────
if not SECRETS.exists():
    print(f"ERROR: secrets.json not found at {SECRETS}")
    sys.exit(1)

cfg         = json.loads(SECRETS.read_text())
API_URL     = cfg.get("api_url", "").rstrip("/")
API_KEY     = cfg.get("internal_api_key", "")
PLATFORM    = cfg.get("platform", "lvl13")

if not API_URL or not API_KEY:
    print("ERROR: api_url or internal_api_key missing in secrets.json")
    sys.exit(1)

ENDPOINT = f"{API_URL}/internal/tracker/push"
HEADERS  = {
    "Content-Type":  "application/json",
    "X-Internal-Key": API_KEY,
}

# ── Push each data file ───────────────────────────────────────────────────────
FILES = {
    "state":   DATA_DIR / "state.json",
    "news":    DATA_DIR / "news.json",
    "signals": DATA_DIR / "signals.json",
    "reports": DATA_DIR / "reports.json",
}

ok = 0
for data_type, path in FILES.items():
    if not path.exists():
        print(f"  SKIP  {data_type} — file not found: {path}")
        continue

    payload = json.loads(path.read_text())

    body = {
        "platform":  PLATFORM,
        "data_type": data_type,
        "data":      payload,
    }

    try:
        r = requests.post(ENDPOINT, headers=HEADERS, json=body, timeout=30)
        if r.status_code in (200, 201):
            print(f"  OK    {data_type} → pushed to {PLATFORM}")
            ok += 1
        else:
            print(f"  FAIL  {data_type} → HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"  ERROR {data_type} → {e}")

print(f"\nDone. {ok}/{len(FILES)} data types pushed.")
if ok == len(FILES):
    print("Refresh lvl13.tech — the site should load now.")
