@echo off
echo ==========================================================
echo    Max Clipper - Free Local Vertical Short Maker
echo ==========================================================

REM Check if ffmpeg is installed
where ffmpeg >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ FFmpeg is not installed! Please install ffmpeg first.
    echo    Windows: winget install Gyan.FFmpeg
    exit /b 1
)

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo 📦 Creating Python virtual environment...
    python -m venv venv
)

echo 🔄 Activating virtual environment...
call venv\Scripts\activate

echo 📥 Installing Max Clipper ^& dependencies...
pip install -r requirements.txt
pip install -e .

REM Install optional STT engine
pip install -e ".[stt]" 2>nul || echo ⚠️  Optional offline STT (faster-whisper) not installed. Run: pip install -e ".[stt]"

echo ✨ Starting Max Clipper Studio on http://localhost:3000...
python -m uvicorn app.main:app --host 0.0.0.0 --port 3000 --reload
