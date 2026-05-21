@echo off
title Fixing detached HEAD + pushing fixes...
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

set LOG=push-rebase-log.txt
echo === PUSH REBASE LOG === > %LOG%
echo %DATE% %TIME% >> %LOG%
echo. >> %LOG%

REM Set git identity
git config user.name  "WallStBots Bot"
git config user.email "bot@wallstbots.tech"

REM Clean up lock files and aborted rebase state
if exist ".git\HEAD.lock"    del /f /q ".git\HEAD.lock"
if exist ".git\index.lock"   del /f /q ".git\index.lock"
if exist ".git\rebase-merge" rmdir /s /q ".git\rebase-merge" 2>nul
if exist ".git\rebase-apply" rmdir /s /q ".git\rebase-apply" 2>nul

echo [1] Current state >> %LOG%
git status --short >> %LOG% 2>&1
git branch >> %LOG% 2>&1
echo. >> %LOG%

echo [2] Get back onto master branch >> %LOG%
git checkout master >> %LOG% 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  checkout failed - trying to create master from remote >> %LOG%
    git checkout -B master origin/master >> %LOG% 2>&1
)
echo CHECKOUT EXIT: %ERRORLEVEL% >> %LOG%

echo. >> %LOG%
echo [3] Reset master to match remote exactly >> %LOG%
git reset --hard origin/master >> %LOG% 2>&1
echo RESET EXIT: %ERRORLEVEL% >> %LOG%

echo. >> %LOG%
echo [4] Apply stashed changes >> %LOG%
git stash pop >> %LOG% 2>&1
echo STASH POP EXIT: %ERRORLEVEL% >> %LOG%

echo. >> %LOG%
echo [5] Stage our fix files >> %LOG%
git add ".github/workflows/refresh-wallstbots.yml" >> %LOG% 2>&1
git add "Project/scripts/refresh_wallstbots.py"    >> %LOG% 2>&1
git add "Frontends/wallstbots.tech/assets/app.js"  >> %LOG% 2>&1
git add "Frontends/bitbot13.tech/assets/app.js"    >> %LOG% 2>&1
git add "Frontends/wallstbots.tech/data/"          >> %LOG% 2>&1
git add "Frontends/bitbot13.tech/data/"            >> %LOG% 2>&1
echo STAGE EXIT: %ERRORLEVEL% >> %LOG%

echo. >> %LOG%
echo [6] Commit >> %LOG%
git commit -m "fix: workflow simplified + traceback on crash + data files restored" >> %LOG% 2>&1
echo COMMIT EXIT: %ERRORLEVEL% >> %LOG%

echo. >> %LOG%
echo [7] Push >> %LOG%
git push origin master >> %LOG% 2>&1
echo PUSH EXIT: %ERRORLEVEL% >> %LOG%

echo. >> %LOG%
echo [8] Final log >> %LOG%
git log --oneline -5 >> %LOG% 2>&1

echo. >> %LOG%
echo === DONE === >> %LOG%

echo.
echo Results:
type push-rebase-log.txt
echo.
echo ============================================================
echo  NEXT: Run RUN-seed-all.bat to seed the backend with live data
echo ============================================================
pause
