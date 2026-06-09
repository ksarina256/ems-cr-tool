@echo off
title EMS CR Validation Tool

echo ================================================
echo   EMS CR Validation Tool
echo ================================================
echo.

REM Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.8 or higher.
    pause
    exit /b 1
)

REM Install dependencies if needed
echo Checking dependencies...
pip show flask >nul 2>&1
if errorlevel 1 (
    echo Installing Flask...
    pip install flask
)

echo.
echo Starting server...
echo Open your browser to: http://localhost:5000
echo.
echo Press Ctrl+C to stop the tool.
echo.

REM Open browser after short delay
start /b cmd /c "timeout /t 2 >nul && start http://localhost:5000"

REM Start the Flask server
cd /d "%~dp0backend"
python app.py

pause
