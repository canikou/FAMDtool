@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%tools\build_release.ps1"

if errorlevel 1 (
    echo.
    echo Release build failed.
    pause
    exit /b 1
)

echo.
echo Release build complete.
pause
