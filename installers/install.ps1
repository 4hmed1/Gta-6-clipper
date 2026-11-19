<#
.SYNOPSIS
    GTA 6 Clipper Windows Installer (PowerShell)
#>

$ErrorActionPreference = "Stop"

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "     GTA 6 Clipper Windows Installer (PowerShell) " -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# 1. Check Python 3.11+
try {
    $pyVersion = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    Write-Host "[OK] Found Python $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python 3.11+ is required but not found in PATH." -ForegroundColor Red
    exit 1
}

# 2. Setup directory
$installDir = "$HOME\.gta6-clipper"
Write-Host "Installing GTA 6 Clipper to $installDir..."
if (!(Test-Path $installDir)) {
    New-Item -ItemType Directory -Force -Path $installDir | Out-Null
}

& python -m venv "$installDir\venv"

# 3. Install
Write-Host "Installing GTA 6 Clipper and dependencies..."
& "$installDir\venv\Scripts\python" -m pip install --upgrade pip
& "$installDir\venv\Scripts\python" -m pip install .

# 4. Create batch wrapper (gta6-clipper + clipforge alias)
$binDir = "$HOME\AppData\Local\Microsoft\WindowsApps"
$wrapperPath = "$binDir\gta6-clipper.bat"

$wrapperContent = "@echo off`r`n`"$installDir\venv\Scripts\python.exe`" -m clipforge.cli %*"
Set-Content -Path $wrapperPath -Value $wrapperContent

# clipforge alias
$aliasPath = "$binDir\clipforge.bat"
Set-Content -Path $aliasPath -Value $wrapperContent

Write-Host "[OK] Created 'gta6-clipper' and 'clipforge' command shortcuts." -ForegroundColor Green

# 5. Doctor
Write-Host "Running system health check..."
& "$installDir\venv\Scripts\python" -m clipforge.cli doctor

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "GTA 6 Clipper installed successfully! Run: gta6-clipper" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Cyan
