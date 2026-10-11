@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo   AI-Powered Resume Analyzer
echo ==========================================

rem --- If the virtual environment does not exist yet, create it and install the PINNED packages ---
if not exist "venv\Scripts\python.exe" (
    echo.
    echo [Setup] Virtual environment not found. Creating it with Python 3.12...
    py -3.12 --version >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Python 3.12 was not found.
        echo Install Python 3.12 from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
        pause
        exit /b 1
    )
    py -3.12 -m venv venv
    if errorlevel 1 (
        echo ERROR: Could not create the virtual environment.
        pause
        exit /b 1
    )
    echo [Setup] Installing the packages listed in requirements.txt. This can take several minutes...
    "venv\Scripts\python.exe" -m pip install --upgrade pip
    "venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERROR: Package installation failed. Removing the incomplete venv so the next run starts clean.
        rmdir /s /q venv
        pause
        exit /b 1
    )
)

rem --- Make sure the existing venv really is Python 3.12 ---
"venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)"
if errorlevel 1 (
    echo ERROR: The venv folder was not created with Python 3.12.
    echo Delete the venv folder and run this file again.
    pause
    exit /b 1
)

echo.
echo Starting the app. When you see "Running on http://127.0.0.1:5000", open that address in your browser.
echo Press Ctrl+C in this window to stop the server.
echo.
"venv\Scripts\python.exe" app.py

pause
