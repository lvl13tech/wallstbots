@echo off
title WallStBots - Full Deploy
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

echo ============================================
echo  WallStBots Full Deploy
echo ============================================
echo.

echo [1/5] Removing git locks if present...
if exist .git\index.lock del /f .git\index.lock
if exist .git\HEAD.lock del /f .git\HEAD.lock

echo [2/5] Staging all local changes...
git add -A
git commit -m "chore: deploy scripts and bat file updates" 2>nul
REM (commit returns non-zero if nothing to commit — that's fine, ignore it)

echo [3/5] Pulling remote changes...
git pull --rebase origin master
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: git pull failed. You may have a merge conflict.
    pause
    exit /b 1
)

echo [4/5] Pushing to GitHub (triggers Cloud Run + Cloudflare deploy)...
git push origin master
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: git push failed.
    pause
    exit /b 1
)

echo [5/5] Uploading lvl13.tech to HostGator via FTP...
python "Project\scripts\upload_lvl13_full.py"
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: FTP upload may have encountered issues. Check output above.
)

echo.
echo ============================================
echo  Deploy Complete!
echo ============================================
echo.
echo Next: Run PROMOTE_WEBMASTER.bat (wait ~3 min for backend to go live first)
echo.
pause
