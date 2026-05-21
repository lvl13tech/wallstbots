@echo off
title PUSH FINAL FIXES — signals shape + app.js parity
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

REM Use a timestamped log OUTSIDE the repo so git can freely reset the tree
for /f "tokens=2 delims==" %%a in ('"wmic os get localdatetime /value"') do set DT=%%a
set LOG=%TEMP%\push-final-fixes-%DT:~0,14%.txt

echo === PUSH FINAL FIXES === > "%LOG%"
echo %DATE% %TIME% >> "%LOG%"

REM Cleanup
if exist ".git\HEAD.lock"      del /f /q ".git\HEAD.lock"      >> "%LOG%" 2>&1
if exist ".git\index.lock"     del /f /q ".git\index.lock"     >> "%LOG%" 2>&1
if exist ".git\rebase-merge"   rmdir /s /q ".git\rebase-merge" >> "%LOG%" 2>&1
if exist ".git\rebase-apply"   rmdir /s /q ".git\rebase-apply" >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo [1] git add the only files we want to commit (avoid noise) >> "%LOG%"
git add Project/scripts/refresh_bitbot13.py     >> "%LOG%" 2>&1
git add Project/scripts/refresh_wallstbots.py   >> "%LOG%" 2>&1
git add Frontends/bitbot13.tech/assets/app.js   >> "%LOG%" 2>&1
git add Frontends/wallstbots.tech/assets/app.js >> "%LOG%" 2>&1
git add Frontends/lvl13.tech/assets/app.js      >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo [2] commit >> "%LOG%"
git -c user.name="Level 13 Deploy" -c user.email="lvl13cs@gmail.com" commit -m "fix: signals emit canonical shape (symbol/action/upside_pct) + restore truncated app.js" >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo [3] pull --rebase --strategy-option=theirs (auto-resolve data files) >> "%LOG%"
git pull --rebase --strategy-option=theirs --autostash origin master >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo [4] push >> "%LOG%"
git push origin master >> "%LOG%" 2>&1
echo PUSH EXIT: %ERRORLEVEL% >> "%LOG%"

echo. >> "%LOG%"
echo [5] last 5 commits >> "%LOG%"
git log --oneline -5 >> "%LOG%" 2>&1

REM Copy log back into repo so Claude can read it
copy /Y "%LOG%" "%~dp0push-final-fixes-result.txt" >nul

type "%LOG%"
exit /b 0
