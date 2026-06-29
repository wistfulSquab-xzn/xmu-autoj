@echo off
cd /d "%~dp0"
python setup_check.py 2>nul
if %errorlevel% neq 0 (
    echo Python not found! Install: https://www.python.org/downloads/
    pause
    exit /b 1
)
python start.py
pause
