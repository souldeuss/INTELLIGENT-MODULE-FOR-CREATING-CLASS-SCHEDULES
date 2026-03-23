@echo off
echo ========================================
echo   Intelligent Scheduling System GUI
echo ========================================
echo.
echo Starting graphical interface...
echo.

python gui_app.py

if errorlevel 1 (
    echo.
    echo ERROR: Failed to start GUI
    echo.
    echo Please make sure:
    echo 1. Python is installed
    echo 2. tkinter is available
    echo.
    pause
)
