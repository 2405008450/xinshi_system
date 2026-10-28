@echo off
cd /d "%~dp0"
if not exist "node_modules\electron\dist\electron.exe" (
  call npm ci
  if errorlevel 1 (
    echo Desktop dependencies failed to install.
    pause
    exit /b 1
  )
)
call npm start
