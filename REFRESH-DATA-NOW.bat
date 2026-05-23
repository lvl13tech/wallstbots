@echo off
title REFRESH DATA NOW — run bitbot13 + wallstbots refresh scripts
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

REM Log goes to %TEMP% so git pull --rebase can freely reset the tree later
for /f "tokens=2 delims==" %%a in ('"wmic os get localdatetime /value"') do set DT=%%a
set LOG=%TEMP%\refresh-data-%DT:~0,14%.txt

echo === REFRESH DATA NOW === > "%LOG%"
echo %DATE% %TIME% >> "%LOG%"
echo. >> "%LOG%"

REM ── Find python ──────────────────────────────────────────────────────────
set PY=
where py >nul 2>&1 && set PY=py -3
if "%PY%"=="" (
  where python >nul 2>&1 && set PY=python
)
if "%PY%"=="" (
  echo ERROR: python not found on this machine. Install from https://python.org >> "%LOG%"
  type "%LOG%"
  pause
  exit /b 1
)
echo Using python: %PY% >> "%LOG%"

REM ── Make sure deps are installed (one-time, idempotent) ─────────────────
echo. >> "%LOG%"
echo [deps] checking yfinance + requests... >> "%LOG%"
%PY% -c "import yfinance, requests" >nul 2>&1
if errorlevel 1 (
  echo Installing yfinance + requests... >> "%LOG%"
  %PY% -m pip install --quiet yfinance requests >> "%LOG%" 2>&1
)

REM ── Run bitbot13 refresh ────────────────────────────────────────────────
echo. >> "%LOG%"
echo ============================================================ >> "%LOG%"
echo  Running refresh_bitbot13.py --push >> "%LOG%"
echo ============================================================ >> "%LOG%"
%PY% Project\scripts\refresh_bitbot13.py --push >> "%LOG%" 2>&1
echo BITBOT13 EXIT: %ERRORLEVEL% >> "%LOG%"

REM ── Run wallstbots refresh ──────────────────────────────────────────────
echo. >> "%LOG%"
echo ============================================================ >> "%LOG%"
echo  Running refresh_wallstbots.py --push >> "%LOG%"
echo ============================================================ >> "%LOG%"
%PY% Project\scripts\refresh_wallstbots.py --push >> "%LOG%" 2>&1
echo WALLSTBOTS EXIT: %ERRORLEVEL% >> "%LOG%"

echo. >> "%LOG%"
echo === DONE === >> "%LOG%"

REM Copy log back into repo so Claude can read it
copy /Y "%LOG%" "%~dp0refresh-data-result.txt" >nul

type "%LOG%"
echo.
echo ============================================================
echo  Done. Window will stay open. Close it when ready.
echo ============================================================
pause
