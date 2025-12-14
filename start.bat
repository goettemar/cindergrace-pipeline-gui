@echo off
REM CINDERGRACE GUI Launcher for Windows
setlocal enabledelayedexpansion

echo ========================================================
echo        CINDERGRACE Pipeline Control - GUI
echo ========================================================
echo.

REM Change to script directory
cd /d "%~dp0"

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [X] Python not found. Please install Python 3.10 or higher.
    echo     Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version') do echo [OK] %%i
echo.

REM Check if virtual environment exists
if not exist ".venv" (
    echo [..] Virtual environment not found. Creating...
    python -m venv .venv
    echo [OK] Virtual environment created
    echo.
)

REM Activate virtual environment
echo [..] Activating virtual environment...
call .venv\Scripts\activate.bat
echo [OK] Virtual environment activated
echo.

REM Install/update dependencies
echo [..] Checking and updating dependencies...
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
echo [OK] Dependencies up to date
echo.

REM Check workflow templates
set WORKFLOW_DIR=config\workflow_templates
set /a WORKFLOW_COUNT=0
for %%f in ("%WORKFLOW_DIR%\*.json") do set /a WORKFLOW_COUNT+=1

if %WORKFLOW_COUNT%==0 (
    echo [!] No workflow templates found in %WORKFLOW_DIR%
    echo     Please add your ComfyUI workflow JSON files there.
    echo.
) else (
    echo [OK] Found %WORKFLOW_COUNT% workflow template(s)
    echo.
)

REM Check if ComfyUI is running
echo [..] Checking ComfyUI connection...
curl -s http://127.0.0.1:8188/system_stats >nul 2>&1
if errorlevel 1 (
    echo [!] ComfyUI not detected at http://127.0.0.1:8188
    echo.
    echo     To start ComfyUI, run in a separate terminal:
    echo     cd C:\path\to\ComfyUI ^&^& python main.py
    echo.
    set /p CONTINUE="    Continue anyway? [Y/n] "
    if /i "!CONTINUE!"=="n" (
        echo Aborted.
        exit /b 1
    )
    echo.
) else (
    echo [OK] ComfyUI is running at http://127.0.0.1:8188
    echo.
)

REM Launch GUI
echo ========================================================
echo.
echo    Open your browser at: http://127.0.0.1:7860
echo.
echo    Press Ctrl+C to stop the GUI
echo.
echo ========================================================
echo.

python main.py

REM Deactivate venv on exit
call deactivate
