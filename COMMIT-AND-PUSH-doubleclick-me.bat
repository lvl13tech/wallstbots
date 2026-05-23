@echo off
title Fixing lock + committing refresh_wallstbots.py...
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

set LOG=commit-push-log.txt
echo === COMMIT AND PUSH LOG === > %LOG%
echo %DATE% %TIME% >> %LOG%
echo. >> %LOG%

echo [0] Removing stale git lock files... >> %LOG%
if exist ".git\HEAD.lock" (
    del /f /q ".git\HEAD.lock" >> %LOG% 2>&1
    echo Deleted HEAD.lock >> %LOG%
) else (
    echo No HEAD.lock found >> %LOG%
)
if exist ".git\index.lock" (
    del /f /q ".git\index.lock" >> %LOG% 2>&1
    echo Deleted index.lock >> %LOG%
) else (
    echo No index.lock found >> %LOG%
)

echo. >> %LOG%
echo [1] git status >> %LOG%
git status >> %LOG% 2>&1

echo. >> %LOG%
echo [2] git add refresh_wallstbots.py >> %LOG%
git add "Project\scripts\refresh_wallstbots.py" >> %LOG% 2>&1
echo ADD EXIT: %ERRORLEVEL% >> %LOG%

echo. >> %LOG%
echo [3] git commit >> %LOG%
git -c user.name="WallStBots Bot" -c user.email="bot@wallstbots.tech" commit -m "feat: add refresh_wallstbots.py to repo" >> %LOG% 2>&1
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
type commit-push-log.txt
pause
