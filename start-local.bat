@echo off
REM Local Development Startup Script for Phase 1 Batch Processing
REM Usage: start-local.bat

setlocal enabledelayedexpansion

echo ==========================================
echo Dr. Mohan's Sentiment Analysis - Phase 1
echo Local Batch Processing Setup
echo ==========================================
echo.

REM Check if .env exists
if not exist ".env" (
    echo Error: .env file not found
    echo Please run: copy .env.example .env
    echo Then edit .env with your API keys
    pause
    exit /b 1
)

echo Creating necessary directories...
if not exist "data\uploads" mkdir data\uploads
if not exist "data\reports" mkdir data\reports
if not exist "backend\logs" mkdir backend\logs
echo OK
echo.

REM Start Backend
echo Starting Backend...
cd backend

REM Check if venv exists
if not exist "venv" (
    echo Creating Python virtual environment...
    python -m venv venv
)

REM Activate venv
call venv\Scripts\activate.bat

REM Install requirements
echo Checking Python dependencies...
pip install -q -r requirements.txt

REM Start backend in a new window
echo Starting FastAPI server on http://localhost:8000...
start "Backend Server" /D "." python -m uvicorn app.main:app --reload --port 8000
timeout /t 3 /nobreak

REM Start Frontend
echo.
echo Starting Frontend...
cd ..\frontend

REM Check if node_modules exists
if not exist "node_modules" (
    echo Installing npm dependencies (this may take a minute)...
    call npm install -q
)

REM Create .env.local if it doesn't exist
if not exist ".env.local" (
    (
        echo VITE_API_URL=http://localhost:8000/api
        echo VITE_ADMIN_USERNAME=admin
        echo VITE_ADMIN_PASSWORD=changeme
    ) > .env.local
    echo Frontend .env.local created
)

REM Start frontend in a new window
echo Starting Vite dev server on http://localhost:5173...
start "Frontend Server" /D "." cmd /k npm run dev

echo.
echo ==========================================
echo Phase 1 Local Setup Started!
echo ==========================================
echo.
echo Services running:
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:5173
echo   API Docs: http://localhost:8000/docs
echo.
echo To use the application:
echo   1. Open http://localhost:5173 in your browser
echo   2. Go to 'Batch Processing' tab
echo   3. Upload 5+ audio files
echo   4. Enter batch name and start processing
echo   5. Watch progress on Dashboard tab
echo.
echo To stop services, close the console windows
echo.
pause
