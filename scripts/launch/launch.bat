@echo off
REM ==============================================================================
REM Stream Cloner — Windows One-Click Setup & Launcher
REM Usage: Double-click scripts\launch\launch.bat or run with [--reinstall | --update]
REM ==============================================================================
setlocal EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%..\..\"
set "PROJECT_ROOT=%CD%"
set "VENV_DIR=%PROJECT_ROOT%\.venv"
set "MARKER_FILE=%VENV_DIR%\.setup_version"
set "CURRENT_SETUP_VER=7"

echo ==============================================================
echo   Stream Cloner — Windows YouTube Video ^& Playlist Studio
echo ==============================================================

set "FORCE_SETUP=0"
set "UPDATE_YTDLP=0"
for %%A in (%*) do (
    if /I "%%~A"=="--reinstall" set "FORCE_SETUP=1"
    if /I "%%~A"=="--setup" set "FORCE_SETUP=1"
    if /I "%%~A"=="--update" set "UPDATE_YTDLP=1"
)

set "HAS_UV=0"
where uv >nul 2>nul
if %ERRORLEVEL% EQU 0 set "HAS_UV=1"

set "PYTHON_CMD="
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    py -3.12 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul && set "PYTHON_CMD=py -3.12"
    if not defined PYTHON_CMD (
        py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul && set "PYTHON_CMD=py -3"
    )
)
if not defined PYTHON_CMD (
    where python >nul 2>nul
    if %ERRORLEVEL% EQU 0 (
        python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul && set "PYTHON_CMD=python"
    )
)

if "%HAS_UV%"=="0" if not defined PYTHON_CMD (
    echo [!] Python 3.10+ was not found on this Windows PC.
    echo Please install Python 3.12 from https://www.python.org/downloads/windows/
    echo ^(Make sure to check "Add python.exe to PATH" during installation^)
    pause
    exit /b 1
)

set "INSTALLED_VER=0"
if exist "%MARKER_FILE%" (
    set /p INSTALLED_VER=<"%MARKER_FILE%"
)

set "NEEDS_FULL_SETUP=0"
set "NEEDS_UPDATE=0"

if "%FORCE_SETUP%"=="1" set "NEEDS_FULL_SETUP=1"
if not exist "%VENV_DIR%\Scripts\python.exe" set "NEEDS_FULL_SETUP=1"

if "%NEEDS_FULL_SETUP%"=="0" (
    if not "%INSTALLED_VER%"=="%CURRENT_SETUP_VER%" set "NEEDS_UPDATE=1"
    if "%UPDATE_YTDLP%"=="1" set "NEEDS_UPDATE=1"
)

if "%NEEDS_FULL_SETUP%"=="1" (
    echo [1/3] Creating virtual environment in .venv ...
    if exist "%VENV_DIR%" rmdir /s /q "%VENV_DIR%"
    if "%HAS_UV%"=="1" (
        echo [*] Using uv environment manager...
        uv venv --python 3.12 "%VENV_DIR%" 2>nul || uv venv "%VENV_DIR%"
    ) else (
        %PYTHON_CMD% -m venv "%VENV_DIR%"
    )

    echo [2/3] Installing dependencies ^(yt-dlp, pywebview, bottle, Pillow, FFmpeg^)...
    if "%HAS_UV%"=="1" (
        uv pip install --python "%VENV_DIR%\Scripts\python.exe" -U -r "%PROJECT_ROOT%\requirements.txt"
        uv pip install --python "%VENV_DIR%\Scripts\python.exe" -U "yt-dlp[default]" deno yt-dlp-ejs 2>nul
    ) else (
        "%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip wheel setuptools --quiet
        "%VENV_DIR%\Scripts\pip.exe" install -U -r "%PROJECT_ROOT%\requirements.txt"
        "%VENV_DIR%\Scripts\pip.exe" install -U "yt-dlp[default]" deno yt-dlp-ejs 2>nul
    )

    echo [3/3] Verifying standalone FFmpeg binary for Windows...
    where ffmpeg >nul 2>nul
    if %ERRORLEVEL% NEQ 0 (
        for /f "delims=" %%F in ('"%VENV_DIR%\Scripts\python.exe" -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())" 2^>nul') do (
            if exist "%%F" copy /Y "%%F" "%VENV_DIR%\Scripts\ffmpeg.exe" >nul
        )
    )
    >"%MARKER_FILE%" echo %CURRENT_SETUP_VER%
    echo [OK] Setup complete!
) else if "%NEEDS_UPDATE%"=="1" (
    echo [*] Updating dependencies...
    if "%HAS_UV%"=="1" (
        uv pip install --python "%VENV_DIR%\Scripts\python.exe" -U -r "%PROJECT_ROOT%\requirements.txt"
    ) else (
        "%VENV_DIR%\Scripts\pip.exe" install -U -r "%PROJECT_ROOT%\requirements.txt" --quiet
    )
    >"%MARKER_FILE%" echo %CURRENT_SETUP_VER%
    echo [OK] Environment updated!
) else (
    echo [OK] Environment verified.
)

if not exist "%PROJECT_ROOT%\src\stream_cloner\web\dist\index.html" (
    echo [*] Compiling Vue.js frontend production bundle...
    where npm >nul 2>nul
    if %ERRORLEVEL% EQU 0 (
        npm --prefix "%PROJECT_ROOT%\frontend" run build
    )
)

set "PATH=%VENV_DIR%\Scripts;%PATH%"
echo [*] Starting Stream Cloner...
start "" "%VENV_DIR%\Scripts\pythonw.exe" "%PROJECT_ROOT%\app.py"
if %ERRORLEVEL% NEQ 0 (
    "%VENV_DIR%\Scripts\python.exe" "%PROJECT_ROOT%\app.py"
)
endlocal

