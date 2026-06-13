@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating local virtual environment...
    python -m venv .venv
    if errorlevel 1 goto error
)

".venv\Scripts\python.exe" -c "import PIL" >nul 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto error
)

echo Starting FAMD Tool ni Yeol...
".venv\Scripts\python.exe" "famd_tool.py"
if errorlevel 1 goto error

exit /b 0

:error
echo.
echo Something went wrong. Press any key to close.
pause >nul
exit /b 1
