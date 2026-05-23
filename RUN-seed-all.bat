@echo off
title Seeding ALL data to backend API (state + signals + news + reports)...
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"

echo.
echo ============================================================
echo  SEED ALL — runs both refresh scripts locally.
echo  Fetches live prices via yfinance, computes bot P^&L,
echo  generates signals, fetches news, and pushes everything
echo  (state, signals, news, reports) to the backend tracker DB.
echo ============================================================
echo.

echo [1/2] Running refresh_wallstbots.py...
echo ----------------------------------------
python Project\scripts\refresh_wallstbots.py
echo.

echo [2/2] Running refresh_bitbot13.py...
echo ----------------------------------------
python Project\scripts\refresh_bitbot13.py
echo.

echo ============================================================
echo  Done! Verify live data at:
echo.
echo  wallstbots state:
echo    https://wallstbots-backend-868128114349.us-east1.run.app/public/tracker/state?platform=wallstbots
echo  wallstbots signals:
echo    https://wallstbots-backend-868128114349.us-east1.run.app/public/tracker/signals?platform=wallstbots
echo  wallstbots news:
echo    https://wallstbots-backend-868128114349.us-east1.run.app/public/tracker/news?platform=wallstbots
echo.
echo  bitbot13 state:
echo    https://wallstbots-backend-868128114349.us-east1.run.app/public/tracker/state?platform=bitbot13
echo  bitbot13 signals:
echo    https://wallstbots-backend-868128114349.us-east1.run.app/public/tracker/signals?platform=bitbot13
echo  bitbot13 news:
echo    https://wallstbots-backend-868128114349.us-east1.run.app/public/tracker/news?platform=bitbot13
echo ============================================================
pause
