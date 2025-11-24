@echo off
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
npm --version >nul 2>&1
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
    echo [IMPORTANT] Update backend\.env with your API keys!
) else (
    echo .env file already exists.
)

echo Starting Docker containers...
docker-compose up -d

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

echo Installing dependencies...
call venv\Scripts\activate
pip install -r requirements.txt

echo Running migrations...
echo Waiting for database to be ready...
set max_attempts=30
set attempt=0
:waitloop
set /a attempt+=1
docker exec blog_gen_db pg_isready -U user -d blog_gen >nul 2>&1
if %errorlevel% equ 0 goto dbready
if %attempt% geq %max_attempts% (
    echo Warning: Database not ready after 30 seconds. Continuing anyway...
    goto dbready
)
echo Waiting for database... (%attempt%/%max_attempts%)
timeout /t 1 /nobreak >nul
goto waitloop
:dbready
echo Database is ready!
alembic upgrade head

cd ..

echo.
echo [INFO] Setting up Frontend...
cd frontend
call npm install
cd ..

echo.
echo ======================================
echo    Setup Complete!
echo ======================================
echo 1. Update backend\.env with your API keys.
echo 2. Run start.bat to launch the application.
pause
