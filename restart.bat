@echo off
echo Restarting Kanban Dashboard...
taskkill /F /IM python.exe >nul 2>&1
timeout /t 2 /nobreak >nul
cd /d C:\Users\PROJECT-1\pl-kanban
del /s /q __pycache__ 2>nul
echo Starting server...
python server.py
pause
