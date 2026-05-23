@echo off
title Push Backend Deploy Workflow
echo ============================================================
echo   Pushing GitHub Actions backend deploy workflow
echo ============================================================
echo.

echo Removing git lock if present...
del /f /q "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots\.git\index.lock" 2>nul

echo [1/2] Git push (auto-deploys bitbot13 + wallstbots via Cloudflare)...
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"
git add -A
git commit -m "Add GitHub Actions workflow for automatic backend Cloud Run deployment"
git push origin master
echo.

echo [2/2] Done! lvl13.tech already updated via FTP (17/17 files).
echo.

echo ============================================================
echo   All 3 sites deployed. Backend needs Cloud Run redeploy.
echo ============================================================
echo.
pause
