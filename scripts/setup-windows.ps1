param([string]$Python = '')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
$dayframeVersionProbe = 'import sys; print(sys.executable); sys.exit(0 if (3,12) <= sys.version_info[:2] < (3,15) else 1)'
if (!$Python) {
    foreach ($dayframeCandidate in @(@('py','-3.14'),@('py','-3.13'),@('py','-3.12'),@('python'))) {
        if (!(Get-Command $dayframeCandidate[0] -ErrorAction SilentlyContinue)) { continue }
        $dayframeArguments = @()
        if ($dayframeCandidate.Count -gt 1) { $dayframeArguments += $dayframeCandidate[1] }
        $dayframeArguments += @('-c',$dayframeVersionProbe)
        $dayframeProbe = & $dayframeCandidate[0] @dayframeArguments 2>$null
        if ($LASTEXITCODE -eq 0) { $Python = [string]($dayframeProbe | Select-Object -Last 1); break }
    }
}
if (!$Python) { throw 'Install Python 3.12–3.14 (3.14 recommended), or pass -Python with its executable path.' }
& $Python -c $dayframeVersionProbe
if ($LASTEXITCODE -ne 0) { throw 'DayFrame desktop requires Python 3.12–3.14; 3.14 is recommended.' }
if (Test-Path -LiteralPath '.venv\Scripts\python.exe') {
    & .\.venv\Scripts\python.exe -c $dayframeVersionProbe
    if ($LASTEXITCODE -ne 0) { throw 'Existing .venv uses an older Python. Preserve/rename it, then rerun setup with Python 3.14.' }
}
& $Python -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Could not create the DayFrame environment.' }
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
Write-Host 'Ready. Open Start DayFrame.cmd.'
