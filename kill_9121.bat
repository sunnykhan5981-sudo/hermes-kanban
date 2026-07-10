@echo off
echo Killing python on port 9121...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :9121 ^| findstr LISTENING') do (
  echo killing %%a
  taskkill /F /PID %%a >nul 2>&1
)
echo Done.
pause
