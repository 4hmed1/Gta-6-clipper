#!/usr/bin/env sh
set -e

echo "=================================================="
echo "     GTA 6 Clipper Installer (macOS/Linux)        "
echo "=================================================="

# 1. Check Python 3.11+
if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ Error: Python 3.11+ is required but not found."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "[✓] Found Python $PYTHON_VERSION"

# 2. Setup virtual environment
INSTALL_DIR="$HOME/.gta6-clipper"
echo "📦 Installing GTA 6 Clipper to $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
python3 -m venv "$INSTALL_DIR/venv"

# 3. Upgrade pip and install GTA 6 Clipper
echo "⬇️  Downloading and installing GTA 6 Clipper & dependencies..."
"$INSTALL_DIR/venv/bin/python" -m pip install --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install git+https://github.com/max/viralforge-ai.git || {
    # Fallback to local install if offline/development
    "$INSTALL_DIR/venv/bin/pip" install .
}

# 4. Create symlink / wrapper for gta6-clipper command
BIN_DIR="/usr/local/bin"
if [ ! -w "$BIN_DIR" ]; then
    BIN_DIR="$HOME/.local/bin"
    mkdir -p "$BIN_DIR"
fi

cat << EOF > "$BIN_DIR/gta6-clipper"
#!/usr/bin/env sh
exec "$INSTALL_DIR/venv/bin/python" -m clipforge.cli "\$@"
EOF
chmod +x "$BIN_DIR/gta6-clipper"

# Also create clipforge alias
cat << EOF > "$BIN_DIR/clipforge"
#!/usr/bin/env sh
exec "$INSTALL_DIR/venv/bin/python" -m clipforge.cli "\$@"
EOF
chmod +x "$BIN_DIR/clipforge"

# 5. Doctor
echo "🩺 Running system health check..."
"$INSTALL_DIR/venv/bin/python" -m clipforge.cli doctor

echo "=================================================="
echo "🎉 GTA 6 Clipper installed successfully!"
echo "   Run: gta6-clipper  (or: clipforge)"
echo "=================================================="
