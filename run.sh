#!/usr/bin/env bash
set -e

echo "=========================================================="
echo "   🚀 ViralForge AI - Open-Source Video Clipping Tool   "
echo "=========================================================="

# Check if ffmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo "❌ FFmpeg is not installed! Please install ffmpeg first."
    echo "   Ubuntu/Debian: sudo apt update && sudo apt install -y ffmpeg"
    echo "   macOS: brew install ffmpeg"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv venv
fi

echo "🔄 Activating virtual environment..."
source venv/bin/activate

echo "📥 Installing required Python dependencies..."
pip install -r requirements.txt

echo "✨ Starting ViralForge AI Studio on http://localhost:3000..."
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 3000 --reload
