@echo off
title Pushing wallstbots.tech auth fixes...
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

set LOG=push-auth-log.txt
echo === PUSH AUTH FIXES LOG === > %LOG%
echo %DATE% %TIME% >> %LOG%
echo. >> %LOG%

echo [0] Removing stale git lock files... >> %LOG%
if exist ".git\HEAD.lock" (
    del /f /q ".git\HEAD.lock"
    echo Deleted HEAD.lock >> %LOG%
) else (
    echo No HEAD.lock found >> %LOG%
)
if exist ".git\index.lock" (
    del /f /q ".git\index.lock"
    echo Deleted index.lock >> %LOG%
) else (
    echo No index.lock found >> %LOG%
)

echo. >> %LOG%
echo [1] git status >> %LOG%
git status >> %LOG% 2>&1

echo. >> %LOG%
echo [2] git add frontend auth files >> %LOG%
git add "Frontends/wallstbots.tech/index.html" >> %LOG% 2>&1
git add "Frontends/wallstbots.tech/assets/style.css" >> %LOG% 2>&1
git add "Frontends/wallstbots.tech/assets/app.js" >> %LOG% 2>&1
echo ADD EXIT: %ERRORLEVEL% >> %LOG%

echo. >> %LOG%
echo [3] git commit >> %LOG%
git -c user.name="WallStBots Bot" -c user.email="bot@wallstbots.tech" commit -m "fix: add login/signup nav buttons + auth-aware nav + fix broken #/login routes" >> %LOG% 2>&1
echo COMMIT EXIT: %ERRORLEVEL% >> %LOG%

echo. >> %LOG%
echo [4] git push origin master >> %LOG%
git push origin master >> %LOG% 2>&1
echo PUSH EXIT: %ERRORLEVEL% >> %LOG%

echo. >> %LOG%
echo [5] git log >> %LOG%
git log --oneline -5 >> %LOG% 2>&1

echo. >> %LOG%
echo === DONE === >> %LOG%

echo Done! Results:
type push-auth-log.txt
pause
