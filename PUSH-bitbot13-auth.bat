@echo off
title Pushing bitbot13.tech auth + login fixes...
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

set LOG=push-bitbot13-auth-log.txt
echo === PUSH BITBOT13 AUTH LOG === > %LOG%
echo %DATE% %TIME% >> %LOG%
echo. >> %LOG%

if exist ".git\HEAD.lock" del /f /q ".git\HEAD.lock"
if exist ".git\index.lock" del /f /q ".git\index.lock"

echo [1] git add bitbot13 files >> %LOG%
git add "Frontends/bitbot13.tech/index.html" >> %LOG% 2>&1
git add "Frontends/bitbot13.tech/assets/style.css" >> %LOG% 2>&1
git add "Frontends/bitbot13.tech/assets/app.js" >> %LOG% 2>&1
git add "Frontends/bitbot13.tech/auth.js" >> %LOG% 2>&1
git add "Frontends/bitbot13.tech/login.html" >> %LOG% 2>&1
git add "Frontends/bitbot13.tech/dashboard.html" >> %LOG% 2>&1
echo ADD EXIT: %ERRORLEVEL% >> %LOG%

echo. >> %LOG%
echo [2] git commit >> %LOG%
git -c user.name="WallStBots Bot" -c user.email="bot@wallstbots.tech" commit -m "fix: add login/dashboard + auth nav to bitbot13.tech" >> %LOG% 2>&1
echo COMMIT EXIT: %ERRORLEVEL% >> %LOG%

echo. >> %LOG%
echo [3] git push >> %LOG%
git push origin master >> %LOG% 2>&1
echo PUSH EXIT: %ERRORLEVEL% >> %LOG%

echo. >> %LOG%
echo [4] git log >> %LOG%
git log --oneline -5 >> %LOG% 2>&1

echo. >> %LOG%
echo === DONE === >> %LOG%

echo Done! Results:
type push-bitbot13-auth-log.txt
pause
