@echo off
title Promote lvl13cs@gmail.com to Webmaster
echo ============================================
echo  Promoting lvl13cs@gmail.com to Webmaster
echo ============================================
echo.
echo Calling /webmaster/set-owner endpoint...
echo.

curl -s -X POST "https://wallstbots-backend-868128114349.us-east1.run.app/webmaster/set-owner?email=lvl13cs@gmail.com" ^
     -H "X-Internal-Key: wsb_internal_7f3a9b2c4e1d8f6a5b0e3c7d2a9f4b1e" ^
     -H "Content-Type: application/json"

echo.
echo.
echo Done! Log in to the dashboard and you should see the "Command" nav link.
echo.
pause
