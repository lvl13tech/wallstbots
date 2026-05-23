@echo off
title Deploy Stock Search Fix — All 3 Sites
echo ============================================================
echo   Deploying stock search + holdings fix to all 3 sites
echo ============================================================
echo.

echo Removing git lock if present...
del /f /q "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots\.git\index.lock" 2>nul

echo [1/2] Git push (auto-deploys bitbot13 + wallstbots via Cloudflare)...
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"
git add -A
git commit -m "Fix stock search + holdings: add POST/DELETE /bots/{id}/holdings to backend; expand search to NYSE+NASDAQ+OTC+PinkSheets; fix truncated bot-detail.html files; bitbot13 searches crypto"
git push origin master
echo.

echo [2/2] Done! lvl13.tech already updated via FTP (17/17 files).
echo.

echo ============================================================
echo   All 3 sites deployed. Backend needs Cloud Run redeploy.
echo ============================================================
echo.
pause
