#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diag_resend.py -- one isolated test send through Resend, printing the EXACT API
response so we can tell a bad/missing key from a domain-verification rejection.

Usage (Windows, from C:\\Claude\\Websites\\WallStBots):
    set RESEND_API_KEY=re_your_key_here
    python Project\\scripts\\diag_resend.py your@email.com

If no recipient arg is given it sends to info@lvl13.tech's owner address below.
The key is read from the environment only and is never printed.
"""
import os
import sys
import json
import urllib.request
import urllib.error

FROM = "Wall St. Bots <info@lvl13.tech>"        # same FROM the real sender uses
TO   = sys.argv[1] if len(sys.argv) > 1 else "lvl13cs@gmail.com"

key = os.environ.get("RESEND_API_KEY", "")
print("RESEND_API_KEY present:", "yes" if key else "NO (set it first: set RESEND_API_KEY=re_xxx)")
print("FROM:", FROM)
print("TO:  ", TO)
if not key:
    sys.exit(1)

body = json.dumps({
    "from": FROM,
    "to": [TO],
    "subject": "WallStBots Resend diagnostic",
    "html": "<p>If you received this, Resend delivery from info@lvl13.tech works.</p>",
}).encode()

req = urllib.request.Request(
    "https://api.resend.com/emails",
    data=body,
    headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
)
try:
    r = urllib.request.urlopen(req, timeout=20)
    print("\nHTTP", r.status)
    print("RESPONSE:", r.read().decode()[:500])
    print("\nRESULT: SENT OK. Check the inbox for", TO,
          "\n -> If members still get nothing on the schedule, the GitHub RESEND_API_KEY",
          "secret is the problem (this key works; the one in Actions may be missing/old).")
except urllib.error.HTTPError as e:
    print("\nHTTP", e.code)
    try:
        print("ERROR BODY:", e.read().decode()[:600])
    except Exception:
        pass
    if e.code in (401, 403):
        print("\nRESULT: KEY rejected (401/403) -> the API key is invalid/disabled.")
    elif e.code in (422,) :
        print("\nRESULT: Request rejected (422) -> usually the FROM domain (lvl13.tech) is",
              "NOT verified in Resend, or the from-address isn't allowed. Fix domain verification.")
    else:
        print("\nRESULT: Resend rejected with the code above -- read ERROR BODY for the reason.")
except Exception as e:
    print("\nERROR:", repr(e))
    print("RESULT: could not reach Resend (network/timeout).")
