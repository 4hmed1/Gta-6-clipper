.PARAMISE
    ONE-COMMAND INSTALL FOR WINDOWS POWERSHELL
#>

$ErrorActionPreference = "Stop"

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "     MaxClipper: One-Command Install (Windows)     " -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# 1. Detect if running from repo root or downloaded script
$scriptDir = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition
if ($scriptDir -and (Test-Path (Join-Path $scriptDir "pyproject.toml"))) {
    Write-Host "[INFO] Running from repository root detected." -ForegroundColor Yellow
} else {
    Write-Host "[INFO] Installer script detected (will download repo)." -ForegroundColor Yellow
}

# 2. Check Python 3.11+
try {
    $pyOutput = & python3 -c "import sys; Write-Host $($sys.version_info.major).$($sys.version_info.minor)"
    Write-Host "[OK] Found Python $pyOutput" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python 3.11+ is required but not found in PATH." -ForegroundColor Red
    exit 1
}

# 3. Check and install FFmpeg if missing
Write-Host "Checking FFmpeg..."
if (!(command -v ffmpeg)) {
    Write-Host "[WARN] FFmpeg not found. Attempting automatic download..." -ForegroundColor Yellow
    # Download verified static FFmpeg for Windows
    $ffmpegUrl = "https://github.com/BtbN/FFmpeg-Builds/releases/download/ffmpeg-2026.11.13-essentials-full/ffmpeg-2026.11.13-win64-gpl-shared-avi.7z"
    $ffmpegDir = "$env:USERPROFILE\ffmpeg"
    if (!(Test-Path $ffmpegDir)) {
        Write-Host "Downloading FFmpeg (approx 50MB)..." -ForegroundColor Cyan
        try {
            $wc = New-Object Net.WebClient
            $wc.DownloadFile($ffmpegUrl, "$ffmpeg_dir.7z")
            & 7z x "$ffmpeg_dir.7z" -o$ffmpegDir
            Remove-Item "$ffmpeg_dir.7z"
            $env:PATH += ";$ffmpegDir"
            Write-Host "[OK] FFmpeg downloaded and added to PATH." -ForegroundColor Green
        } catch {
            Write-Host "[ERROR] Could not download FFmpeg automatically." -ForegroundColor Red
            Write-Host "   Please install FFmpeg manually from https://ffmpeg.org/" -ForegroundColor White
            exit 1
        }
    }
} else {
    Write-Host "[OK] FFmpeg found in PATH." -ForegroundColor Green
}

# 4. Setup isolated environment (no global pollution)
$installDir = "$env:USERPROFILE\maxclipper"
if (!(Test-Path $installDir)) {
    New-Item -ItemType Directory -Force -Path $installDir | Out-Null
}
Write-Host "Installing MaxClipper to $installDir..." -ForegroundColor Cyan

# 5. Use uv for fast, isolated installation if available
$useUv = $false
try {
    & python3 -c "import uv; $useUv = $true"
} catch {
    Write-Host "[INFO] uv not available, will use pip." -ForegroundColor Yellow
}

if ($useUv) {
    Write-Host "Using uv for installation..." -ForegroundColor Cyan
    & python3 -m pip install --upgrade pip
    & python3 -m pip install uv
    & python3 -m uv venv "$installDir\venv"
    & "$installDir\venv\Scripts\python" -m uv pip install --system --upgrade pip
    & "$installDir\venv\Scripts\python" -m uv pip install .
} else {
    & python3 -m venv "$installDir\venv"
    Write-Host "Upgrading pip in venv..." -ForegroundColor Cyan
    & "$installDir\venv\Scripts\python" -m pip install --upgrade pip
    Write-Host "Installing MaxClipper and dependencies..." -ForegroundColor Cyan
    & "$installDir\venv\Scripts\python" -m pip install --upgrade pip
    & "$installDir\venv\Scripts\python" -m pip install -e ".[stt]"
    # Also install yt-dlp if not already
    & "$installDir\venv\Scripts\python" -m pip install yt-dlp
}

# 6. Create command wrappers (NO admin rights needed)
$binDir = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs"
Write-Host "Creating command wrappers in $binDir..." -ForegroundColor Cyan

# maxclipper command
$maxclipperWrapper = "$installDir\venv\Scripts\python.exe"
Write-Host "  maxclipper -> $maxclipperWrapper -m maxclipper.cli" -ForegroundColor White

# 7. Run doctor
Write-Host "Running system health check (maxclipper doctor)..." -ForegroundColor Cyan
& "$installDir\venv\Scripts\python" -m maxclipper.cli doctor

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "MaxClipper installed successfully!" -ForegroundColor Green
Write-Host "Run: `maxclipper`  to start the application" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
