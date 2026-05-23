"""
Fixes lvl13.tech DNS: removes the CNAME pointing to wallstbots.pages.dev
so the site routes to HostGator (129.121.81.184) instead of the wrong server.

HOW TO RUN: Double-click this file, or right-click → Open With → Python
"""
import urllib.request, urllib.error, json, sys

ZONE_ID  = '4e9327c386ae7e5a589b338ddfc5f946'
REC_ID   = '7825148a28c2a033dcc047e468f68f07'
EMAIL    = 'lvl13cs@gmail.com'

print("=" * 60)
print("  lvl13.tech DNS Fix")
print("=" * 60)
print()
print("Problem: CNAME 'lvl13.tech' → 'wallstbots.pages.dev'")
print("Fix:     Delete that CNAME → A record (129.121.81.184) wins.")
print()
print("You need your Cloudflare GLOBAL API Key.")
print("Find it: dash.cloudflare.com → Profile (top right)")
print("         → API Tokens → Global API Key → View")
print()

api_key = input("Paste your Cloudflare Global API Key, press Enter: ").strip()
if not api_key:
    print("No key entered. Exiting.")
    input("\nPress Enter to close...")
    sys.exit(1)

url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records/{REC_ID}"
req = urllib.request.Request(url, method='DELETE')
req.add_header('Content-Type', 'application/json')
req.add_header('X-Auth-Email', EMAIL)
req.add_header('X-Auth-Key', api_key)

print("\nCalling Cloudflare API...")
try:
    with urllib.request.urlopen(req) as resp:
        body = json.loads(resp.read().decode())
        if body.get('success'):
            print()
            print("SUCCESS - CNAME deleted!")
            print("lvl13.tech will load from HostGator within 1-2 minutes.")
        else:
            print(f"\nFailed: {body.get('errors')}")
except urllib.error.HTTPError as e:
    body = json.loads(e.read().decode())
    print(f"\nHTTP {e.code}: {body.get('errors', e.reason)}")
    if e.code == 403:
        print("-> Wrong key. Use the GLOBAL API Key, not an API Token.")

print()
input("Press Enter to close...")
