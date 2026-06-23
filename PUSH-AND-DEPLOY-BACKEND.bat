@echo off
setlocal
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

echo.
echo Commit faecdd7 already made. Pushing to GitHub now...
echo.

git push origin master
if %ERRORLEVEL% NEQ 0 (
  echo.
  echo ERROR: Push failed. Check git status.
  pause
  exit /b 1
)

echo.
echo Push done! Cloudflare Pages will auto-deploy frontends in ~60 sec.
echo.
echo ============================================================
echo  Now deploying backend to Cloud Run...
echo  (takes 3-5 min - do not close this window)
echo ============================================================
echo.

cd Backend

gcloud run deploy wallstbots-backend --source . --region us-east1 --allow-unauthenticated --quiet

if %ERRORLEVEL% NEQ 0 (
  echo.
  echo WARNING: Cloud Run deploy may have failed.
  echo Check: https://console.cloud.google.com/run
) else (
  echo.
  echo Backend deployed!
)

cd ..

echo.
echo ============================================================
echo  ALL DONE
echo ============================================================
echo.
echo NEXT: Run the SQL migration in Supabase:
echo   https://supabase.com/dashboard/project/_/sql/new
echo   File: Backend\admin_migration.sql
echo.
echo Then log in at: https://wallstbots.tech/admin.html
echo.
pause
