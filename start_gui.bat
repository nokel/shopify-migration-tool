@echo off
REM Simple launcher for the migration tool GUI
REM This launches the GUI without showing a console window

REM Check if pythonw.exe exists
where pythonw >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: pythonw.exe not found
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

REM Launch the GUI without console window
start "" pythonw main.pyw
