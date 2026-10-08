@echo off
setlocal
cd /d "%~dp0"
set "PROJECT_PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%PROJECT_PYTHON%" (
    echo [ERROR] Project virtual environment not found: %PROJECT_PYTHON%
    exit /b 1
)
echo Starting Backend Server on http://127.0.0.1:8000...
echo Python: %PROJECT_PYTHON%
"%PROJECT_PYTHON%" -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause
