@echo off
title Deploy Dashboard Color Fixes
echo ============================================================
echo   Deploying dashboard color fixes to all 3 sites
echo ============================================================
echo.

echo [1/2] Git push WallStBots repo (auto-deploys bitbot13 + wallstbots via Cloudflare)...
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"
git add -A
git commit -m "Fix wallstbots dashboard colors: green -> blue (#00d4ff); sync lvl13 dark-theme dashboard"
git push origin master
echo.

echo [2/2] FTP upload to HostGator (lvl13.tech)...
pip install paramiko --quiet --break-system-packages 2>nul || pip install paramiko --quiet
python "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots\Project\scripts\upload_lvl13_full.py"
echo.

echo ============================================================
echo   Done! All 3 sites updated.
echo ============================================================
echo.
pause
