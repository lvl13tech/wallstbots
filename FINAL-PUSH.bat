@echo off
title FINAL PUSH — full repair + rebase + push
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

REM Use a timestamped log so nothing else holds it open
for /f "tokens=2 delims==" %%a in ('"wmic os get localdatetime /value"') do set DT=%%a
set LOG=final-push-%DT:~0,14%.txt

echo === FINAL PUSH LOG === > %LOG%
echo %DATE% %TIME% >> %LOG%
echo. >> %LOG%

echo [A] killing stale git processes... >> %LOG%
taskkill /F /IM git.exe          /T >> %LOG% 2>&1
taskkill /F /IM git-remote-https.exe /T >> %LOG% 2>&1
timeout /t 2 /nobreak >nul

echo. >> %LOG%
echo [B] removing all lock + rebase state... >> %LOG%
if exist ".git\HEAD.lock"      del /f /q ".git\HEAD.lock"      >> %LOG% 2>&1
if exist ".git\index.lock"     del /f /q ".git\index.lock"     >> %LOG% 2>&1
if exist ".git\index"          del /f /q ".git\index"          >> %LOG% 2>&1
if exist ".git\rebase-merge"   rmdir /s /q ".git\rebase-merge" >> %LOG% 2>&1
if exist ".git\rebase-apply"   rmdir /s /q ".git\rebase-apply" >> %LOG% 2>&1

echo. >> %LOG%
echo [C] git reset (rebuild index from HEAD)... >> %LOG%
git reset >> %LOG% 2>&1

echo. >> %LOG%
echo [D] fetch origin... >> %LOG%
git fetch origin master >> %LOG% 2>&1

REM Pre-resolve: take remote's version of the 4 auto-refresh data files
echo. >> %LOG%
echo [E] take remote's version of auto-refresh data files... >> %LOG%
git checkout origin/master -- "Frontends/bitbot13.tech/data/signals.json"  >> %LOG% 2>&1
git checkout origin/master -- "Frontends/bitbot13.tech/data/state.json"    >> %LOG% 2>&1
git checkout origin/master -- "Frontends/wallstbots.tech/data/signals.json" >> %LOG% 2>&1
git checkout origin/master -- "Frontends/wallstbots.tech/data/state.json"   >> %LOG% 2>&1

echo. >> %LOG%
echo [F] amend the existing local commit with the resolved data files... >> %LOG%
git add -A >> %LOG% 2>&1
git -c user.name="Level 13 Deploy" -c user.email="lvl13cs@gmail.com" commit --amend --no-edit >> %LOG% 2>&1
echo AMEND EXIT: %ERRORLEVEL% >> %LOG%

echo. >> %LOG%
echo [G] rebase onto origin/master (autostash any leftovers)... >> %LOG%
git pull --rebase --autostash --strategy-option=theirs origin master >> %LOG% 2>&1
echo PULL EXIT: %ERRORLEVEL% >> %LOG%

echo. >> %LOG%
echo [H] push origin master... >> %LOG%
git push origin master >> %LOG% 2>&1
echo PUSH EXIT: %ERRORLEVEL% >> %LOG%

echo. >> %LOG%
echo [I] last 5 commits >> %LOG%
git log --oneline -5 >> %LOG% 2>&1

echo. >> %LOG%
echo === DONE === >> %LOG%
echo Log written to: %LOG% >> %LOG%

type %LOG%
exit /b 0
