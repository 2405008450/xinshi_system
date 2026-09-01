@echo off
setlocal
cd /d "%~dp0"
echo Starting Frontend Server on 192.168.31.144:3000...
npm run dev -- --host 0.0.0.0 --port 3000
pause
