@echo off
setlocal enabledelayedexpansion
echo -------------------------------------------------------
echo  Amenity Scorer - Environment Setup
echo -------------------------------------------------------

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install Python 3.9+ and ensure it is in PATH.
    pause
    exit /b 1
)

:: Create venv if it does not exist
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: Activate
call venv\Scripts\activate.bat

:: Set UTF-8 encoding for the session to handle non-ASCII characters in addresses
set PYTHONIOENCODING=utf-8

:: Install dependencies
if exist "amenity_scorer\requirements.txt" (
    echo Upgrading pip...
    pip install --upgrade pip -q
    echo Installing dependencies...
    pip install -r amenity_scorer\requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Dependency installation failed.
        pause
        exit /b 1
    )
) else (
    echo [ERROR] amenity_scorer\requirements.txt not found.
    pause
    exit /b 1
)

echo.
echo -------------------------------------------------------
echo  Setup complete. Steps to run:
echo.
echo  1. Activate environment:
echo       venv\Scripts\activate
echo.
echo  2. Set encoding (once per terminal session):
echo       set PYTHONIOENCODING=utf-8
echo.
echo  3. Run from amenity_scorer\:
echo       python main.py --lat ^<LAT^> --lon ^<LON^>
echo       python main.py --input ..\data\location.csv --output ..\results\amenity_scores --workers 2
echo -------------------------------------------------------
pause