@echo off
title Push yfinance price fix...
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

set LOG=push-price-fix-log.txt
echo === PUSH PRICE FIX LOG === > %LOG%
echo %DATE% %TIME% >> %LOG%
echo. >> %LOG%

git config user.name  "WallStBots Bot"
git config user.email "bot@wallstbots.tech"
if exist ".git\index.lock" del /f /q ".git\index.lock"

echo [1] Pull latest >> %LOG%
git pull --ff-only origin master >> %LOG% 2>&1
echo PULL EXIT: %ERRORLEVEL% >> %LOG%
echo. >> %LOG%

echo [2] Stage >> %LOG%
git add "Project/scripts/refresh_wallstbots.py" >> %LOG% 2>&1
git add "Project/scripts/refresh_bitbot13.py"   >> %LOG% 2>&1
echo STAGE EXIT: %ERRORLEVEL% >> %LOG%
echo. >> %LOG%

echo [3] Commit >> %LOG%
git commit -m "fix: replace fast_info (broken) with yf.download bulk price fetch" >> %LOG% 2>&1
echo COMMIT EXIT: %ERRORLEVEL% >> %LOG%
echo. >> %LOG%

echo [4] Push >> %LOG%
git push origin master >> %LOG% 2>&1
echo PUSH EXIT: %ERRORLEVEL% >> %LOG%
echo. >> %LOG%

echo [5] Final log >> %LOG%
git log --oneline -5 >> %LOG% 2>&1
echo. >> %LOG%
echo === DONE === >> %LOG%

echo.
echo Results:
type push-price-fix-log.txt
echo.
echo ============================================================
echo  NEXT: Run RUN-seed-all.bat to verify prices come through
echo ============================================================
pause
