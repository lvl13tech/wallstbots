@echo off
title Pushing logo PNG files to GitHub...
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

set LOG=push-logos-log.txt
echo === PUSH LOGOS LOG === > %LOG%
echo %DATE% %TIME% >> %LOG%
echo. >> %LOG%

echo [0] Removing stale lock files... >> %LOG%
if exist ".git\HEAD.lock" del /f /q ".git\HEAD.lock"
if exist ".git\index.lock" del /f /q ".git\index.lock"

echo [1] git add logo PNGs for both sites >> %LOG%
git add "Frontends/wallstbots.tech/assets/logo-bitbot13.png" >> %LOG% 2>&1
git add "Frontends/wallstbots.tech/assets/logo-lvl13.png" >> %LOG% 2>&1
git add "Frontends/wallstbots.tech/assets/logo-wallstbots.png" >> %LOG% 2>&1
git add "Frontends/bitbot13.tech/assets/logo-bitbot13.png" >> %LOG% 2>&1
git add "Frontends/bitbot13.tech/assets/logo-lvl13.png" >> %LOG% 2>&1
git add "Frontends/bitbot13.tech/assets/logo-wallstbots.png" >> %LOG% 2>&1
echo ADD EXIT: %ERRORLEVEL% >> %LOG%

echo. >> %LOG%
echo [2] git commit >> %LOG%
git -c user.name="WallStBots Bot" -c user.email="bot@wallstbots.tech" commit -m "fix: add missing logo PNG files for cross-promo section" >> %LOG% 2>&1
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
type push-logos-log.txt
pause
