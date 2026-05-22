@echo off
title FIX INCEPTION DATES AND REFRESH
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

set LOG=%~dp0fix-inception-result.txt
echo === FIX INCEPTION DATES === > "%LOG%"
echo %DATE% %TIME% >> "%LOG%"
echo. >> "%LOG%"

set PYTHON=
where py >nul 2>&1 && set PYTHON=py -3
if "%PYTHON%"=="" (where python >nul 2>&1 && set PYTHON=python)
if "%PYTHON%"=="" (
  echo ERROR: python not found >> "%LOG%"
  type "%LOG%" & pause & exit /b 1
)

REM ── Step 1: Patch inception dates in live DB ──────────────────────
echo [1] patching inception dates 2026-05-23 → 2026-05-22 ... >> "%LOG%"
%PYTHON% fix_inception.py >> "%LOG%" 2>&1
if %ERRORLEVEL% NEQ 0 (
  echo ERROR: fix_inception.py failed >> "%LOG%"
  type "%LOG%" & pause & exit /b 1
)
echo     patch done >> "%LOG%"

REM ── Step 2: Refresh wallstbots ────────────────────────────────────
echo. >> "%LOG%"
echo [2] refreshing wallstbots data ... >> "%LOG%"
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots\Project\scripts"
%PYTHON% refresh_wallstbots.py >> "%LOG%" 2>&1
echo     wallstbots refresh exit: %ERRORLEVEL% >> "%LOG%"

REM ── Step 3: Refresh bitbot13 ──────────────────────────────────────
echo. >> "%LOG%"
echo [3] refreshing bitbot13 data ... >> "%LOG%"
%PYTHON% refresh_bitbot13.py >> "%LOG%" 2>&1
echo     bitbot13 refresh exit: %ERRORLEVEL% >> "%LOG%"

echo. >> "%LOG%"
echo === DONE === >> "%LOG%"
echo %DATE% %TIME% >> "%LOG%"

type "%LOG%"
echo.
echo Log saved to fix-inception-result.txt
echo.
echo Hard-refresh wallstbots.tech and bitbot13.tech to see the race live.
pause
