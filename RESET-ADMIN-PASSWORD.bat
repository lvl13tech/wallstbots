@echo off
title RESET ADMIN PASSWORD
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

set LOG=%~dp0reset-admin-result.txt
echo === RESET ADMIN PASSWORD === > "%LOG%"
echo %DATE% %TIME% >> "%LOG%"
echo. >> "%LOG%"

set PYTHON=
where py >nul 2>&1 && set PYTHON=py -3
if "%PYTHON%"=="" (where python >nul 2>&1 && set PYTHON=python)
if "%PYTHON%"=="" (
  echo ERROR: python not found >> "%LOG%"
  type "%LOG%"
  pause & exit /b 1
)

%PYTHON% reset_admin.py >> "%LOG%" 2>&1
set RC=%ERRORLEVEL%

type "%LOG%"
echo.
if "%RC%"=="0" (
  echo ============================================================
  echo  Password reset complete.
  echo  Login: https://wallstbots.tech/#/login
  echo ============================================================
) else (
  echo ============================================================
  echo  Something went wrong - check log above.
  echo ============================================================
)
pause
