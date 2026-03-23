@echo off
chcp 65001 > nul
title Web UI Launcher - Timetabling System

echo.
echo ═══════════════════════════════════════════════════════════════
echo   🌐 Web UI Launcher - Intelligent Timetabling System
echo ═══════════════════════════════════════════════════════════════
echo.

:: Перевірка чи встановлений Node.js
where node >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Node.js не знайдено!
    echo.
    echo Будь ласка, встановіть Node.js з https://nodejs.org/
    echo.
    pause
    exit /b 1
)

echo ✅ Node.js знайдено: 
node --version
echo.

:: Перевірка чи встановлені залежності
if not exist "frontend\node_modules\" (
    echo ⚠ Залежності не встановлені. Встановлюю...
    echo.
    cd frontend
    call npm install
    cd ..
    echo.
)

echo ══════════════════════════════════════════════════════════════
echo   ВАЖЛИВО: Спочатку запустіть Backend!
echo ══════════════════════════════════════════════════════════════
echo.
echo   Якщо Backend ще не запущений, виконайте у іншому терміналі:
echo.
echo   cd backend
echo   python -m uvicorn app.main:app --reload
echo.
echo ══════════════════════════════════════════════════════════════
echo.

:: Пауза для перевірки
echo Натисніть будь-яку клавішу, щоб запустити Web UI...
pause > nul

echo.
echo 🚀 Запуск React Frontend...
echo.
echo Web UI буде доступний за адресою: http://localhost:3000
echo Backend API повинен працювати на: http://localhost:8000
echo.
echo Натисніть Ctrl+C, щоб зупинити сервер
echo.
echo ══════════════════════════════════════════════════════════════
echo.

cd frontend
npm start
