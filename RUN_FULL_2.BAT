@echo off
chcp 65001 > nul
title Full System Launcher - Timetabling System

echo.
echo ===============================================================
echo   INTELLIGENT TIMETABLING SYSTEM - FULL LAUNCHER
echo ===============================================================
echo.
echo   This script will start the full stack:
echo   1) Backend Server (FastAPI + DRL Engine)
echo   2) Web UI (React Frontend)
echo.
echo ===============================================================
echo.

:: Check Python
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python not found! Install Python 3.8+
    pause
    exit /b 1
)

:: Check Node.js
where node >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Node.js not found! Install Node.js from https://nodejs.org/
    pause
    exit /b 1
)

echo [OK] Python:
python --version
echo [OK] Node.js:
node --version
echo.

:: Detect LAN IP for access hints from another PC
set "LAN_IP="
for /f "tokens=2 delims=:" %%i in ('ipconfig ^| findstr /R /C:"IPv4"') do (
    for /f "tokens=* delims= " %%j in ("%%i") do (
        if not defined LAN_IP set "LAN_IP=%%j"
    )
)
if not defined LAN_IP set "LAN_IP=127.0.0.1"

:: Check Backend dependencies
echo [INFO] Checking Backend dependencies...
cd backend
pip show fastapi >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [WARN] Backend dependencies are not installed
    echo.
    choice /M "Install Backend dependencies (about 5 min)"
    if errorlevel 2 (
        echo [ERROR] Cannot continue without dependencies
        pause
        exit /b 1
    ) else (
        pip install -r requirements.txt
        echo [OK] Backend dependencies installed
    )
)
cd ..

:: Check Frontend dependencies
echo [INFO] Checking Frontend dependencies...
if not exist "frontend\node_modules\" (
    echo [WARN] Frontend dependencies are not installed
    echo.
    choice /M "Install Frontend dependencies (about 3 min)"
    if errorlevel 2 (
        echo [ERROR] Cannot continue without dependencies
        pause
        exit /b 1
    ) else (
        cd frontend
        call npm install
        cd ..
        echo [OK] Frontend dependencies installed
    )
)

:: Check database
if not exist "backend\timetabling.db" (
    echo.
    echo [WARN] Database not found
    echo.
    choice /M "Create database with test data"
    if not errorlevel 2 (
        cd backend
        python populate_db.py
        cd ..
        echo [OK] Database created
    )
)

echo.
echo ===============================================================
echo   READY! STARTING SYSTEM...
echo ===============================================================
echo.

:: Start Backend in new window
echo [INFO] Starting Backend Server...
start "Backend Server - Port 8000" cmd /k "cd /d "%CD%\backend" && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

:: Wait for backend to start
echo [INFO] Waiting 5 seconds for Backend startup...
timeout /t 5 /nobreak > nul

:: Start Frontend in new window
echo [INFO] Starting Web UI...
start "Web UI - Port 3000" cmd /k "cd /d "%CD%\frontend" && set "HOST=0.0.0.0" && npm start"

echo.
echo ===============================================================
echo   SYSTEM STARTED
echo ===============================================================
echo.
echo   Available services:
echo.
echo   Web UI:          http://localhost:3000
echo   Backend API:     http://localhost:8000
echo   API Docs:        http://localhost:8000/docs
echo.
echo   LAN access from another PC:
echo   Web UI:          http://%LAN_IP%:3000
echo   Backend API:     http://%LAN_IP%:8000
echo   API Docs:        http://%LAN_IP%:8000/docs
echo.
echo   Two new terminal windows were opened:
echo   - Backend Server (do not close)
echo   - Web UI (do not close)
echo.
echo   Browser will open automatically in about 10 seconds
echo.
echo   To stop the system:
echo   Close both terminal windows or press Ctrl+C
echo.
echo ===============================================================
echo.

:: Wait and open browser
timeout /t 10 /nobreak > nul
start http://localhost:3000

echo [OK] Browser opened
echo.
echo You can close this window.
echo.
pause
