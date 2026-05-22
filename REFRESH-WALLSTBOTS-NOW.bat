@echo off
title REFRESH WALLSTBOTS
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

set LOG=%~dp0refresh-wallstbots-result.txt
echo === REFRESH WALLSTBOTS === > "%LOG%"
echo %DATE% %TIME% >> "%LOG%"
echo. >> "%LOG%"

set PYTHON=
where py >nul 2>&1 && set PYTHON=py -3
if "%PYTHON%"=="" (where python >nul 2>&1 && set PYTHON=python)
if "%PYTHON%"=="" (
  echo ERROR: python not found >> "%LOG%"
  type "%LOG%" & pause & exit /b 1
)

echo [1] running refresh_wallstbots.py ... >> "%LOG%"
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots\Project\scripts"
%PYTHON% refresh_wallstbots.py >> "%LOG%" 2>&1
echo     exit: %ERRORLEVEL% >> "%LOG%"

echo. >> "%LOG%"
echo [2] committing and pushing to GitHub ... >> "%LOG%"
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

git rebase --abort >nul 2>&1
git add Frontends/wallstbots.tech/data/ >> "%LOG%" 2>&1
git commit -m "wallstbots refresh — fix bot13 inception 2026-05-22" >> "%LOG%" 2>&1
git fetch origin master >> "%LOG%" 2>&1
git merge -X ours origin/master -m "merge remote; keep local data" >> "%LOG%" 2>&1
git push origin master >> "%LOG%" 2>&1
if %ERRORLEVEL% EQU 0 (echo     push OK >> "%LOG%") else (echo     push FAILED >> "%LOG%")

echo. >> "%LOG%"
echo === DONE === >> "%LOG%"
echo %DATE% %TIME% >> "%LOG%"

type "%LOG%"
echo.
pause
