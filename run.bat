@echo off
REM ==============================================================================
REM Stream Cloner — Windows Local Application Launcher
REM Directly starts the standalone Vue.js + Python desktop app locally.
REM Distribution packaging (EXE) is built separately via 'make exe' or GitHub workflow.
REM ==============================================================================
setlocal EnableDelayedExpansion

set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

echo ==============================================================
echo    Stream Cloner — Native Desktop YouTube & Media Cloner
echo ==============================================================

set "VENV_DIR=%PROJECT_ROOT%.venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"

REM Ensure Python virtual environment exists
if not exist "%PYTHON_EXE%" (
    echo [*] Creating virtual environment in .venv ...
    python -m venv "%VENV_DIR%"
)

REM Ensure dependencies installed
"%PYTHON_EXE%" -c "import webview, bottle, yt_dlp" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [*] Installing required dependencies...
    "%PYTHON_EXE%" -m pip install -U -r requirements.txt
)

REM Ensure frontend build exists
if not exist "src\stream_cloner\web\dist\index.html" (
    echo [*] Building Vue.js frontend production bundle...
    where npm >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        npm --prefix frontend run build
    ) else (
        echo [!] npm was not found. Please install Node.js to build frontend assets.
        pause
        exit /b 1
    )
)

echo [*] Launching Stream Cloner Desktop App...
"%PYTHON_EXE%" app.py %*
exit /b %ERRORLEVEL%
