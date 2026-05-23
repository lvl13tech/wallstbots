@echo off
title UPLOAD lvl13 to HostGator (FTP)
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

REM Log goes to %TEMP% (NOT in repo) so nothing locks/syncs it
for /f "tokens=2 delims==" %%a in ('"wmic os get localdatetime /value"') do set DT=%%a
set LOG=%TEMP%\upload-lvl13-%DT:~0,14%.txt

echo === UPLOAD lvl13 to HostGator === > "%LOG%"
echo %DATE% %TIME% >> "%LOG%"
echo. >> "%LOG%"

REM Find python
set PY=
where py >nul 2>&1 && set PY=py -3
if "%PY%"=="" (where python >nul 2>&1 && set PY=python)
if "%PY%"=="" (
  echo ERROR: python not found. Install from python.org >> "%LOG%"
  type "%LOG%"
  pause
  exit /b 1
)

echo Using: %PY% >> "%LOG%"
echo. >> "%LOG%"

%PY% Project\scripts\upload_lvl13_full.py >> "%LOG%" 2>&1
set RC=%ERRORLEVEL%

REM Copy log back into repo so Claude can read it
copy /Y "%LOG%" "%~dp0upload-lvl13-result.txt" >nul

type "%LOG%"
echo.
if "%RC%"=="0" (
  echo ============================================================
  echo  SUCCESS. Now hard-refresh https://lvl13.tech ^(Ctrl+F5^)
  echo ============================================================
) else (
  echo ============================================================
  echo  ERRORS. Read the log above for details.
  echo ============================================================
)
echo Window will stay open. Close it when ready.
pause
