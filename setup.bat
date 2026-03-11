@echo off
echo Setting up Amenity Scorer Environment...

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed or not added to PATH. Please install Python 3.9+.
    pause
    exit /b 1
)

REM Create virtual environment if it doesn't exist
if not exist venv (
    echo Creating virtual environment (venv)...
    python -m venv venv
) else (
    echo Virtual environment 'venv' already exists.
)

echo.
echo Activating virtual environment and installing dependencies...
call venv\Scripts\activate.bat

if exist amenity_scorer\requirements.txt (
    pip install -r amenity_scorer\requirements.txt
) else (
    echo WARNING: amenity_scorer\requirements.txt not found. 
    echo Please ensure dependencies are installed manually.
)

echo.
echo =======================================================
echo Setup Complete!
echo.
echo To run the script manually, open a prompt and type:
echo 1. call venv\Scripts\activate.bat
echo 2. cd amenity_scorer
echo 3. python main.py --lat 18.9057 --lon 72.8101
echo =======================================================
echo.
pause
