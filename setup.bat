@echo off
REM ═══════════════════════════════════════════════════════
REM  XCRDownloader — Windows Setup Script
REM  Creates venv, installs all deps, builds .exe via PyInstaller
REM ═══════════════════════════════════════════════════════
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

echo.
echo ╔══════════════════════════════════════════════╗
echo ║   ⚡ XCRDownloader — Windows Setup           ║
echo ╚══════════════════════════════════════════════╝
echo.

cd /d "%~dp0"

REM ─── Check Python ───
where python >nul 2>&1
if errorlevel 1 (
    echo ❌ Python not found. Install Python 3.10+ from https://python.org
    echo    Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)
for /f "delims=" %%i in ('python --version 2^>^&1') do set PY_VER=%%i
echo ✅ Found: %PY_VER%

REM ─── Check ffmpeg ───
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo ⚠  ffmpeg not found in PATH.
    echo    Install via: winget install Gyan.FFmpeg
    echo    Or download from: https://www.gyan.dev/ffmpeg/builds/
    echo.
    set /p CONT="   Continue without ffmpeg? (y/N): "
    if /i not "!CONT!"=="y" exit /b 1
) else (
    echo ✅ ffmpeg found
)

REM ─── Create venv ───
echo.
echo 📦 Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo ❌ Failed to create venv
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
pip install --upgrade pip -q

REM ─── Install dependencies ───
echo 📦 Installing Python dependencies...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo ❌ Failed to install dependencies
    pause
    exit /b 1
)
echo ✅ All packages installed

REM ─── Build .exe ───
echo.
set /p BUILD="🔨 Build standalone .exe? (Y/n): "
if /i not "!BUILD!"=="n" (
    echo 🔨 Building XCRDownloader.exe with PyInstaller...
    python build.py
    if exist "dist\XCRDownloader.exe" (
        echo ✅ Build complete! dist\XCRDownloader.exe
    ) else (
        echo ❌ Build failed. Check output above.
    )
)

echo.
echo ════════════════════════════════════════════════
echo  ✅ Setup complete!
echo ════════════════════════════════════════════════
echo.
echo   Usage:
echo     venv\Scripts\activate
echo     python cli.py ^<URL^>
echo     python cli.py --web
echo.
echo   Or run the .exe directly:
echo     dist\XCRDownloader.exe ^<URL^>
echo     dist\XCRDownloader.exe --web
echo.
pause
