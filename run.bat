@echo off
echo ==========================================================
echo    ViralForge AI - Open-Source Video Clipping Tool
echo ==========================================================

where ffmpeg >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] FFmpeg is not installed or not in PATH!
    echo Please install FFmpeg: winget install Gyan.FFmpeg
    pause
    exit /b
)

if not exist venv (
    echo [INFO] Creating Python virtual environment...
    python -m venv venv
)

echo [INFO] Activating virtual environment...
call venv\Scripts\activate

echo [INFO] Installing dependencies...
pip install -r requirements.txt

echo [INFO] Starting ViralForge AI Studio on http://localhost:8000...
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
