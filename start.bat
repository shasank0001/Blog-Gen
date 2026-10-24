@echo off
cd /d "%~dp0"
echo Starting Blog-Gen...

echo Validating setup...
if not exist backend\venv (
    echo [ERROR] Virtual environment not found.
    echo Please run setup.bat first.
    pause
    exit /b 1
)

if not exist backend\.env (
    echo [ERROR] backend\.env not found.
    echo Please run setup.bat and configure your API keys.
    pause
    exit /b 1
)

if not exist frontend\node_modules (
    echo [ERROR] Frontend dependencies not installed.
    echo Please run setup.bat first.
    pause
    exit /b 1
)

echo Starting Backend...
cd backend
call venv\Scripts\activate
docker compose up -d --wait --wait-timeout 60 db
if errorlevel 1 exit /b 1
alembic upgrade head
if errorlevel 1 exit /b 1
start "Blog-Gen Worker" cmd /k "call venv\Scripts\activate && python -m app.worker"
:: Opens a new window for the backend
start "Blog-Gen Backend" cmd /k "call venv\Scripts\activate && uvicorn app.main:app --reload"
cd ..

echo Starting Frontend...
cd frontend
:: Opens a new window for the frontend
start "Blog-Gen Frontend" cmd /k "npm run dev"
cd ..

echo.
echo Application is launching in separate windows!
echo Frontend: http://localhost:5173
echo Backend:  http://localhost:8000/docs
echo.
echo Close the new windows to stop the servers.
pause
