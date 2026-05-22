@echo off
title SYNC wallstbots app.js to Project/public_html
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

set LOG=%~dp0sync-wallstbots-result.txt
echo === SYNC wallstbots app.js === > "%LOG%"
echo %DATE% %TIME% >> "%LOG%"
echo. >> "%LOG%"

echo [1] copy updated app.js from Frontends to Project/public_html >> "%LOG%"
copy /Y "Frontends\wallstbots.tech\assets\app.js" "Project\public_html\assets\app.js" >> "%LOG%" 2>&1
echo exit: %ERRORLEVEL% >> "%LOG%"

echo. >> "%LOG%"
echo [2] verify SYNDICATE is in the copied file >> "%LOG%"
findstr /C:"SYNDICATE" "Project\public_html\assets\app.js" >> "%LOG%" 2>&1
echo findstr exit: %ERRORLEVEL% >> "%LOG%"

echo. >> "%LOG%"
echo [3] git add >> "%LOG%"
git add "Project/public_html/assets/app.js" >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo [4] git status >> "%LOG%"
git status --short >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo [5] git commit >> "%LOG%"
git commit -m "fix: sync Project/public_html/assets/app.js with 4-tier pricing" >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo [6] fetch origin >> "%LOG%"
git fetch origin >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo [7] rebase onto origin/master >> "%LOG%"
git rebase origin/master >> "%LOG%" 2>&1
set REBASE_RC=%ERRORLEVEL%
echo rebase exit: %REBASE_RC% >> "%LOG%"

if %REBASE_RC% NEQ 0 (
  echo REBASE FAILED - force push >> "%LOG%"
  git rebase --abort >> "%LOG%" 2>&1
  git push origin master --force >> "%LOG%" 2>&1
  set PUSH_RC=%ERRORLEVEL%
) else (
  echo [8] push >> "%LOG%"
  git push origin master >> "%LOG%" 2>&1
  set PUSH_RC=%ERRORLEVEL%
)
echo push exit: %PUSH_RC% >> "%LOG%"

echo. >> "%LOG%"
echo [9] final git log >> "%LOG%"
git log --oneline -4 >> "%LOG%" 2>&1

echo. >> "%LOG%"
if %PUSH_RC% EQU 0 (
  echo === SUCCESS - wallstbots.tech will deploy from Cloudflare === >> "%LOG%"
) else (
  echo === PUSH FAILED === >> "%LOG%"
)

type "%LOG%"
echo.
echo Log saved to sync-wallstbots-result.txt
echo Window will stay open. Close when ready.
pause
