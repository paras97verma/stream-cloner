@echo off
REM ==============================================================================
REM Stream Cloner — One-Command Windows .EXE Builder
REM Usage: Double-click scripts\build\build-windows-exe.bat
REM Produces: dist\Stream-Cloner-Windows.exe
REM ==============================================================================
setlocal EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%..\..\"
set "PROJECT_ROOT=%CD%"
set "VENV_DIR=%PROJECT_ROOT%\.venv"

echo ==============================================================
echo   Building Standalone Windows Executable: Stream-Cloner.exe
echo ==============================================================

if not exist "%VENV_DIR%\Scripts\python.exe" (
    where uv >nul 2>nul
    if %ERRORLEVEL% EQU 0 (
        uv venv --python 3.12 "%VENV_DIR%" 2>nul || uv venv "%VENV_DIR%"
    ) else (
        py -3.12 -m venv "%VENV_DIR%" 2>nul || py -3 -m venv "%VENV_DIR%" 2>nul || python -m venv "%VENV_DIR%"
    )
)

echo [1/2] Installing PyInstaller ^& bundling dependencies...
where uv >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    uv pip install --python "%VENV_DIR%\Scripts\python.exe" -U -r "%PROJECT_ROOT%\requirements.txt"
    uv pip install --python "%VENV_DIR%\Scripts\python.exe" -U "yt-dlp[default]" deno yt-dlp-ejs pyinstaller
) else (
    "%VENV_DIR%\Scripts\pip.exe" install -U -r "%PROJECT_ROOT%\requirements.txt"
    "%VENV_DIR%\Scripts\pip.exe" install -U "yt-dlp[default]" deno yt-dlp-ejs pyinstaller
)

echo [2/2] Compiling standalone dist\Stream-Cloner-Windows.exe ...
"%VENV_DIR%\Scripts\python.exe" "%SCRIPT_DIR%build_installer.py"

echo ==============================================================
echo [OK] Build complete! Your standalone .exe is located at:
echo      %PROJECT_ROOT%\dist\Stream-Cloner-Windows.exe
echo ==============================================================
explorer /select,"%PROJECT_ROOT%\dist\Stream-Cloner-Windows.exe"
pause

