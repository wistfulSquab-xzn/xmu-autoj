@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo   XMUOJ 自动答题 - 环境检查
echo   ─────────────────────────

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo   [错误] 未找到 Python！
    echo   请先安装 Python 3.10+：
    echo   https://www.python.org/downloads/
    echo   安装时务必勾选 "Add Python to PATH"
    echo.
    pause
    exit /b 1
)
echo   [OK] Python 已安装

REM 检查依赖包
python -c "import playwright, bs4, anthropic, openai" >nul 2>&1
if errorlevel 1 (
    echo.
    echo   [安装] 正在安装依赖包，请稍候...
    pip install playwright beautifulsoup4 anthropic openai -q
    if errorlevel 1 (
        echo   [错误] 依赖包安装失败，请手动运行：
        echo   pip install playwright beautifulsoup4 anthropic openai
        pause
        exit /b 1
    )
    echo   [OK] 依赖包安装完成
) else (
    echo   [OK] 依赖包已就绪
)

REM 检查 Playwright 浏览器
python -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); p.chromium.launch(); p.stop()" >nul 2>&1
if errorlevel 1 (
    echo.
    echo   [安装] 正在下载浏览器，约 180MB，请稍候...
    python -m playwright install chromium
    echo   [OK] 浏览器安装完成
) else (
    echo   [OK] 浏览器已就绪
)

echo   [OK] 环境检查通过，启动中...
echo.
python start.py
pause
