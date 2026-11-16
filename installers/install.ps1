<#
.SYNOPSIS
    ClipForge Windows Installer (PowerShell)
#>

$ErrorActionPreference = "Stop"

Write-Host "==================================================" -ForegroundColor Cyan
Type "       ClipForge Windows Installer (PowerShell)        " -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# 1. Check Python 3.11+
try {
    $pyVersion = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    Write-Host "[✓] Found Python $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Error: Python 3.11+ is required but not found in PATH." -ForegroundColor Red
    exit 1
}

# 2. Setup directory
$installDir = "$HOME\.clipforge"
Write-Host "📦 Installing ClipForge to $installDir..."
if (!(Test-Path $installDir)) {
    New-Item -ItemType Directory -Force -Path $installDir | Out-Null
}

& python -m venv "$installDir\venv"

# 3. Install
Write-Host "⬇️ Installing ClipForge and dependencies..."
& "$installDir\venv\Scripts\python" -m pip install --upgrade pip
& "$installDir\venv\Scripts\python" -m pip install .

# 4. Create batch wrapper
$binDir = "$HOME\AppData\Local\Microsoft\WindowsApps"
$wrapperPath = "$binDir\clipforge.bat"

$wrapperContent = "@echo off`n""$installDir\venv\Scripts\python.exe"" -m clipforge.cli %*"
Set-Content -Path $wrapperPath -Value $wrapperContent

Write-Host "[✓] Created 'clipforge' command shortcut." -ForegroundColor Green

# 5. Doctor
Write-Host "🩺 Running system health check..."
& "$installDir\venv\Scripts\python" -m clipforge.cli doctor

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "🎉 ClipForge installed successfully! Run: clipforge" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Cyan
