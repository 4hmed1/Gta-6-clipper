#!/usr/bin/env bash
set -e

echo "=========================================================="
echo "   🎬 Max Clipper - Free Local Vertical Short Maker   "
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

echo "📥 Installing Max Clipper & dependencies..."
pip install -e ".[stt]"

# Use the myenv environment if it exists, otherwise use the local venv
if [ -d "../myenv" ] && [ -f "../myenv/bin/python" ]; then
    echo "Using existing myenv environment..."
    source ../myenv/bin/activate
else
    echo "Using local venv..."
fi

echo "✨ Starting Max Clipper Studio on http://localhost:8760..."
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8760 --reload
