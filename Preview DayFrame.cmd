@echo off
rem Runs the current source version in a separate preview profile; see scripts\preview.ps1.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\preview.ps1" %*
if errorlevel 1 pause
