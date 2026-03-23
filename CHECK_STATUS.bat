@echo off
chcp 65001 > nul
title System Status Check - Timetabling System

echo.
echo ═══════════════════════════════════════════════════════════════
echo   🔍 SYSTEM STATUS CHECK
echo ═══════════════════════════════════════════════════════════════
echo.

:: Check Backend
echo 🔧 Backend Server (Port 8000):
netstat -ano | findstr :8000 | findstr LISTENING >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   ✅ RUNNING
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
        echo   📍 Process ID: %%a
    )
    echo   🌐 URL: http://127.0.0.1:8000
    echo   📚 Docs: http://127.0.0.1:8000/docs
) else (
    echo   ❌ NOT RUNNING
    echo   💡 Start with: RUN_BACKEND.bat
)

echo.

:: Check Frontend
echo 🌐 Web UI (Port 3000):
netstat -ano | findstr :3000 | findstr LISTENING >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   ✅ RUNNING
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do (
        echo   📍 Process ID: %%a
    )
    echo   🌐 URL: http://localhost:3000
) else (
    echo   ❌ NOT RUNNING
    echo   💡 Start with: RUN_WEB_UI.bat
)

echo.
echo ═══════════════════════════════════════════════════════════════

:: Test Backend API if running
netstat -ano | findstr :8000 | findstr LISTENING >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo.
    echo 🧪 Testing Backend API...
    python -c "import requests; r = requests.get('http://127.0.0.1:8000/api/courses'); print(f'  Courses: {len(r.json())}'); r = requests.get('http://127.0.0.1:8000/api/teachers'); print(f'  Teachers: {len(r.json())}'); r = requests.get('http://127.0.0.1:8000/api/groups'); print(f'  Groups: {len(r.json())}'); r = requests.get('http://127.0.0.1:8000/api/classrooms'); print(f'  Classrooms: {len(r.json())}'); r = requests.get('http://127.0.0.1:8000/api/timeslots'); print(f'  Timeslots: {len(r.json())}'); print('  ✅ API is working!')" 2>nul
    if errorlevel 1 (
        echo   ⚠️  API test failed - but server is running
    )
)

echo.
echo ═══════════════════════════════════════════════════════════════
echo.
pause
