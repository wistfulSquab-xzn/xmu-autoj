@echo off
cd /d "%~dp0"
set PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright/
python setup_check.py 2>nul
if %errorlevel% neq 0 (
    echo Python not found! Install: https://www.python.org/downloads/
    pause
    exit /b 1
)
python start.py
pause
