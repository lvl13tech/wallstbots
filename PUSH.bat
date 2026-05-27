@echo off
REM ============================================================
REM  PUSH.bat — Universal deploy for all 3 sites
REM  lvl13.tech is now on Cloudflare Pages (migrated May 2026)
REM
REM  HOW IT WORKS:
REM  git push → GitHub → Cloudflare auto-deploys all 3 sites
REM  No FTP. No upload script. All 3 sites identical process.
REM
REM  USAGE:
REM  Just run this after making any changes.
REM  Pass a commit message as argument, or edit the default below.
REM ============================================================

cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

set MSG=%~1
if "%MSG%"=="" set MSG=update: site changes

echo [1/3] Staging all changes...
git add -A

echo [2/3] Committing...
git diff --staged --quiet && (
    echo Nothing to commit - working tree clean.
    goto push
)
git commit -m "%MSG%"

:push
echo [3/3] Pushing to GitHub...
git pull --rebase --autostash origin master
if errorlevel 1 (
    git rebase --abort 2>nul
    git push origin master --force-with-lease
) else (
    git push origin master
)

if errorlevel 1 (
    echo ERROR: push failed.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  DONE. Changes pushed to GitHub.
echo  Cloudflare is now deploying all 3 sites automatically.
echo  wallstbots.tech  — auto-deploy in ~60s
echo  bitbot13.tech    — auto-deploy in ~60s
echo  lvl13.tech       — auto-deploy in ~60s
echo ============================================================
pause
