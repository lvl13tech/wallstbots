@echo off
title FIX SECRET IN GIT HISTORY AND PUSH
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

set LOG=%~dp0fix-secret-result.txt
echo === FIX SECRET IN GIT HISTORY === > "%LOG%"
echo %DATE% %TIME% >> "%LOG%"
echo. >> "%LOG%"

REM ── Step 1: Stop tracking reset_admin.py ──────────────────────────
echo [1] removing reset_admin.py from git tracking... >> "%LOG%"
git rm --cached reset_admin.py >> "%LOG%" 2>&1
echo     done (file stays on disk, just removed from git) >> "%LOG%"

REM ── Step 2: Rewrite history to remove the secret from all commits ──
echo. >> "%LOG%"
echo [2] rewriting git history to scrub reset_admin.py from all commits... >> "%LOG%"
git filter-branch --force --index-filter ^
  "git rm --cached --ignore-unmatch reset_admin.py" ^
  --prune-empty --tag-name-filter cat -- --all >> "%LOG%" 2>&1
echo     filter-branch exit: %ERRORLEVEL% >> "%LOG%"

REM ── Step 3: Clean up refs left by filter-branch ────────────────────
echo. >> "%LOG%"
echo [3] cleaning up old refs... >> "%LOG%"
git for-each-ref --format="delete %(refname)" refs/original/ | git update-ref --stdin >> "%LOG%" 2>&1
git reflog expire --expire=now --all >> "%LOG%" 2>&1
git gc --prune=now --aggressive >> "%LOG%" 2>&1
echo     cleanup done >> "%LOG%"

REM ── Step 4: Commit updated .gitignore ──────────────────────────────
echo. >> "%LOG%"
echo [4] committing .gitignore update... >> "%LOG%"
git add .gitignore >> "%LOG%" 2>&1
git diff --cached --quiet
if %ERRORLEVEL% NEQ 0 (
  git commit -m "security: add reset_admin.py to .gitignore, remove from tracking" >> "%LOG%" 2>&1
  echo     committed >> "%LOG%"
) else (
  echo     nothing new to commit >> "%LOG%"
)

REM ── Step 5: Force push (history was rewritten) ─────────────────────
echo. >> "%LOG%"
echo [5] force pushing to GitHub... >> "%LOG%"
git push origin master --force >> "%LOG%" 2>&1
set PUSH_RC=%ERRORLEVEL%
echo     push exit: %PUSH_RC% >> "%LOG%"

echo. >> "%LOG%"
git log --oneline -5 >> "%LOG%" 2>&1

echo. >> "%LOG%"
if %PUSH_RC% EQU 0 (
  echo === SUCCESS === >> "%LOG%"
  echo   Secret purged from history. >> "%LOG%"
  echo   Cloudflare will redeploy wallstbots.tech and bitbot13.tech now. >> "%LOG%"
  echo   Run UPLOAD-LVL13-TO-HOSTGATOR.bat for lvl13.tech. >> "%LOG%"
) else (
  echo === PUSH FAILED === >> "%LOG%"
  echo   If GitHub still blocks, visit the unblock URL in the error above. >> "%LOG%"
)

type "%LOG%"
echo.
pause
