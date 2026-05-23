@echo off
title Push x-internal-key header fix...
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

set LOG=push-header-fix-log.txt
echo === PUSH HEADER FIX LOG === > %LOG%
echo %DATE% %TIME% >> %LOG%
echo. >> %LOG%

REM Set git identity
git config user.name  "WallStBots Bot"
git config user.email "bot@wallstbots.tech"

REM Clean up any lock files
if exist ".git\HEAD.lock"    del /f /q ".git\HEAD.lock"
if exist ".git\index.lock"   del /f /q ".git\index.lock"

echo [1] Current branch >> %LOG%
git branch >> %LOG% 2>&1
git status --short >> %LOG% 2>&1
echo. >> %LOG%

echo [2] Pull latest (fast-forward only) >> %LOG%
git pull --ff-only origin master >> %LOG% 2>&1
echo PULL EXIT: %ERRORLEVEL% >> %LOG%
echo. >> %LOG%

echo [3] Stage the two fixed scripts >> %LOG%
git add "Project/scripts/refresh_wallstbots.py" >> %LOG% 2>&1
git add "Project/scripts/refresh_bitbot13.py"   >> %LOG% 2>&1
echo STAGE EXIT: %ERRORLEVEL% >> %LOG%
echo. >> %LOG%

echo [4] Commit >> %LOG%
git commit -m "fix: use x-internal-key header for backend API pushes" >> %LOG% 2>&1
echo COMMIT EXIT: %ERRORLEVEL% >> %LOG%
echo. >> %LOG%

echo [5] Push >> %LOG%
git push origin master >> %LOG% 2>&1
echo PUSH EXIT: %ERRORLEVEL% >> %LOG%
echo. >> %LOG%

echo [6] Final log >> %LOG%
git log --oneline -5 >> %LOG% 2>&1
echo. >> %LOG%
echo === DONE === >> %LOG%

echo.
echo Results:
type push-header-fix-log.txt
echo.
echo ============================================================
echo  NEXT: Run RUN-seed-all.bat to push live data to the backend
echo ============================================================
pause
