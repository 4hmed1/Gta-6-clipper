#!/usr/bin/env bash
set -e

echo "=================================================="
echo "     Max Clipper Installer (macOS/Linux)        "
echo "=================================================="

# Parse arguments for --no-start flag
SKIP_START=false
for arg in "$@"; do
    case $arg in
        --no-start)
            SKIP_START=true
            shift
            ;;
    esac
done

# 1. Check Python 3.11+
if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ Error: Python 3.11+ is required but not found."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "[✓] Found Python $PYTHON_VERSION"

if [ "$(printf '%s\n' "3.11" "$PYTHON_VERSION" | sort -V | head -1)" != "3.11" ]; then
    echo "❌ Error: Python 3.11+ is required (found $PYTHON_VERSION)."
    exit 1
fi

# 2. Check and install FFmpeg if missing
echo "Checking FFmpeg..."
if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "[WARN] FFmpeg not found. Attempting automatic download..."
    # Detect OS and architecture
    OS=$(uname -s)
    ARCH=$(uname -m)
    
    FFMPEG_DIR="$HOME/ffmpeg"
    mkdir -p "$FFMPEG_DIR"
    
    if [ "$OS" = "Linux" ]; then
        if [ "$ARCH" = "x86_64" ] || [ "$ARCH" = "aarch64" ]; then
            FFMPEG_URL="https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-64bit-static.tar.xz"
        else
            echo "⚠️  Automatic FFmpeg download not supported for ARM Linux."
            echo "   Please install FFmpeg manually: sudo apt install ffmpeg"
            exit 1
        fi
    elif [ "$OS" = "Darwin" ]; then
        FFMPEG_URL="https://evermeet.cx/ffmpeg/releases/ffmpeg-6.0-escapism.zip"
    fi
    
    echo "Downloading FFmpeg (approx 60MB)..."
    curl -fL "$FFMPEG_URL" -o "/tmp/ffmpeg.tar.xz"
    tar -xJf "/tmp/ffmpeg.tar.xz" -C "$FFMPEG_DIR" --strip-components=1 2>/dev/null || \
        tar -xf "/tmp/ffmpeg.tar.xz" -C "$FFMPEG_DIR" --strip-components=1 2>/dev/null
    rm -f "/tmp/ffmpeg.tar.xz"
    export PATH="$FFMPEG_DIR:$PATH"
    echo "[OK] FFmpeg downloaded and added to PATH."
else
    echo "[OK] FFmpeg found in PATH."
fi

# 3. Setup isolated environment (no global pollution)
INSTALL_DIR="$HOME/.maxclipper"
echo "📦 Installing Max Clipper to $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
python3 -m venv "$INSTALL_DIR/venv"

# 4. Upgrade pip and install Max Clipper
echo "⬇️  Downloading and installing Max Clipper & dependencies..."
"$INSTALL_DIR/venv/bin/python" -m pip install --upgrade pip
# Prefer the local checkout (this script is run from the repo root);
# fall back to GitHub only if the local tree is missing.
if [ -f "pyproject.toml" ] && [ -d "app" ]; then
    "$INSTALL_DIR/venv/bin/pip" install . || {
        echo "⚠️  Local install failed, trying GitHub..."
        "$INSTALL_DIR/venv/bin/pip" install git+https://github.com/4hmed1/MaxClipper.git
    }
else
    "$INSTALL_DIR/venv/bin/pip" install git+https://github.com/4hmed1/MaxClipper.git || {
        echo "❌ Could not install MaxClipper. Run this script from the cloned repo root."
        exit 1
    }
fi

# 5. Create symlink / wrapper for maxclipper command
BIN_DIR="/usr/local/bin"
if [ ! -w "$BIN_DIR" ]; then
    BIN_DIR="$HOME/.local/bin"
    mkdir -p "$BIN_DIR"
fi

cat > "$BIN_DIR/maxclipper" << END_SCRIPT
#!/usr/bin/env bash
exec "$INSTALL_DIR/venv/bin/python" -m maxclipper.cli "$@"
END_SCRIPT
chmod +x "$BIN_DIR/maxclipper"

# Also create maxclipper alias
cat > "$BIN_DIR/maxclipper" << END_SCRIPT
#!/usr/bin/env bash
exec "$INSTALL_DIR/venv/bin/python" -m maxclipper.cli "$@"
END_SCRIPT
chmod +x "$BIN_DIR/maxclipper"

# 6. Run doctor
echo "🩺 Running system health check..."
"$INSTALL_DIR/venv/bin/python" -m maxclipper.cli doctor

# 7. Auto-start server unless --no-start is provided
if [ "$SKIP_START" = true ]; then
    echo "✅ Max Clipper installed successfully!"
    echo "   To start the server later, run: maxclipper"
else
    echo "🔄 Starting Max Clipper server..."
    echo "🌐 Max Clipper is starting on http://localhost:8760"
    echo "   To re-open the browser later, run: maxclipper"
    echo "   To stop the server, press Ctrl+C"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🎉 Max Clipper is ready! Open your browser to http://localhost:8760"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Start the server in background
    nohup "$INSTALL_DIR/venv/bin/python" -m uvicorn app.main:app --host 0.0.0.0 --port 8760 >> "$(echo $HOME)/maxclipper_install.log" 2>&1 &
    SERVER_PID=$!
    echo "Server started with PID: $SERVER_PID"
    
    # Wait a moment for server to start
    sleep 3
    
    # Check if server is running
    if curl -s -m 3 http://127.0.0.1:8760/api/status >/dev/null; then
        echo "✅ Server is running! You can access it at: http://localhost:8760"
    else
        echo "⚠️  Server may not be starting properly. Check the log file."
    fi
fi

echo "=================================================="
echo "🎉 Max Clipper installed successfully!"
if [ "$SKIP_START" = true ]; then
    echo "   To start the server later, run: maxclipper"
else
    echo "   Server is running at: http://localhost:8760"
fi
echo "=================================================="
END_SCRIPT
chmod +x "$BIN_DIR/maxclipper"

# Move the script to installers/install.sh
mv tmp_install.sh installers/install.sh
chmod +x installers/install.sh
echo "install.sh updated successfully"
