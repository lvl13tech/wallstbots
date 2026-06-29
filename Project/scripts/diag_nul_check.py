#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diag_nul_check.py — verify key repo files have real content (no NUL bytes, not empty,
and Python files compile) at a given repo root. Used after the OneDrive->C:\\Claude move
to confirm nothing was copied as a placeholder/corrupted. Exit 1 if any problem.

Usage: python diag_nul_check.py <repo_root>
"""
import sys
import glob
import os
import py_compile

root = sys.argv[1] if len(sys.argv) > 1 else "."

# Files that matter most (the ones that kept corrupting).
patterns = [
    "Project/scripts/refresh_wallstbots.py",
    "Project/scripts/refresh_aistocks.py",
    "Project/scripts/refresh_bitbot13.py",
    "Project/scripts/refresh_portfolios.py",
    "Project/scripts/send_emails.py",
    "Project/scripts/email_service.py",
    "Project/scripts/bot13_engine.py",
    "Backend/main.py",
    "Frontends/*/assets/app.js",
    "Frontends/*/portfolio-fund.html",
]

problems = []
checked = 0
for pat in patterns:
    for f in glob.glob(os.path.join(root, pat)):
        checked += 1
        try:
            b = open(f, "rb").read()
        except Exception as e:
            problems.append(f"{f}: cannot read ({e})")
            continue
        if len(b) == 0:
            problems.append(f"{f}: EMPTY (placeholder?)")
            continue
        if b"\x00" in b:
            problems.append(f"{f}: contains NUL bytes (corrupted)")
            continue
        if f.endswith(".py"):
            try:
                py_compile.compile(f, doraise=True)
            except Exception as e:
                problems.append(f"{f}: does not compile ({e})")

print(f"checked {checked} key files under {root}")
if problems:
    print("PROBLEMS FOUND:")
    for p in problems:
        print("  -", p)
    sys.exit(1)
print("ALL CLEAN — no NULs, no empties, all Python compiles.")
sys.exit(0)
