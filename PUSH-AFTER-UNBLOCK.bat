@echo off
title PUSH AFTER GITHUB UNBLOCK
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

set LOG=%~dp0push-after-unblock-result.txt
echo === PUSH AFTER GITHUB SECRET UNBLOCK === > "%LOG%"
echo %DATE% %TIME% >> "%LOG%"
echo. >> "%LOG%"

echo [1] fetch origin >> "%LOG%"
git fetch origin >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo [2] rebase onto origin/master >> "%LOG%"
git rebase origin/master >> "%LOG%" 2>&1
set RB=%ERRORLEVEL%
if %RB% NEQ 0 (
  git rebase --abort >> "%LOG%" 2>&1
  echo rebase failed - using force push >> "%LOG%"
  git push origin master --force >> "%LOG%" 2>&1
) else (
  echo [3] push >> "%LOG%"
  git push origin master >> "%LOG%" 2>&1
)
set PUSH_RC=%ERRORLEVEL%

echo. >> "%LOG%"
git log --oneline -5 >> "%LOG%" 2>&1

echo. >> "%LOG%"
if %PUSH_RC% EQU 0 (
  echo === SUCCESS - Cloudflare deploying now === >> "%LOG%"
  echo Run UPLOAD-LVL13-TO-HOSTGATOR.bat for lvl13.tech >> "%LOG%"
) else (
  echo === PUSH FAILED === >> "%LOG%"
  echo Make sure you visited the unblock URL and clicked Allow first. >> "%LOG%"
)

type "%LOG%"
echo.
pause
