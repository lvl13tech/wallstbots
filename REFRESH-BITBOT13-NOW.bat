@echo off
title REFRESH BITBOT13 (new coin universe)
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

set LOG=%~dp0refresh-bitbot13-result.txt
echo === REFRESH BITBOT13 === > "%LOG%"
echo %DATE% %TIME% >> "%LOG%"
echo New universe: TAO/STX/FTM/GRT/IMX replaced by POL/RENDER/FET/ONDO/WIF >> "%LOG%"
echo. >> "%LOG%"

set PYTHON=
where py >nul 2>&1 && set PYTHON=py -3
if "%PYTHON%"=="" (where python >nul 2>&1 && set PYTHON=python)
if "%PYTHON%"=="" (
  echo ERROR: python not found >> "%LOG%"
  type "%LOG%" & pause & exit /b 1
)

echo [1] running refresh_bitbot13.py ... >> "%LOG%"
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots\Project\scripts"
%PYTHON% refresh_bitbot13.py >> "%LOG%" 2>&1
set REFRESH_RC=%ERRORLEVEL%
echo     exit code: %REFRESH_RC% >> "%LOG%"

echo. >> "%LOG%"
echo [2] committing and pushing to GitHub ... >> "%LOG%"
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

REM Abort any in-progress rebase before we start
git rebase --abort >nul 2>&1

REM Stage and commit our fresh data + script
git add Project/scripts/refresh_bitbot13.py Frontends/bitbot13.tech/data/ >> "%LOG%" 2>&1
git commit -m "swap POL->JUP; fix ticker; new universe live" >> "%LOG%" 2>&1

REM Fetch remote, then merge with -X ours so our data files always win conflicts
git fetch origin master >> "%LOG%" 2>&1
git merge -X ours origin/master -m "merge remote; keep local data files" >> "%LOG%" 2>&1

REM Push
git push origin master >> "%LOG%" 2>&1
set PUSH_RC=%ERRORLEVEL%
if %PUSH_RC% NEQ 0 (
  echo     WARNING: push failed >> "%LOG%"
) else (
  echo     push OK >> "%LOG%"
)
echo     git done >> "%LOG%"

echo. >> "%LOG%"
echo === DONE === >> "%LOG%"
echo %DATE% %TIME% >> "%LOG%"

type "%LOG%"
echo.
echo Log saved to refresh-bitbot13-result.txt
echo.
echo Hard-refresh bitbot13.tech to see the new coin universe live.
pause
