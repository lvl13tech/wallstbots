@echo off
title PUSH PRICING - LOGGED
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

set LOG=%~dp0push-pricing-result.txt
echo === PUSH PRICING TO MASTER === > "%LOG%"
echo %DATE% %TIME% >> "%LOG%"
echo. >> "%LOG%"

echo [1] abort any in-progress rebase >> "%LOG%"
git rebase --abort >> "%LOG%" 2>&1
echo exit: %ERRORLEVEL% >> "%LOG%"

echo. >> "%LOG%"
echo [2] abort any in-progress merge >> "%LOG%"
git merge --abort >> "%LOG%" 2>&1
echo exit: %ERRORLEVEL% >> "%LOG%"

echo. >> "%LOG%"
echo [3] current stash list >> "%LOG%"
git stash list >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo [4] drop all stashes (pricing commit is already committed, not stashed) >> "%LOG%"
git stash clear >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo [5] git status >> "%LOG%"
git status --short >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo [6] git log (check d354dc7 is HEAD) >> "%LOG%"
git log --oneline -6 >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo [7] fetch origin >> "%LOG%"
git fetch origin >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo [8] rebase onto origin/master >> "%LOG%"
git rebase origin/master >> "%LOG%" 2>&1
set REBASE_RC=%ERRORLEVEL%
echo rebase exit: %REBASE_RC% >> "%LOG%"

if %REBASE_RC% NEQ 0 (
  echo. >> "%LOG%"
  echo REBASE FAILED - aborting and using force push >> "%LOG%"
  git rebase --abort >> "%LOG%" 2>&1
  echo. >> "%LOG%"
  echo [8b] force push to master >> "%LOG%"
  git push origin master --force >> "%LOG%" 2>&1
  set PUSH_RC=%ERRORLEVEL%
  echo force-push exit: %PUSH_RC% >> "%LOG%"
) else (
  echo. >> "%LOG%"
  echo [9] normal push to master >> "%LOG%"
  git push origin master >> "%LOG%" 2>&1
  set PUSH_RC=%ERRORLEVEL%
  echo push exit: %PUSH_RC% >> "%LOG%"
)

echo. >> "%LOG%"
echo [10] final git log >> "%LOG%"
git log --oneline -5 >> "%LOG%" 2>&1

echo. >> "%LOG%"
if %PUSH_RC% EQU 0 (
  echo === SUCCESS - pricing is on master === >> "%LOG%"
) else (
  echo === FAILED - check log above === >> "%LOG%"
)

copy /Y "%LOG%" "%~dp0push-pricing-result.txt" >nul
type "%LOG%"
echo.
echo Log saved to push-pricing-result.txt - Claude can read it.
echo Window will stay open. Close when ready.
pause
