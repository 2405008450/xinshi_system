@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\deploy\start_local.ps1" -Service Frontend
set "START_EXIT=%ERRORLEVEL%"
pause
exit /b %START_EXIT%
