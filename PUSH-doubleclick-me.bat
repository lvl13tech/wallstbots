@echo off
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"
echo === Committing and pushing all changes ===
git add -A
git commit -m "update: %date% %time%"
git pull --rebase --autostash origin master
git push origin master
echo.
echo === Done! Cloudflare will auto-deploy in ~60 seconds ===
pause
