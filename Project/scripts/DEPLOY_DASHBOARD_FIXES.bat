@echo off
title Deploy Enhanced Dashboards — All 3 Sites
echo ============================================================
echo   Deploying enhanced dashboards to all 3 sites
echo ============================================================
echo.

echo [1/2] Git push WallStBots repo (auto-deploys bitbot13 + wallstbots via Cloudflare)...
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"
git add -A
git commit -m "Fix dashboard data unwrapping + api.js endpoint paths; add /subscriptions/current + /auth/password-reset to backend; upgraded bot-detail.html all 3 sites (platform switcher, account drawer, doughnut chart, live stock search)"
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
