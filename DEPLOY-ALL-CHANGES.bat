@echo off
title DEPLOY ALL — git push (triggers Cloudflare auto-deploy)
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

set LOG=deploy-all-log.txt
echo === DEPLOY-ALL LOG === > %LOG%
echo %DATE% %TIME% >> %LOG%
echo. >> %LOG%

REM ────────────────────────────────────────────────────────────────────────
REM Step 0 — clean any stale git locks (common on Windows + OneDrive)
REM ────────────────────────────────────────────────────────────────────────
echo [0] Cleaning git lock files...
if exist ".git\HEAD.lock"  del /f /q ".git\HEAD.lock"   >> %LOG% 2>&1
if exist ".git\index.lock" del /f /q ".git\index.lock"  >> %LOG% 2>&1

REM ────────────────────────────────────────────────────────────────────────
REM Step 1 — show current branch + status (just for the log)
REM ────────────────────────────────────────────────────────────────────────
echo. >> %LOG%
echo [1] git branch + status >> %LOG%
git rev-parse --abbrev-ref HEAD >> %LOG% 2>&1
git status -s >> %LOG% 2>&1

REM ────────────────────────────────────────────────────────────────────────
REM Step 2 — stage EVERYTHING that changed (frontend + backend + scripts)
REM ────────────────────────────────────────────────────────────────────────
echo. >> %LOG%
echo [2] git add -A >> %LOG%
git add -A >> %LOG% 2>&1
echo ADD EXIT: %ERRORLEVEL% >> %LOG%

REM ────────────────────────────────────────────────────────────────────────
REM Step 3 — commit
REM ────────────────────────────────────────────────────────────────────────
echo. >> %LOG%
echo [3] git commit >> %LOG%
git -c user.name="Level 13 Deploy" -c user.email="lvl13cs@gmail.com" commit -m "feat: 3-site parity pass + crypto/stocks news filter + origin_platform tracking + lvl13 SPA restored" >> %LOG% 2>&1
echo COMMIT EXIT: %ERRORLEVEL% >> %LOG%

REM ────────────────────────────────────────────────────────────────────────
REM Step 3.5 — pull remote changes first so push won't be rejected
REM ────────────────────────────────────────────────────────────────────────
echo. >> %LOG%
echo [3.5] git pull --rebase origin master >> %LOG%
git pull --rebase origin master >> %LOG% 2>&1
echo PULL EXIT: %ERRORLEVEL% >> %LOG%

REM ────────────────────────────────────────────────────────────────────────
REM Step 4 — push to GitHub (triggers Cloudflare Pages auto-deploy)
REM ────────────────────────────────────────────────────────────────────────
echo. >> %LOG%
echo [4] git push origin master >> %LOG%
git push origin master >> %LOG% 2>&1
echo PUSH EXIT: %ERRORLEVEL% >> %LOG%

REM ────────────────────────────────────────────────────────────────────────
REM Step 5 — recap
REM ────────────────────────────────────────────────────────────────────────
echo. >> %LOG%
echo [5] last 5 commits >> %LOG%
git log --oneline -5 >> %LOG% 2>&1

echo. >> %LOG%
echo === DONE === >> %LOG%
echo Cloudflare Pages will rebuild bitbot13.tech + wallstbots.tech within ~60-90 sec. >> %LOG%
echo lvl13.tech needs separate HostGator upload (use FTP script). >> %LOG%
echo Backend: run DEPLOY-BACKEND-NOW.bat for Cloud Run. >> %LOG%
echo Supabase: paste Backend\origin_platform_migration.sql into SQL Editor. >> %LOG%

echo.
echo ============================================================
echo  DEPLOY-ALL FINISHED. Results below:
echo ============================================================
type %LOG%
echo.
echo ============================================================
echo  Window will stay open. Press any key to close.
echo ============================================================
pause
