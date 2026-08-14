@echo off
title Demeter Launcher
cd /d "%~dp0"

echo ============================================
echo   Starting Demeter...
echo ============================================

call demeter-env\Scripts\activate.bat

start "Demeter Server" /min cmd /c "python app.py"

timeout /t 5 /nobreak >nul

start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --app=http://localhost:5000

exit