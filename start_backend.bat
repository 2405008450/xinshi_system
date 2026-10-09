@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy\start_local.ps1" -Service Backend -Reload
set "START_EXIT=%ERRORLEVEL%"
pause
exit /b %START_EXIT%
