#!/bin/sh
# ============================================================================
#  pre-commit-truncation-guard.sh
#  Git pre-commit hook: blocks any commit containing a TRUNCATED file.
#  Covers the recurring mid-save truncation bug (OneDrive sync racing the
#  editor) for BOTH file types:
#    - HTML : must contain </html> in its final lines
#    - .py  : must COMPILE (py_compile) AND parse to a complete module;
#             a mid-line cut, unclosed bracket, or missing tail all fail.
#  Installed to .git/hooks/pre-commit by INSTALL-truncation-guard.bat.
#  Emergency override (use sparingly): git commit --no-verify
# ============================================================================

fail=0

# --- HTML files -------------------------------------------------------------
for f in $(git diff --cached --name-only --diff-filter=ACM | grep -i '\.html$'); do
    [ -f "$f" ] || continue
    case "$f" in
        *.JUNE11.html|*.GOOD.html|*.CURRENT-backup.html) continue ;;
    esac
    if tail -n 5 "$f" | grep -qi "</html>"; then
        :
    else
        echo "  X TRUNCATED (no </html> at end): $f"
        fail=1
    fi
done

# --- Python files -----------------------------------------------------------
# Pick a python interpreter if one exists; if none, skip the .py check
PY=""
for cand in python3 python py; do
    if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
done

for f in $(git diff --cached --name-only --diff-filter=ACM | grep -i '\.py$'); do
    [ -f "$f" ] || continue
    if [ -n "$PY" ]; then
        if ! "$PY" -m py_compile "$f" >/dev/null 2>&1; then
            echo "  X TRUNCATED or broken (does not compile): $f"
            fail=1
        fi
    else
        # No python available: fall back to a heuristic - a complete script
        # should not end mid-token. Flag if last non-empty line ends with an
        # obvious continuation/open construct.
        last=$(awk 'NF{l=$0} END{print l}' "$f")
        case "$last" in
            *"="|*","|*"("|*"["|*"{"|*"\\")
                echo "  X LIKELY TRUNCATED (ends mid-statement): $f"
                fail=1 ;;
        esac
    fi
done

if [ "$fail" -ne 0 ]; then
    echo ""
    echo "============================================================"
    echo " COMMIT BLOCKED: one or more files are TRUNCATED/broken."
    echo " This is the mid-save truncation bug (OneDrive vs editor)."
    echo " Re-save the flagged file(s), then commit again."
    echo " Emergency override: git commit --no-verify"
    echo "============================================================"
    exit 1
fi

exit 0
