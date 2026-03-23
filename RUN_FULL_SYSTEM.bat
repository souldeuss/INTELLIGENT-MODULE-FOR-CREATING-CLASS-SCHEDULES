@echo off
chcp 65001 > nul
title Full System Launcher - Timetabling System

echo.
echo ═══════════════════════════════════════════════════════════════
echo   🚀 INTELLIGENT TIMETABLING SYSTEM - FULL LAUNCHER
echo ═══════════════════════════════════════════════════════════════
echo.
echo   Цей скрипт запустить весь стек:
echo   1️⃣  Backend Server (FastAPI + DRL Engine)
echo   2️⃣  Web UI (React Frontend)
echo.
echo ═══════════════════════════════════════════════════════════════
echo.

:: Перевірка Python
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Python не знайдено! Встановіть Python 3.8+
    pause
    exit /b 1
)

:: Перевірка Node.js
where node >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Node.js не знайдено! Встановіть Node.js з https://nodejs.org/
    pause
    exit /b 1
)

echo ✅ Python: 
python --version
echo ✅ Node.js: 
node --version
echo.

:: Перевірка залежностей Backend
echo 📦 Перевірка Backend залежностей...
cd backend
pip show fastapi >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ⚠ Backend залежності не встановлені
    echo.
    choice /M "Встановити Backend залежності (потрібно ~5 хв)"
    if %ERRORLEVEL% EQU 1 (
        pip install -r requirements.txt
        echo ✅ Backend залежності встановлені
    ) else (
        echo ❌ Не можу продовжити без залежностей
        pause
        exit /b 1
    )
)
cd ..

:: Перевірка залежностей Frontend
echo 📦 Перевірка Frontend залежностей...
if not exist "frontend\node_modules\" (
    echo ⚠ Frontend залежності не встановлені
    echo.
    choice /M "Встановити Frontend залежності (потрібно ~3 хв)"
    if %ERRORLEVEL% EQU 1 (
        cd frontend
        call npm install
        cd ..
        echo ✅ Frontend залежності встановлені
    ) else (
        echo ❌ Не можу продовжити без залежностей
        pause
        exit /b 1
    )
)

:: Перевірка бази даних
if not exist "backend\timetabling.db" (
    echo.
    echo ⚠ База даних не знайдена
    echo.
    choice /M "Створити базу даних з тестовими даними"
    if %ERRORLEVEL% EQU 1 (
        cd backend
        python populate_db.py
        cd ..
        echo ✅ База даних створена
    )
)

echo.
echo ═══════════════════════════════════════════════════════════════
echo   ✅ ВСЕ ГОТОВО! ЗАПУСК СИСТЕМИ...
echo ═══════════════════════════════════════════════════════════════
echo.

:: Запуск Backend у новому вікні
echo 🚀 Запуск Backend Server...
start "Backend Server - Port 8000" cmd /k "cd /d "%CD%\backend" && python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"

:: Пауза щоб backend встиг запуститись
echo ⏳ Чекаю 5 секунд поки Backend запуститься...
timeout /t 5 /nobreak > nul

:: Запуск Frontend у новому вікні
echo 🌐 Запуск Web UI...
start "Web UI - Port 3000" cmd /k "cd /d "%CD%\frontend" && npm start"

echo.
echo ═══════════════════════════════════════════════════════════════
echo   ✅ СИСТЕМА ЗАПУЩЕНА!
echo ═══════════════════════════════════════════════════════════════
echo.
echo   📍 Відкриті сервіси:
echo.
echo   🌐 Web UI:          http://localhost:3000
echo   🔧 Backend API:     http://localhost:8000
echo   📚 API Docs:        http://localhost:8000/docs
echo.
echo   ℹ️  Відкрилися два нових вікна терміналу:
echo      - Backend Server (не закривайте!)
echo      - Web UI (не закривайте!)
echo.
echo   💡 Через ~10 секунд браузер автоматично відкриється
echo.
echo   🛑 Щоб зупинити систему:
echo      Закрийте обидва вікна терміналу або натисніть Ctrl+C
echo.
echo ═══════════════════════════════════════════════════════════════
echo.

:: Пауза і автоматичне відкриття браузера
timeout /t 10 /nobreak > nul
start http://localhost:3000

echo ✅ Браузер відкрито!
echo.
echo Це вікно можна закрити.
echo.
pause
