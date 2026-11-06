@echo off
setlocal
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Python virtual environment was not found: venv\Scripts\python.exe
    echo Please prepare the project virtual environment before running this file.
    pause
    exit /b 1
)

"venv\Scripts\python.exe" -m flask --app apps:create_app run --debug
pause
