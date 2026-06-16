#!/usr/bin/env python3
"""
strip_boxchars.py
-----------------
Replaces Unicode box-drawing / decorative characters in comment dividers with
plain ASCII. These non-ASCII bytes are where the recurring file-truncation bug
keeps cutting (tools/editors choke on them when re-writing whole files).

SAFE: these characters only appear in CSS/JS *comments* (e.g.  // -- Boot --,
/* -- Header -- */), never in logic or visible content. Replacing them changes
nothing the user sees and no code behavior.

CRITICAL: reads and writes every file as UTF-8 explicitly, so this script itself
can never introduce an encoding-truncation.

Scope: all .html in Frontends/ and all .py in Project/scripts/ (the files that
have these comment dividers). Skips temp comparison copies.

Run:  python Project/scripts/strip_boxchars.py
Add --dry to preview without writing.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DRY  = "--dry" in sys.argv

# Box-drawing + a few decorative chars -> ASCII replacements.
REPLACEMENTS = {
    "─": "-",  # ─ light horizontal
    "━": "-",  # ━ heavy horizontal
    "│": "|",  # │ light vertical
    "┃": "|",  # ┃ heavy vertical
    "┌": "+",  # ┌
    "┐": "+",  # ┐
    "└": "+",  # └
    "┘": "+",  # ┘
    "├": "+",  # ├
    "┤": "+",  # ┤
    "┬": "+",  # ┬
    "┴": "+",  # ┴
    "┼": "+",  # ┼
    "═": "=",  # ═ double horizontal
    "║": "|",  # ║ double vertical
    "╔": "+", "╗": "+", "╚": "+", "╝": "+",  # double corners
    "╠": "+", "╣": "+", "╦": "+", "╩": "+", "╬": "+",
    "�": "",   # � replacement char (corruption residue) -> drop
}

def targets():
    fe = ROOT / "Frontends"
    for p in fe.rglob("*.html"):
        name = p.name
        # skip temp comparison copies
        if any(s in name for s in (".JUNE11.", ".GOOD.", ".CURRENT-backup.")):
            continue
        # skip per-commit hash copies like foo.1a2b3c4.html
        parts = name.split(".")
        if len(parts) == 3 and len(parts[1]) == 7 and all(c in "0123456789abcdef" for c in parts[1]):
            continue
        yield p
    sc = ROOT / "Project" / "scripts"
    for p in sc.rglob("*.py"):
        if p.name == "strip_boxchars.py":
            continue
        yield p

def main():
    changed = 0
    scanned = 0
    for path in targets():
        scanned += 1
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"  SKIP (read error) {path}: {e}")
            continue
        new = text
        for src, dst in REPLACEMENTS.items():
            if src in new:
                new = new.replace(src, dst)
        if new != text:
            n = sum(text.count(s) for s in REPLACEMENTS)
            print(f"  {'WOULD FIX' if DRY else 'FIXED'} {path}  ({n} chars)")
            if not DRY:
                path.write_text(new, encoding="utf-8")
            changed += 1
    print("")
    print(f"Scanned {scanned} files. {'Would change' if DRY else 'Changed'} {changed}.")
    if DRY:
        print("(dry run — nothing written. Re-run without --dry to apply.)")

if __name__ == "__main__":
    main()
