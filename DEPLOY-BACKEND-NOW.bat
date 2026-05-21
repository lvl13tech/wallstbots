@echo off
setlocal EnableDelayedExpansion
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

echo.
echo ============================================================
echo  DEPLOY BACKEND v2.0 to Cloud Run
echo  (admin endpoints + bug fixes)
echo ============================================================
echo.

REM ── Find gcloud wherever it lives ───────────────────────────
set GCLOUD=

REM Try PATH first
where gcloud >nul 2>&1
if %ERRORLEVEL% EQU 0 (
  set GCLOUD=gcloud
  goto :found
)

REM Try common install locations
for %%P in (
  "%LOCALAPPDATA%\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
  "%PROGRAMFILES(X86)%\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
  "%PROGRAMFILES%\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
  "%APPDATA%\gcloud\bin\gcloud.cmd"
  "C:\tools\google-cloud-sdk\bin\gcloud.cmd"
  "%USERPROFILE%\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
) do (
  if exist %%P (
    set GCLOUD=%%P
    goto :found
  )
)

REM Try PowerShell search as last resort
for /f "delims=" %%i in ('powershell -NoProfile -Command "Get-ChildItem -Path $env:LOCALAPPDATA,$env:PROGRAMFILES,'C:\' -Filter gcloud.cmd -Recurse -ErrorAction SilentlyContinue 2>$null | Select-Object -First 1 -ExpandProperty FullName"') do (
  set GCLOUD=%%i
  goto :found
)

echo.
echo ERROR: gcloud not found on this machine.
echo.
echo Please install Google Cloud SDK from:
echo   https://cloud.google.com/sdk/docs/install
echo.
echo OR use Google Cloud Shell at:
echo   https://shell.cloud.google.com
echo.
echo In Cloud Shell, run:
echo   git clone https://github.com/lvl13tech/wallstbots.git
echo   cd wallstbots/Backend
echo   gcloud run deploy wallstbots-backend --source . --region us-east1 --allow-unauthenticated --quiet
echo.
pause
exit /b 1

:found
echo Found gcloud at: !GCLOUD!
echo.

REM ── Set project ──────────────────────────────────────────────
echo Setting project...
"!GCLOUD!" config set project lvl13-tracker-496402
echo.

REM ── Deploy ───────────────────────────────────────────────────
echo [Deploying] Building + deploying wallstbots-backend...
echo This takes 3-5 minutes. Do NOT close this window.
echo.

cd Backend

"!GCLOUD!" run deploy wallstbots-backend ^
  --source . ^
  --region us-east1 ^
  --allow-unauthenticated ^
  --project lvl13-tracker-496402 ^
  --quiet

if %ERRORLEVEL% NEQ 0 (
  echo.
  echo ============================================================
  echo  WARNING: Deploy may have failed. Check logs at:
  echo  https://console.cloud.google.com/run
  echo ============================================================
) else (
  echo.
  echo ============================================================
  echo  BACKEND DEPLOYED SUCCESSFULLY!
  echo ============================================================
  echo.
  echo Backend URL:
  echo   https://wallstbots-backend-868128114349.us-east1.run.app
  echo.
  echo NEXT STEPS:
  echo.
  echo  1. Sign up at https://wallstbots.tech  (use lvl13cs@gmail.com)
  echo  2. Then tell Claude to run the admin migration
  echo     to set your account as admin.
  echo.
)

cd ..
pause
