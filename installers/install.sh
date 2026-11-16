#!/usr/bin/env sh
set -e

echo "=================================================="
echo "         ClipForge Installer (macOS/Linux)        "
echo "=================================================="

# 1. Check Python 3.11+
if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ Error: Python 3.11+ is required but not found."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "[✓] Found Python $PYTHON_VERSION"

# 2. Setup virtual environment
INSTALL_DIR="$HOME/.clipforge"
echo "📦 Installing ClipForge to $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
python3 -m venv "$INSTALL_DIR/venv"

# 3. Upgrade pip and install ClipForge
echo "⬇️ Downloading and installing ClipForge & dependencies..."
"$INSTALL_DIR/venv/bin/python" -m pip install --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install git+https://github.com/max/clipforge.git || {
    # Fallback to local install if offline/development
    "$INSTALL_DIR/venv/bin/pip" install .
}

# 4. Create symlink / wrapper for clipforge command
BIN_DIR="/usr/local/bin"
if [ ! -w "$BIN_DIR" ]; then
    BIN_DIR="$HOME/.local/bin"
    mkdir -p "$BIN_DIR"
fi

cat << EOF > "$BIN_DIR/clipforge"
#!/usr/bin/env sh
exec "$INSTALL_DIR/venv/bin/python" -m clipforge.cli "\$@"
EOF

chmod +x "$BIN_DIR/clipforge"
echo "[✓] Created 'clipforge' command at $BIN_DIR/clipforge"

# 5. Run clipforge doctor
echo "🩺 Running system health check..."
"$BIN_DIR/clipforge" doctor

echo "=================================================="
echo "🎉 ClipForge installed successfully!"
echo "Run: clipforge"
echo "=================================================="
