@echo off
title Deploy lvl13.tech app.js (SFTP)
echo ============================================================
echo   Uploading lvl13.tech app.js to HostGator
echo   Uses SFTP (port 22) - works even if FTP port 21 is blocked
echo ============================================================
echo.

echo [1/2] Ensuring paramiko is installed (required for SFTP)...
pip install paramiko --quiet --break-system-packages 2>nul || pip install paramiko --quiet
echo.

echo [2/2] Uploading via upload_lvl13_full.py (SFTP first, FTP fallback)...
python "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots\Project\scripts\upload_lvl13_full.py"

echo.
echo ============================================================
echo   Done!
echo ============================================================
echo.
pause
