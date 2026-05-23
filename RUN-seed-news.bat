@echo off
title Seeding news to backend API...
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

echo.
echo ============================================================
echo  SEED NEWS — runs refresh scripts locally, pushes news
echo  to the backend tracker DB for wallstbots + bitbot13
echo ============================================================
echo.

echo [1/2] Running refresh_wallstbots.py (news only path)...
python Project\scripts\refresh_wallstbots.py
echo.

echo [2/2] Running refresh_bitbot13.py (news only path)...
python Project\scripts\refresh_bitbot13.py
echo.

echo ============================================================
echo  Done! Check output above for:
echo    [news] X articles fetched per sector
echo    [news-push] pushed X articles to backend API
echo.
echo  Then verify live:
echo    https://wallstbots-backend-868128114349.us-east1.run.app/public/tracker/news?platform=wallstbots
echo    https://wallstbots-backend-868128114349.us-east1.run.app/public/tracker/news?platform=bitbot13
echo ============================================================
pause
