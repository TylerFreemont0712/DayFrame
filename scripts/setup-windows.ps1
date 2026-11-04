$ErrorActionPreference = "Stop"
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
python -m venv .venv
if ($LASTEXITCODE -ne 0) { throw "Python 3.11 is required. Install it and run this script again." }
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
Write-Host "Ready. Open Start DayFrame.cmd."
