@echo off
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

echo Removing git lock if present...
if exist .git\index.lock del /f .git\index.lock

echo Staging frontend files...
git add Frontends/

echo Committing...
git commit -m "Fix: dashboard tier system (member/insider/syndicate) + portfolio limits"

echo Pulling remote changes first...
git pull --rebase origin master

echo Pushing to origin...
git push origin master

echo Done.
pause
