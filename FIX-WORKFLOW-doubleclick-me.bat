@echo off
title Pushing workflow fix...
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

set LOGFILE=git-push-log.txt
echo. > %LOGFILE%
echo === GIT PUSH LOG === >> %LOGFILE%
echo. >> %LOGFILE%

echo [status] >> %LOGFILE%
git status >> %LOGFILE% 2>&1

echo. >> %LOGFILE%
echo [remote] >> %LOGFILE%
git remote -v >> %LOGFILE% 2>&1

echo. >> %LOGFILE%
echo [add] >> %LOGFILE%
git add ".github\workflows\refresh-wallstbots.yml" >> %LOGFILE% 2>&1

echo. >> %LOGFILE%
echo [commit] >> %LOGFILE%
git commit -m "fix: use python -m pip install with pandas and debug steps" >> %LOGFILE% 2>&1

echo. >> %LOGFILE%
echo [push] >> %LOGFILE%
git push origin master >> %LOGFILE% 2>&1

echo. >> %LOGFILE%
echo EXIT CODE: %ERRORLEVEL% >> %LOGFILE%

echo Done. Check git-push-log.txt in the WallStBots folder.
pause
