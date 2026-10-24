@echo off
cd /d "%~dp0"
echo ======================================
echo    Blog-Gen Setup Script (Windows)
echo ======================================

:: Check for Docker
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker is not installed or not in PATH.
    pause
    exit /b 1
)

:: Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    pause
    exit /b 1
)

:: Check for Node
call npm --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] npm is not installed or not in PATH.
    pause
    exit /b 1
)

echo.
echo [INFO] Setting up Backend...
cd backend

if not exist .env (
    echo Creating .env file...
    copy .env.example .env
    python generate_secret.py
    echo [IMPORTANT] Update backend\.env with your API keys!
) else (
    echo .env file already exists.
)

echo Starting Docker containers...
docker compose up -d --wait --wait-timeout 60 db
if errorlevel 1 exit /b 1

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 exit /b 1
)

echo Installing dependencies...
call venv\Scripts\activate
pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo Running migrations...
alembic upgrade head
if errorlevel 1 exit /b 1

cd ..

echo.
echo [INFO] Setting up Frontend...
cd frontend
call npm ci
if errorlevel 1 exit /b 1
cd ..

echo.
echo ======================================
echo    Setup Complete!
echo ======================================
echo 1. Update backend\.env with your API keys.
echo 2. Run start.bat to launch the application.
pause
