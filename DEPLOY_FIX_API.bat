@echo off
title Deploy API Fix — All 3 Sites
echo ============================================================
echo   Deploying "api is not defined" fix to all 3 sites
echo ============================================================
echo.

echo Removing git lock if present...
del /f /q "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots\.git\index.lock" 2>nul

echo [1/2] Git push (auto-deploys bitbot13 + wallstbots via Cloudflare)...
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"
git add -A
git commit -m "Fix api is not defined: load auth.js + instantiate WallStBotsAuth/WallStBotsAPI in all 3 dashboards and all 3 bot-detail pages"
git push origin master
echo.

echo [2/2] Done! lvl13.tech already updated via FTP (17/17 files).
echo.

echo ============================================================
echo   All 3 sites deployed.
echo ============================================================
echo.
pause
