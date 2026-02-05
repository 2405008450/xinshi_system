@echo off
echo Starting Backend Server on 192.168.31.125:8000...
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause
