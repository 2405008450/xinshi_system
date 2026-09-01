@echo off
setlocal
cd /d "%~dp0"
set "PROJECT_PYTHON=%~dp0.conda_env\python.exe"
if not exist "%PROJECT_PYTHON%" (
    echo [ERROR] Conda environment not found: %PROJECT_PYTHON%
    exit /b 1
)
echo Starting Backend Server on 192.168.31.144:8000...
echo Python: %PROJECT_PYTHON%
"%PROJECT_PYTHON%" -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause
