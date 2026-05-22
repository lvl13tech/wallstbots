"""
Patch inception dates: change 2026-05-23 → 2026-05-22 for all funds
on wallstbots and bitbot13 platforms.
"""
import urllib.request, urllib.error, json

API      = "https://wallstbots-backend-868128114349.us-east1.run.app"
INT_KEY  = "wsb_internal_7f3a9b2c4e1d8f6a5b0e3c7d2a9f4b1e"
OLD_DATE = "2026-05-23"
NEW_DATE = "2026-05-22"
PLATFORMS = ["wallstbots", "bitbot13"]

headers_get  = {"Content-Type": "application/json"}
headers_push = {"Content-Type": "application/json", "X-Internal-Key": INT_KEY}

def get(url):
    req = urllib.request.Request(url, headers=headers_get)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

def push(data_type, platform, data):
    body = json.dumps({"data_type": data_type, "platform": platform, "data": data}).encode()
    req  = urllib.request.Request(API + "/internal/tracker/push", data=body,
                                  headers=headers_push, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

for platform in PLATFORMS:
    print(f"\n=== {platform} ===")

    # Fetch current state
    resp = get(f"{API}/public/tracker/state?platform={platform}")
    state = resp["data"]

    # Fix inception on every fund
    changed = 0
    for fid, fund in state.get("funds", {}).items():
        if fund.get("inception") == OLD_DATE:
            fund["inception"] = NEW_DATE
            changed += 1
            print(f"  {fid}: {OLD_DATE} -> {NEW_DATE}")

    if changed == 0:
        print(f"  No funds had inception={OLD_DATE} — nothing to change.")
        continue

    # Push corrected state back
    result = push("state", platform, state)
    print(f"  pushed at {result.get('pushed_at')} — OK")

print("\n=== DONE ===")
print(f"Inception dates updated to {NEW_DATE} on all platforms. Run refresh next.")
print("Run the refresh script next to re-process today's signals with the corrected dates.")
