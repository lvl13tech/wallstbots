@echo off
title Pushing RSS news fix to GitHub...
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

set LOG=push-rss-news-log.txt
echo === PUSH RSS NEWS FIX LOG === > %LOG%
echo %DATE% %TIME% >> %LOG%
echo. >> %LOG%

if exist ".git\HEAD.lock" del /f /q ".git\HEAD.lock"
if exist ".git\index.lock" del /f /q ".git\index.lock"

echo [1] git add refresh scripts >> %LOG%
git add "Project/scripts/refresh_wallstbots.py" >> %LOG% 2>&1
git add "Project/scripts/refresh_bitbot13.py" >> %LOG% 2>&1
echo ADD EXIT: %ERRORLEVEL% >> %LOG%

echo. >> %LOG%
echo [2] git commit >> %LOG%
git -c user.name="WallStBots Bot" -c user.email="bot@wallstbots.tech" commit -m "fix: replace NewsAPI with free RSS feeds for news (NewsAPI blocks server-side requests)" >> %LOG% 2>&1
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
type push-rss-news-log.txt
pause
