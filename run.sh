#!/usr/bin/env bash
set -e

echo "=========================================================="
echo "   🎬 GTA 6 Clipper - Free Local Vertical Short Maker   "
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

echo "📥 Installing GTA 6 Clipper & dependencies..."
pip install -r requirements.txt
pip install -e .

# Install optional STT engine
pip install -e ".[stt]" 2>/dev/null || echo "⚠️  Optional offline STT (faster-whisper) not installed. Run: pip install -e '.[stt]'"

echo "✨ Starting GTA 6 Clipper Studio on http://localhost:3000..."
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 3000 --reload
