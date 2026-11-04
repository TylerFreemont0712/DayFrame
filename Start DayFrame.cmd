@echo off
cd /d "%~dp0"
if exist "release\native-0.5.0\DayFrame\DayFrame.exe" (
    start "" "release\native-0.5.0\DayFrame\DayFrame.exe" %*
    exit /b
)
if exist "dist\DayFrame\DayFrame.exe" (
    start "" "dist\DayFrame\DayFrame.exe" %*
    exit /b
)
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "app.py" %*
    exit /b
)
echo Run scripts\setup-windows.ps1 to prepare the Python environment.
pause
