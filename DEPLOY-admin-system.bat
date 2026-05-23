@echo off
setlocal EnableDelayedExpansion
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

echo.
echo ============================================================
echo   DEPLOY: Admin System + All Bug Fixes
echo   - main.py (backend v2.0: admin endpoints, all bug fixes)
echo   - app.js x2 (referral URL fixes)
echo   - dashboard.html x2 (news platform fixes)
echo   - admin.html x3 (wallstbots + bitbot13 + lvl13)
echo ============================================================
echo.

REM ── 1. Pull latest ──────────────────────────────────────────
echo [1/5] Pulling latest from GitHub...
git pull --ff-only origin master
if %ERRORLEVEL% NEQ 0 (
  echo ERROR: Pull failed. Run PUSH-FORCE-PULL-REBASE.bat first.
  pause & exit /b 1
)

REM ── 2. Stage all changed files ──────────────────────────────
echo.
echo [2/5] Staging changed files...

git add Backend/main.py
git add Backend/admin_migration.sql
git add Frontends/wallstbots.tech/assets/app.js
git add Frontends/bitbot13.tech/assets/app.js
git add Frontends/wallstbots.tech/dashboard.html
git add Frontends/bitbot13.tech/dashboard.html
git add Frontends/wallstbots.tech/admin.html
git add Frontends/bitbot13.tech/admin.html
git add Frontends/lvl13.tech/admin.html

git status --short
echo.

REM ── 3. Commit ───────────────────────────────────────────────
echo [3/5] Committing...
git diff --cached --quiet
if %ERRORLEVEL% EQU 0 (
  echo Nothing new to commit - files may already be pushed.
) else (
  git commit -m "feat: admin system, backend v2.0 (bug fixes + admin endpoints + admin.html)"
  if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Commit failed.
    pause & exit /b 1
  )
)

REM ── 4. Push to GitHub (Cloudflare auto-deploys frontends) ───
echo.
echo [4/5] Pushing to GitHub (Cloudflare auto-deploys in ~1 min)...
git push origin master
if %ERRORLEVEL% NEQ 0 (
  echo ERROR: Push failed.
  pause & exit /b 1
)
echo.
echo Frontend push done. Cloudflare Pages will auto-deploy.

REM ── 5. Deploy backend to Cloud Run ─────────────────────────
echo.
echo [5/5] Deploying backend to Cloud Run (gcloud source deploy)...
echo This takes 3-5 minutes. Do not close this window.
echo.

cd Backend

gcloud run deploy wallstbots-backend ^
  --source . ^
  --region us-east1 ^
  --allow-unauthenticated ^
  --quiet

if %ERRORLEVEL% NEQ 0 (
  echo.
  echo WARNING: Cloud Run deploy may have failed.
  echo Check: https://console.cloud.google.com/run
  echo.
) else (
  echo.
  echo Backend deployed successfully!
)

cd ..

REM ── Done ────────────────────────────────────────────────────
echo.
echo ============================================================
echo   DEPLOY COMPLETE
echo ============================================================
echo.
echo *** ACTION REQUIRED — Run this SQL in Supabase: ***
echo.
echo   1. Go to: https://supabase.com/dashboard/project/_/sql/new
echo   2. Open: Backend\admin_migration.sql
echo   3. Paste and run it
echo.
echo This will:
echo   - Add max_free_bots column (if not exists)
echo   - Set lvl13cs@gmail.com as admin with max_free_bots=999
echo   - Backfill referral_codes table (FK fix for existing users)
echo   - Grant lvl13cs@gmail.com full access to all 3 platforms
echo.
echo After running the SQL, log in at:
echo   https://wallstbots.tech/admin.html
echo   https://bitbot13.tech/admin.html
echo   https://lvl13.tech/admin.html
echo.
pause
