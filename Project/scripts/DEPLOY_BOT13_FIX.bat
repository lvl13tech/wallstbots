@echo off
title BOT13 Fix - Deploy to GitHub
echo ============================================================
echo   BOT13 Fix: Deploying to GitHub (Cloudflare auto-deploys)
echo ============================================================
echo.

cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

echo [1/3] Staging all changes...
git add -A

echo [2/3] Committing...
git commit -m "Fix BOT13: same-day guard + correct total formula (day_open + sum_pnl)"

echo [3/3] Pushing to GitHub...
git push origin master

echo.
echo ============================================================
echo   Done! Cloudflare will auto-deploy bitbot13.tech and
echo   wallstbots.tech within ~60 seconds.
echo.
echo   BOT13 will now:
echo   - Size positions from day_open capital (not inflated total)
echo   - Never re-create positions mid-day (same_day guard)
echo   - Total = day_open + holdings P^&L  (matches receipts)
echo ============================================================
echo.
pause
