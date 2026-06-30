@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
set PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright/
python setup_check.py
if %errorlevel% neq 0 (
    echo.
    echo Python not found or setup failed.
    echo Install Python 3.8+: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)
python start.py
pause
