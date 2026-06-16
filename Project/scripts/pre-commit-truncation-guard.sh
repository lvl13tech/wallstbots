#!/bin/sh
# ============================================================================
#  pre-commit-truncation-guard.sh
#  Git pre-commit hook: blocks any commit that includes a TRUNCATED HTML file
#  (one whose final non-empty line is not </html>). This is the guard against
#  the recurring mid-save truncation bug (bot-detail, portfolio-fund, app.js).
#
#  Installed to .git/hooks/pre-commit by INSTALL-truncation-guard.bat.
# ============================================================================

fail=0

# Check every staged .html file (Added/Copied/Modified)
for f in $(git diff --cached --name-only --diff-filter=ACM | grep -i '\.html$'); do
    [ -f "$f" ] || continue
    # Skip temp comparison copies (e.g. foo.JUNE11.html, foo.<hash>.html)
    case "$f" in
        *.JUNE11.html|*.GOOD.html|*.CURRENT-backup.html) continue ;;
    esac
    # Look for </html> anywhere in the last 5 lines (tolerates trailing blanks)
    if tail -n 5 "$f" | grep -qi "</html>"; then
        : # ok
    else
        echo "  ✗ TRUNCATED (no </html> at end): $f"
        fail=1
    fi
done

if [ "$fail" -ne 0 ]; then
    echo ""
    echo "============================================================"
    echo " COMMIT BLOCKED: one or more HTML files are TRUNCATED."
    echo " They do not end with </html> -- this is the mid-save"
    echo " truncation bug. Fix the file(s) before committing."
    echo " (To override in a true emergency: git commit --no-verify)"
    echo "============================================================"
    exit 1
fi

exit 0
