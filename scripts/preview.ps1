# Run the current source version of DayFrame in a separate preview profile.
#
#   scripts\preview.ps1               prepare .venv if needed and start the app
#   scripts\preview.ps1 -CopyProfile  first copy your real profile's data into the preview (read-only copy)
#   scripts\preview.ps1 -Reset        delete the preview profile and start empty
#   scripts\preview.ps1 -Console      keep a console open to see errors
#   scripts\preview.ps1 -Demo         use a separate demo profile, created with sample data on first run
#
# The preview profile is %LOCALAPPDATA%\TimeManager-preview. Your real profile
# (%LOCALAPPDATA%\TimeManager) is never opened, so the installed release keeps working
# even when the source version has a newer database schema.
param([switch]$CopyProfile, [switch]$Reset, [switch]$Console, [switch]$Demo)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)

$realProfile = Join-Path $env:LOCALAPPDATA 'TimeManager'
$previewProfile = Join-Path $env:LOCALAPPDATA 'TimeManager-preview'
if ($Demo) { $previewProfile = Join-Path $env:LOCALAPPDATA 'TimeManager-demo' }
$python = '.venv\Scripts\python.exe'

if (!(Test-Path -LiteralPath $python)) {
    Write-Host 'Setting up the Python environment (first run)...'
    & powershell -NoProfile -ExecutionPolicy Bypass -File scripts\setup-windows.ps1
    if ($LASTEXITCODE -ne 0) { throw 'Setup failed; see the messages above.' }
}
& $python -c 'import PySide6, qtawesome, keyring, cryptography, tzdata' 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Installing missing dependencies...'
    & $python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
if (!(Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Warning 'git is not on PATH. The app runs, but the Code page needs git for its actions.'
}

if ($Reset -and (Test-Path -LiteralPath $previewProfile)) {
    if (Test-Path -LiteralPath (Join-Path $previewProfile 'native-desktop.lock')) {
        Write-Warning 'Close the preview app before resetting if it is running.'
    }
    Remove-Item -LiteralPath $previewProfile -Recurse -Force
    Write-Host "Removed the preview profile $previewProfile"
}
if ($Demo -and !(Test-Path -LiteralPath (Join-Path $previewProfile 'timemanager.db'))) {
    & $python scripts\seed-demo.py $previewProfile
    if ($LASTEXITCODE -ne 0) { throw 'The demo profile could not be created.' }
}
if ($CopyProfile) {
    & $python scripts\copy-profile.py $realProfile $previewProfile
    if ($LASTEXITCODE -ne 0) { throw 'The profile was not copied. Use -Reset first to replace an existing preview.' }
}

$commit = (git log -1 --format='%h %s' 2>$null)
$branch = (git branch --show-current 2>$null)
Write-Host "DayFrame source preview: $branch $commit"
Write-Host "Profile: $previewProfile"
if ($Console) {
    & $python app.py --data-dir $previewProfile
} else {
    Start-Process -FilePath '.venv\Scripts\pythonw.exe' -ArgumentList @('app.py', '--data-dir', "`"$previewProfile`"")
}
