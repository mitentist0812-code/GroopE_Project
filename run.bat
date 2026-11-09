@echo off
setlocal
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Python virtual environment was not found: venv\Scripts\python.exe
    echo Please prepare the project virtual environment before running this file.
    pause
    exit /b 1
)

where ollama >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Ollama was not found. Install Ollama and restart this terminal.
    echo https://ollama.com/download
    pause
    exit /b 1
)

where curl.exe >nul 2>&1
if errorlevel 1 (
    echo [ERROR] curl.exe was not found. It is required to check Ollama.
    pause
    exit /b 1
)

set "OLLAMA_HOST=127.0.0.1:11434"
if not defined OLLAMA_MODEL set "OLLAMA_MODEL=llama3.1"

curl.exe --silent --fail --max-time 2 http://127.0.0.1:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo Starting Ollama...
    start "Ollama" /min ollama serve
    set /a OLLAMA_ATTEMPTS=0
    goto wait_for_ollama
)
goto check_model

:wait_for_ollama
set /a OLLAMA_ATTEMPTS+=1
curl.exe --silent --fail --max-time 2 http://127.0.0.1:11434/api/tags >nul 2>&1
if not errorlevel 1 goto check_model
if %OLLAMA_ATTEMPTS% GEQ 30 (
    echo [ERROR] Ollama did not start at 127.0.0.1:11434.
    echo Check the Ollama window or start Ollama manually and try again.
    pause
    exit /b 1
)
ping 127.0.0.1 -n 2 >nul
goto wait_for_ollama

:check_model
ollama show "%OLLAMA_MODEL%" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] The configured Ollama model is not available: "%OLLAMA_MODEL%"
    echo Download it with: ollama pull "%OLLAMA_MODEL%"
    pause
    exit /b 1
)

echo Ollama is ready. Starting the Flask app...
"venv\Scripts\python.exe" -m flask --app apps:create_app run --debug
set "APP_EXIT_CODE=%ERRORLEVEL%"
pause
exit /b %APP_EXIT_CODE%
