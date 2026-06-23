@echo off
title Setting GitHub Actions secrets...
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

echo.
echo ============================================================
echo  SETUP GITHUB SECRETS
echo  Adds INTERNAL_API_KEY to GitHub Actions so the refresh
echo  scripts can push data to the backend API automatically.
echo ============================================================
echo.

REM Check if gh CLI is available
gh --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: GitHub CLI (gh) not found.
    echo.
    echo Add the secret manually at:
    echo   https://github.com/YOUR_USERNAME/WallStBots/settings/secrets/actions
    echo.
    echo Secret name:  INTERNAL_API_KEY
    echo Secret value: wsb_internal_7f3a9b2c4e1d8f6a5b0e3c7d2a9f4b1e
    echo.
    pause
    exit /b 1
)

echo [1] Setting INTERNAL_API_KEY secret...
echo wsb_internal_7f3a9b2c4e1d8f6a5b0e3c7d2a9f4b1e | gh secret set INTERNAL_API_KEY
echo EXIT: %ERRORLEVEL%

echo.
echo [2] Verifying secrets list...
gh secret list

echo.
echo ============================================================
echo  Done! GitHub Actions can now push data to the backend API.
echo  The next scheduled run will automatically populate all data.
echo ============================================================
pause
