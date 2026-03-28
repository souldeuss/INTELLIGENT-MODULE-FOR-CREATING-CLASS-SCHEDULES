@echo off
chcp 65001 > nul
title Auto Compatible Training Pipeline

echo.
echo ================================================================
echo   AUTO COMPATIBLE PIPELINE
echo ================================================================
echo   1) Export DB reference case
echo   2) Generate compatible dataset
echo   3) Train/evaluate DRL model
echo   4) Activate model in both registries
echo   5) Run compatibility preflight
echo ================================================================
echo.

where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Python not found. Install Python 3.10+
    pause
    exit /b 1
)

python backend\auto_compatible_pipeline.py --workspace-root . %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Pipeline failed.
    pause
    exit /b 1
)

echo.
echo Pipeline completed successfully.
pause
