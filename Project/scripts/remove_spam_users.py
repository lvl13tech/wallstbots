#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
remove_spam_users.py — find + hard-delete spam/bot signup accounts.

Logs in as an admin (creds from ADMIN_EMAIL/ADMIN_PASSWORD env, set by the .bat
prompt), looks up each target email via /admin/users, prints what it found, and
(with --apply) calls DELETE /admin/users/{id} to remove the user + all data + the
Supabase auth row. Dry run by default.
"""
import os
import sys
import json
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

print("=== remove_spam_users.py starting ===", flush=True)
APPLY = "--apply" in sys.argv

TARGETS = [
    "yasuo11111@proton.me",
    "renavit147@fanchatu.com",
    "sovevak441@herojp.com",
]

ROOT = Path(__file__).resolve().parents[2]
sec = {}
sp = ROOT / "Project" / "config" / "secrets.json"
if sp.exists():
    try:
        sec = json.loads(sp.read_text())
    except Exception as e:
        print("WARNING: could not read secrets.json:", e)
BACKEND = (sec.get("api_url") or os.environ.get("BACKEND_URL", "")).rstrip("/")
EMAIL = os.environ.get("ADMIN_EMAIL", "").strip()
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
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:
            return e.code, {"error": "http error"}
    except Exception as e:
        return -1, {"error": repr(e)}


def main():
    print("BACKEND:", BACKEND or "(MISSING)")
    print("ADMIN_EMAIL:", EMAIL or "(MISSING)")
    if not BACKEND or not EMAIL or not PW:
        print("ERROR: need BACKEND (secrets.json api_url) + ADMIN_EMAIL + ADMIN_PASSWORD.")
        sys.exit(1)

    st, resp = _req("POST", "/auth/login", body={"email": EMAIL, "password": PW})
    if st != 200 or not resp.get("access_token"):
        print("LOGIN FAILED:", st, resp)
        sys.exit(1)
    token = resp["access_token"]
    print("admin login OK\n")

    print("=== MODE:", "APPLY (will delete)" if APPLY else "DRY RUN (no changes)", "===\n")
    for email in TARGETS:
        st, resp = _req("GET", "/admin/users?search=" + urllib.parse.quote(email), token=token)
        users = (resp or {}).get("users", []) if st == 200 else []
        match = [u for u in users if u.get("email", "").lower() == email.lower()]
        if not match:
            print("  %s: not found (already gone?)" % email)
            continue
        u = match[0]
        print("  %s: id=%s role=%s created=%s paid=$%s platforms=%s" % (
            email, u["id"], u["role"], u.get("created_at"),
            u.get("total_paid", 0), u.get("active_platforms", 0)))
        if u.get("role") == "admin":
            print("    -> SKIP: admin account.")
            continue
        if float(u.get("total_paid", 0) or 0) > 0:
            print("    -> CAUTION: has payments; skipping. Remove manually if intended.")
            continue
        if APPLY:
            ds, dr = _req("DELETE", "/admin/users/" + str(u["id"]), token=token)
            if ds == 200:
                print("    -> DELETED ok. rows=%s auth=%s" % (dr.get("rows_deleted"), dr.get("auth_user_deleted")))
            else:
                print("    -> DELETE FAILED HTTP %s: %s" % (ds, dr))
        else:
            print("    -> would delete (choose APPLY to remove)")
    print("\nDone." if APPLY else "\nDone (dry run -- nothing changed).")


if __name__ == "__main__":
    main()
