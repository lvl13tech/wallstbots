@echo off
echo.
echo ============================================================
echo  DEPLOY via WSL gcloud
echo ============================================================
echo.

REM Check if WSL is available
wsl --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
  echo WSL not available. Trying direct gcloud check...
  goto :try_direct
)

echo [1] Trying gcloud via WSL...
wsl gcloud run deploy wallstbots-backend --source /mnt/c/Users/temps/OneDrive/Desktop/Claude/Websites/WallStBots/Backend --region us-east1 --allow-unauthenticated --quiet --project lvl13-tracker-496402
if %ERRORLEVEL% EQU 0 (
  echo.
  echo DEPLOYED via WSL gcloud!
  goto :done
)

echo [2] Trying gcloud from WSL home clone...
wsl bash -c "cd ~/wallstbots/Backend 2>/dev/null && git pull origin master && gcloud run deploy wallstbots-backend --source . --region us-east1 --allow-unauthenticated --quiet --project lvl13-tracker-496402"
if %ERRORLEVEL% EQU 0 goto :done

:try_direct
echo [3] Checking if gcloud.cmd is in PATH...
where gcloud.cmd >nul 2>&1
if %ERRORLEVEL% EQU 0 (
  gcloud.cmd run deploy wallstbots-backend --source "%~dp0Backend" --region us-east1 --allow-unauthenticated --quiet --project lvl13-tracker-496402
  goto :done
)

where gcloud >nul 2>&1
if %ERRORLEVEL% EQU 0 (
  gcloud run deploy wallstbots-backend --source "%~dp0Backend" --region us-east1 --allow-unauthenticated --quiet --project lvl13-tracker-496402
  goto :done
)

echo.
echo ============================================================
echo  gcloud not found locally or via WSL.
echo  Run this in Google Cloud Shell:
echo.
echo  cd ~/wallstbots/Backend
echo  git pull origin master
echo  gcloud run deploy wallstbots-backend --source . --region us-east1 --allow-unauthenticated --quiet --project lvl13-tracker-496402
echo ============================================================

:done
echo.
pause
