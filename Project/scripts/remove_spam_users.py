#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
remove_spam_users.py — find + hard-delete spam/bot signup accounts.

Logs in as an admin (your account), looks up each target email via /admin/users,
prints what it found, and (with --apply) calls DELETE /admin/users/{id} to remove
the user + all their data + the Supabase auth row.

Usage (from C:\\Claude\\Websites\\WallStBots):
    set ADMIN_EMAIL=you@youremail.com
    set ADMIN_PASSWORD=your_admin_password
    python Project\\scripts\\remove_spam_users.py            (dry run - shows, deletes nothing)
    python Project\\scripts\\remove_spam_users.py --apply    (actually delete)

Backend URL comes from secrets.json (api_url) or BACKEND_URL env.
Credentials are read from env only and never printed.
"""
import os, sys, json, urllib.request, urllib.error
from pathlib import Path

APPLY = "--apply" in sys.argv

# The confirmed spam/bot signups to remove (disposable / unknown domains).
TARGETS = [
    "yasuo11111@proton.me",
    "renavit147@fanchatu.com",
    "sovevak441@herojp.com",
]

ROOT = Path(__file__).resolve().parents[2]
sec = {}
sp = ROOT / "Project" / "config" / "secrets.json"
if sp.exists():
    sec = json.loads(sp.read_text())
BACKEND = (sec.get("api_url") or os.environ.get("BACKEND_URL", "")).rstrip("/")
EMAIL = os.environ.get("ADMIN_EMAIL", "")
PW    = os.environ.get("ADMIN_PASSWORD", "")


def _req(method, path, token=None, body=None):
    url = BACKEND + path
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        r = urllib.request.urlopen(req, timeout=30)
        return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode()[:300]}


def main():
    print("BACKEND:", BACKEND or "(MISSING)")
    if not BACKEND or not EMAIL or not PW:
        print("Set ADMIN_EMAIL + ADMIN_PASSWORD env vars first (and ensure api_url in secrets.json).")
        sys.exit(1)

    st, resp = _req("POST", "/auth/login", body={"email": EMAIL, "password": PW})
    if st != 200 or not resp.get("access_token"):
        print("LOGIN FAILED:", st, resp); sys.exit(1)
    token = resp["access_token"]
    print("admin login OK\n")

    print("=== MODE:", "APPLY (will delete)" if APPLY else "DRY RUN (no changes)", "===\n")
    for email in TARGETS:
        st, resp = _req("GET", f"/admin/users?search={urllib.parse.quote(email)}", token=token)
        users = (resp or {}).get("users", []) if st == 200 else []
        match = [u for u in users if (u.get("email","").lower() == email.lower())]
        if not match:
            print(f"  {email}: not found (already gone?)")
            continue
        u = match[0]
        print(f"  {email}: id={u['id']} role={u['role']} created={u.get('created_at')} "
              f"paid=${u.get('total_paid',0)} platforms={u.get('active_platforms',0)}")
        if u.get("role") == "admin":
            print("    -> SKIP: admin account, not deleting.")
            continue
        if float(u.get("total_paid", 0) or 0) > 0:
            print("    -> CAUTION: this account has payments; skipping to be safe. Remove manually if intended.")
            continue
        if APPLY:
            ds, dr = _req("DELETE", f"/admin/users/{u['id']}", token=token)
            print(f"    -> DELETE -> HTTP {ds} {dr if ds!=200 else 'OK rows='+str(dr.get('rows_deleted')) + ' auth='+str(dr.get('auth_user_deleted'))}")
        else:
            print("    -> would delete (run with --apply)")
    print("\nDone.", "" if APPLY else "(dry run — nothing changed)")


if __name__ == "__main__":
    import urllib.parse
    main()
