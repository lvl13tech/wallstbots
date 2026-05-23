@echo off
title Deploy Enhanced Dashboards — All 3 Sites
echo ============================================================
echo   Deploying enhanced dashboards to all 3 sites
echo ============================================================
echo.

echo [1/2] Git push WallStBots repo (auto-deploys bitbot13 + wallstbots via Cloudflare)...
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"
git add -A
git commit -m "Enhanced dashboard: account drawer, platform switcher, membership stats, sort, ticker picker ($1k/security max 50); add searchStocks/getNews/requestPasswordReset to api.js"
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
