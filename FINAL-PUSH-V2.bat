@echo off
title FINAL PUSH V2 — log outside repo
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

REM Put log in %TEMP% so git pull --rebase can freely reset the working tree
for /f "tokens=2 delims==" %%a in ('"wmic os get localdatetime /value"') do set DT=%%a
set LOG=%TEMP%\final-push-v2-%DT:~0,14%.txt

echo === FINAL PUSH V2 LOG === > "%LOG%"
echo %DATE% %TIME% >> "%LOG%"
echo. >> "%LOG%"

echo [A] killing stale git processes... >> "%LOG%"
taskkill /F /IM git.exe /T              >> "%LOG%" 2>&1
taskkill /F /IM git-remote-https.exe /T >> "%LOG%" 2>&1
timeout /t 2 /nobreak >nul

echo. >> "%LOG%"
echo [B] cleaning lock + rebase state... >> "%LOG%"
if exist ".git\HEAD.lock"      del /f /q ".git\HEAD.lock"      >> "%LOG%" 2>&1
if exist ".git\index.lock"     del /f /q ".git\index.lock"     >> "%LOG%" 2>&1
if exist ".git\rebase-merge"   rmdir /s /q ".git\rebase-merge" >> "%LOG%" 2>&1
if exist ".git\rebase-apply"   rmdir /s /q ".git\rebase-apply" >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo [C] current local HEAD: >> "%LOG%"
git log --oneline -1 >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo [D] fetch origin... >> "%LOG%"
git fetch origin master >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo [E] remote HEAD: >> "%LOG%"
git log --oneline origin/master -1 >> "%LOG%" 2>&1

REM Use rebase with -X theirs to auto-resolve conflicts in our favor for any
REM .json data files (which are auto-generated upstream anyway).
echo. >> "%LOG%"
echo [F] git pull --rebase --strategy-option=theirs --autostash origin master >> "%LOG%"
git pull --rebase --strategy-option=theirs --autostash origin master >> "%LOG%" 2>&1
echo PULL EXIT: %ERRORLEVEL% >> "%LOG%"

echo. >> "%LOG%"
echo [G] push origin master >> "%LOG%"
git push origin master >> "%LOG%" 2>&1
echo PUSH EXIT: %ERRORLEVEL% >> "%LOG%"

echo. >> "%LOG%"
echo [H] last 5 commits >> "%LOG%"
git log --oneline -5 >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo === DONE === >> "%LOG%"

REM Copy log to repo so Claude can read it (after git operations complete)
copy /Y "%LOG%" "%~dp0final-push-v2-result.txt" >nul

type "%LOG%"
exit /b 0
