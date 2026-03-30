@echo off
chcp 65001 > nul
title Backend Server - Timetabling System

echo.
echo ═══════════════════════════════════════════════════════════════
echo   🚀 Backend Server Launcher - DRL Timetabling System
echo ═══════════════════════════════════════════════════════════════
echo.

:: Перевірка чи встановлений Python
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Python не знайдено!
    echo.
    echo Будь ласка, встановіть Python 3.8+ з https://www.python.org/
    echo.
    pause
    exit /b 1
)

echo ✅ Python знайдено: 
python --version
echo.

:: Перевірка та створення віртуального середовища (опціонально)
if not exist "backend\venv\" (
    echo ⚠ Віртуальне середовище не знайдено.
    echo Рекомендується створити його для ізоляції залежностей.
    echo.
    choice /M "Створити віртуальне середовище"
    if %ERRORLEVEL% EQU 1 (
        echo Створення віртуального середовища...
        python -m venv backend\venv
        echo ✅ Віртуальне середовище створено
        echo.
    )
)

:: Активація віртуального середовища якщо існує
if exist "backend\venv\Scripts\activate.bat" (
    echo 📦 Активація віртуального середовища...
    call backend\venv\Scripts\activate.bat
    echo.
)

:: Перевірка залежностей
echo 📦 Перевірка залежностей...
cd backend
pip show fastapi >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ⚠ Залежності не встановлені. Встановлюю...
    echo.
    pip install -r requirements.txt
    echo.
    echo ✅ Залежності встановлені
    echo.
)

:: Перевірка бази даних
if not exist "timetabling.db" (
    echo ⚠ База даних не знайдена
    echo.
    choice /M "Створити та наповнити базу даних тестовими даними"
    if %ERRORLEVEL% EQU 1 (
        echo Наповнення бази даних...
        python populate_db.py
        echo.
        echo ✅ База даних створена та наповнена
        echo.
    )
)

:: Перевірка чи backend вже працює
echo 🔍 Перевірка чи Backend вже запущений...
netstat -ano | findstr :8000 | findstr LISTENING >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✅ Backend вже працює на порту 8000!
    echo.
    echo   🌐 API Documentation: http://127.0.0.1:8000/docs
    echo   📊 Alternative Docs: http://127.0.0.1:8000/redoc
    echo   🔧 Health Check: http://127.0.0.1:8000/
    echo   📡 LAN URL: http://YOUR_PC_IP:8000/docs
    echo.
    echo 💡 Якщо потрібно перезапустити, спочатку зупиніть існуючий процес:
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
        echo    Команда: taskkill /PID %%a /F
    )
    echo.
    pause
    exit /b 0
)

echo ══════════════════════════════════════════════════════════════
echo   ✅ Все готово! Запуск Backend Server...
echo ══════════════════════════════════════════════════════════════
echo.
echo   🌐 API Documentation: http://127.0.0.1:8000/docs
echo   📊 Alternative Docs: http://127.0.0.1:8000/redoc
echo   🔧 Health Check: http://127.0.0.1:8000/
echo   📡 LAN URL: http://YOUR_PC_IP:8000/docs
echo.
echo   Натисніть Ctrl+C, щоб зупинити сервер
echo ══════════════════════════════════════════════════════════════
echo.

python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
