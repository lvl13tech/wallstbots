@echo off
REM GIT-SYNC-AND-PUSH.bat
REM Clears stale index.lock, syncs with remote, then pushes.

cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

echo [1/4] Removing stale index.lock if present...
if exist ".git\index.lock" (
    del /f ".git\index.lock"
    echo   index.lock removed.
) else (
    echo   No lock file found.
)

echo.
echo [2/4] Pulling remote changes with autostash...
git pull --rebase --autostash origin master

if %errorlevel% neq 0 (
    echo ERROR: pull rebase failed. Check for conflicts above.
    pause
    exit /b 1
)

echo.
echo [3/4] Pushing to GitHub...
git push origin master

if %errorlevel% neq 0 (
    echo ERROR: push failed.
    pause
    exit /b 1
)

echo.
echo [4/4] Done. Cloudflare will auto-deploy all 3 sites.
echo wallstbots.tech + bitbot13.tech + lvl13.tech — all on Cloudflare Pages.
pause
