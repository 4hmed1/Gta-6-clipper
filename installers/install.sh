#!/usr/bin/env bash
set -euo pipefail

echo "=================================================="
echo "     ClipForge: One-Command Install (macOS/Linux) "
echo "=================================================="

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
    # Detect architecture and OS
    OS=$(uname -s)
    ARCH=$(uname -m)
    
    FFMPEG_DIR="$HOME/ffmpeg"
    mkdir -p "$FFMPEG_DIR"
    
    if [ "$OS" = "Linux" ]; then
        if [ "$ARCH" = "x86_64" ] || [ "$ARCH" = "aarch64" ]; then
            FFMPEG_URL="https://johnvansickle.com/ffmpeg/releasesffmpeg-release-64-bit-static.tar.xz"
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
    mkdir -p "$FFMPEG_DIR"
    tar -xJf "/tmp/ffmpeg.tar.xz" -C "$FFMPEG_DIR" --strip-components=1 2>/dev/null || \
        tar -xf "/tmp/ffmpeg.tar.xz" -C "$FFMPEG_DIR" --strip-components=1 2>/dev/null
    rm -f "/tmp/ffmpeg.tar.xz"
    export PATH="$FFMPEG_DIR:$PATH"
    echo "[OK] FFmpeg downloaded and added to PATH."
else
    echo "[OK] FFmpeg found in PATH."
fi

# 3. Setup isolated environment (no global pollution)
INSTALL_DIR="$HOME/.clipforge"
mkdir -p "$INSTALL_DIR"

echo "Creating isolated environment at $INSTALL_DIR..."
python3 -m venv "$INSTALL_DIR/venv"

echo "Upgrading pip in venv..."
"$INSTALL_DIR/venv/bin/python" -m pip install --upgrade pip > /dev/null 2>&1

# 4. Use uv for fast installation if available, otherwise pip
echo "Checking for uv..."
if "$INSTALL_DIR/venv/bin/python" -c "import uv" 2>/dev/null; then
    echo "Using uv for installation..."
    "$INSTALL_DIR/venv/bin/python" -m pip install uv
    "$INSTALL_DIR/venv/bin/python" -m uv pip install --system --upgrade pip
    "$INSTALL_DIR/venv/bin/python" -m uv pip install .
else
    echo "Using pip for installation..."
    "$INSTALL_DIR/venv/bin/python" -m pip install .
    # Also install yt-dlp if not already in venv
    "$INSTALL_DIR/venv/bin/python" -m pip install yt-dlp
fi

# 5. Create command wrappers (NO admin rights needed)
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"

echo "Creating command wrappers..."
cat << EOF > "$BIN_DIR/clipforge"
#!/usr/bin/env sh
exec "$INSTALL_DIR/venv/bin/python" -m clipforge.cli "$@"
EOF
chmod +x "$BIN_DIR/clipforge"

cat << EOF > "$BIN_DIR/clipforge-editor"
#!/usr/bin/env sh
exec "$INSTALL_DIR/venv/bin/python" -m clipforge.cli "$@"
EOF
chmod +x "$BIN_DIR/clipforge-editor"

# 6. Run doctor
echo "Running system health check (clipforge doctor)..."
"$INSTALL_DIR/venv/bin/python" -m clipforge.cli doctor

echo "=================================================="
echo "🎉 ClipForge installed successfully!"
echo "   Run: clipforge  to start the application"
echo "=================================================="