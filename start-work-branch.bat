@echo off
setlocal
cd /d "%~dp0"

git rev-parse --show-toplevel >nul 2>&1
if errorlevel 1 (
    echo [ERROR] This file must be run from inside a Git repository.
    pause
    exit /b 1
)

echo Select a branch type:
echo   1. feature/  - New feature
echo   2. fix/      - Bug fix
echo   3. design/   - Design change
choice /c 123 /n /m "Choose 1, 2, or 3: "
if errorlevel 3 set "branch_prefix=design"
if errorlevel 2 if not defined branch_prefix set "branch_prefix=fix"
if errorlevel 1 if not defined branch_prefix set "branch_prefix=feature"

set "branch_name="
set /p "branch_name=Enter branch name (e.g. search or login-error): "
if not defined branch_name (
    echo [ERROR] Branch name cannot be empty.
    pause
    exit /b 1
)

set "branch=%branch_prefix%/%branch_name%"
git check-ref-format --branch "%branch%" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Invalid branch name: %branch%
    pause
    exit /b 1
)

git show-ref --verify --quiet "refs/heads/%branch%"
if not errorlevel 1 (
    echo [ERROR] Branch already exists: %branch%
    pause
    exit /b 1
)

echo.
echo Switching to main...
git switch main
if errorlevel 1 goto git_error

echo.
echo Pulling the latest main from origin...
git pull origin main
if errorlevel 1 goto git_error

echo.
echo Creating branch %branch%...
git switch -c "%branch%"
if errorlevel 1 goto git_error

echo.
echo Ready to work on %branch%.
pause
exit /b 0

:git_error
echo.
echo [ERROR] A Git command failed. Resolve the issue above before continuing.
pause
exit /b 1
