@echo off
title Holdings Fix - Deploy All Sites
echo ============================================================
echo   Holdings Fix: receipts + Holding cash on all 3 sites
echo ============================================================
echo.

echo [1/2] Pushing WallStBots repo to GitHub (Cloudflare auto-deploys)...
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"
git add -A
git commit -m "Fix BOT13 holdings: preserve receipts on HOLD, add holding_cash flag to all 3 sites"
git push origin master

echo.
echo [2/2] FTP uploading lvl13.tech app.js to HostGator...
python "C:\Users\temps\OneDrive\Desktop\Claude\Websites\1. lvl13.tech\Project\scripts\deploy_appjs_ftp.py"

echo.
echo ============================================================
echo   Done! All 3 sites will now show:
echo   - Session receipts in the holdings table
echo   - "Holding cash" row after market close or on HOLD days
echo ============================================================
echo.
pause
