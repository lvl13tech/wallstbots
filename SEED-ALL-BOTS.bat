@echo off
title SEED ALL BOTS — First Run
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

set LOG=%~dp0seed-all-bots-result.txt
echo === SEED ALL BOTS === > "%LOG%"
echo %DATE% %TIME% >> "%LOG%"
echo Seeds ORACLE/WIZARD/EQUALIZER/TITAN on first run >> "%LOG%"
echo. >> "%LOG%"

set PYTHON=
where py >nul 2>&1 && set PYTHON=py -3
if "%PYTHON%"=="" (where python >nul 2>&1 && set PYTHON=python)
if "%PYTHON%"=="" (
  echo ERROR: python not found >> "%LOG%"
  type "%LOG%" & pause & exit /b 1
)

echo [1] refreshing wallstbots (seeds ORACLE/WIZARD/EQUALIZER/TITAN) ... >> "%LOG%"
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots\Project\scripts"
%PYTHON% refresh_wallstbots.py >> "%LOG%" 2>&1
echo     wallstbots exit: %ERRORLEVEL% >> "%LOG%"

echo. >> "%LOG%"
echo [2] refreshing bitbot13 (seeds ORACLE/WIZARD/EQUALIZER/TITAN) ... >> "%LOG%"
%PYTHON% refresh_bitbot13.py >> "%LOG%" 2>&1
echo     bitbot13 exit: %ERRORLEVEL% >> "%LOG%"

echo. >> "%LOG%"
echo [3] committing and pushing to GitHub ... >> "%LOG%"
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

REM Abort any in-progress rebase
git rebase --abort >nul 2>&1

git add Frontends/wallstbots.tech/ Frontends/bitbot13.tech/ Project/scripts/ >> "%LOG%" 2>&1
git commit -m "seed all bots: ORACLE/WIZARD/EQUALIZER/TITAN first-run logic + header count fix" >> "%LOG%" 2>&1
git fetch origin master >> "%LOG%" 2>&1
git merge -X ours origin/master -m "merge remote; keep local seeded data" >> "%LOG%" 2>&1
git push origin master >> "%LOG%" 2>&1
set PUSH_RC=%ERRORLEVEL%
if %PUSH_RC% NEQ 0 (
  echo     WARNING: push failed >> "%LOG%"
) else (
  echo     push OK >> "%LOG%"
)

echo. >> "%LOG%"
echo === DONE === >> "%LOG%"
echo %DATE% %TIME% >> "%LOG%"

type "%LOG%"
echo.
echo Log saved to seed-all-bots-result.txt
echo.
echo Hard-refresh wallstbots.tech and bitbot13.tech — all 5 bots should now be live.
pause
