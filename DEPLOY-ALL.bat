@echo off
title DEPLOY ALL SITES
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

set LOG=%~dp0deploy-all-result.txt
echo === DEPLOY ALL SITES === > "%LOG%"
echo %DATE% %TIME% >> "%LOG%"
echo. >> "%LOG%"

REM ─────────────────────────────────────────────────────────────
REM STEP 1: Sync wallstbots frontend → Project/public_html
REM  (Cloudflare Pages deploys wallstbots.tech from Project/public_html,
REM   NOT from Frontends/wallstbots.tech — keep them in sync)
REM ─────────────────────────────────────────────────────────────
echo [1] sync Frontends/wallstbots.tech → Project/public_html >> "%LOG%"
copy /Y "Frontends\wallstbots.tech\assets\app.js"   "Project\public_html\assets\app.js"   >> "%LOG%" 2>&1
copy /Y "Frontends\wallstbots.tech\assets\style.css" "Project\public_html\assets\style.css" >> "%LOG%" 2>&1
copy /Y "Frontends\wallstbots.tech\index.html"       "Project\public_html\index.html"       >> "%LOG%" 2>&1
copy /Y "Frontends\wallstbots.tech\dashboard.html"   "Project\public_html\dashboard.html"   >> "%LOG%" 2>&1
copy /Y "Frontends\wallstbots.tech\admin.html"       "Project\public_html\admin.html"       >> "%LOG%" 2>&1
copy /Y "Frontends\wallstbots.tech\login.html"       "Project\public_html\login.html"       >> "%LOG%" 2>&1
copy /Y "Frontends\wallstbots.tech\signup.html"      "Project\public_html\signup.html"      >> "%LOG%" 2>&1
copy /Y "Frontends\wallstbots.tech\auth.js"          "Project\public_html\auth.js"          >> "%LOG%" 2>&1
copy /Y "Frontends\wallstbots.tech\api.js"           "Project\public_html\api.js"           >> "%LOG%" 2>&1
echo sync done >> "%LOG%"

echo. >> "%LOG%"
echo [2] git status >> "%LOG%"
git status --short >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo [3] git add all >> "%LOG%"
git add -A >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo [4] git status after add >> "%LOG%"
git status --short >> "%LOG%" 2>&1

REM Only commit if there are staged changes
git diff --cached --quiet
if %ERRORLEVEL% EQU 0 (
  echo. >> "%LOG%"
  echo [5] nothing to commit - working tree clean >> "%LOG%"
  git log --oneline -3 >> "%LOG%" 2>&1
  goto push
)

echo. >> "%LOG%"
echo [5] git commit >> "%LOG%"
git commit -m "deploy: sync all frontend files across sites" >> "%LOG%" 2>&1

:push
echo. >> "%LOG%"
echo [6] fetch origin >> "%LOG%"
git fetch origin >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo [7] rebase onto origin/master >> "%LOG%"
git rebase origin/master >> "%LOG%" 2>&1
set REBASE_RC=%ERRORLEVEL%
echo rebase exit: %REBASE_RC% >> "%LOG%"

if %REBASE_RC% NEQ 0 (
  echo REBASE FAILED - using force push >> "%LOG%"
  git rebase --abort >> "%LOG%" 2>&1
  git push origin master --force >> "%LOG%" 2>&1
  set PUSH_RC=%ERRORLEVEL%
) else (
  echo. >> "%LOG%"
  echo [8] push to master >> "%LOG%"
  git push origin master >> "%LOG%" 2>&1
  set PUSH_RC=%ERRORLEVEL%
)
echo push exit: %PUSH_RC% >> "%LOG%"

echo. >> "%LOG%"
echo [9] final git log >> "%LOG%"
git log --oneline -5 >> "%LOG%" 2>&1

echo. >> "%LOG%"
if %PUSH_RC% EQU 0 (
  echo === SUCCESS ===                                      >> "%LOG%"
  echo   wallstbots.tech  - Cloudflare deploying now       >> "%LOG%"
  echo   bitbot13.tech    - Cloudflare deploying now       >> "%LOG%"
  echo   lvl13.tech       - run UPLOAD-LVL13-TO-HOSTGATOR  >> "%LOG%"
) else (
  echo === PUSH FAILED - check log above === >> "%LOG%"
)

type "%LOG%"
echo.
echo Log saved to deploy-all-result.txt
echo.
echo NOTE: After this succeeds, also run UPLOAD-LVL13-TO-HOSTGATOR.bat
echo       to push lvl13.tech to HostGator via FTP.
echo.
echo Window will stay open. Close when ready.
pause
