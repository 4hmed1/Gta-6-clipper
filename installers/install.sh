#!/usr/bin/env bash
set -euo pipefail

echo "=================================="
echo "   Max Clipper installer"
echo "=================================="

MAXCLIPPER_SRC="${MAXCLIPPER_SRC:-https://github.com/4hmed1/MaxClipper/archive/refs/heads/main.zip}"
BASE="$HOME/.maxclipper"
VENV="$BASE/venv"

main() {
  # Set TMPDIR for all writable data
  export TMPDIR="$HOME/.maxclipper/tmp"

  # Migrate data from old ClipForge / GTA6-Clipper installations
  KEPT=""
  if [ -d "$HOME/.clipforge" ]; then
    OLD_SP="$HOME/.clipforge/venv/site-packages/app"
    if [ -d "$OLD_SP/outputs" ]; then
      cp -r "$OLD_SP/outputs" "$BASE/outputs" 2>/dev/null || true
      KEPT="ClipForge outputs migrated"
    fi
    rm -rf "$HOME/.clipforge"
    # Remove old symlinks
    if [ -L "$HOME/.local/bin/clipforge" ]; then
      rm "$HOME/.local/bin/clipforge"
      KEPT="${KEPT:+$KEPT, }old clipforge symlink removed"
    fi
  fi
  if [ -d "$HOME/.gta6-clipper" ]; then
    OLD_SP="$HOME/.gta6-clipper/venv/site-packages/app"
    if [ -d "$OLD_SP/outputs" ]; then
      cp -r "$OLD_SP/outputs" "$BASE/outputs" 2>/dev/null || true
      KEPT="${KEPT:+$KEPT, }GTA6-Clipper outputs migrated"
    fi
    rm -rf "$HOME/.gta6-clipper"
    # Remove old symlinks
    if [ -L "$HOME/.local/bin/gta6-clipper" ]; then
      rm "$HOME/.local/bin/gta6-clipper"
      KEPT="${KEPT:+$KEPT, }old gta6-clipper symlink removed"
    fi
  fi
  if [ -n "$KEPT" ]; then
    echo "[i] $KEPT"
  fi

  PY=""
  for c in python3.12 python3.13 python3.11 python3.14 python3; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
      PY="$c"
      break
    fi
  done
  if [ -z "$PY" ]; then
    echo "ERROR: Python 3.11 or newer is required."
    echo "Ubuntu/Debian: sudo apt install python3 python3-venv"
    echo "macOS:         brew install python"
    exit 1
  fi
  echo "[ok] Using $($PY --version)"

  if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
    echo "ERROR: FFmpeg is required but was not found."
    echo "Ubuntu/Debian: sudo apt install ffmpeg"
    echo "Fedora:        sudo dnf install ffmpeg"
    echo "Arch:          sudo pacman -S ffmpeg"
    echo "macOS:         brew install ffmpeg"
    echo "Install it, then run this installer again."
    exit 1
  fi
  echo "[ok] FFmpeg found"

  rm -rf "$VENV"
  mkdir -p "$BASE"
  if ! "$PY" -m venv "$VENV"; then
    echo "ERROR: could not create a virtual environment."
    exit 1
  fi

  echo "This takes about 3-8 minutes, please wait..."

  # Install from local folder or remote ZIP
  INSTALL_TARGET="$MAXCLIPPER_SRC"
  if [ -d "$INSTALL_TARGET" ]; then
    echo "[i] Installing from local folder..."
    "$VENV/bin/python" -m pip install --upgrade "$INSTALL_TARGET"
  else
    echo "[i] Installing MaxClipper from remote source..."
    "$VENV/bin/python" -m pip install --upgrade "$INSTALL_TARGET"
  fi

  if [ ! -x "$VENV/bin/maxclipper" ]; then
    echo "ERROR: install finished but the maxclipper program was not created."
    exit 1
  fi

  mkdir -p "$HOME/.local/bin"
  ln -sf "$VENV/bin/maxclipper" "$HOME/.local/bin/maxclipper"

  case ":$PATH:" in
    *":$HOME/.local/bin:"*) ;;
    *)
      for f in "$HOME/.bashrc" "$HOME/.zshrc"; do
        if [ -f "$f" ] && ! grep -q '.local/bin' "$f"; then
          echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$f"
        fi
      done
      ;;
  esac

  echo ""
  "$HOME/.local/bin/maxclipper" doctor || true

  echo ""
  echo "=================================="
  echo " Installed!"
  echo " Open a NEW terminal and type:  maxclipper"
  echo "=================================="
}

# Handle subcommands: update, uninstall
if [ "${1:-}" = "update" ]; then
  echo "[i] Updating MaxClipper from: $MAXCLIPPER_SRC"
  INSTALL_TARGET="${MAXCLIPPER_SRC:-https://github.com/4hmed1/MaxClipper/archive/refs/heads/main.zip}"
  if [ -d "$INSTALL_TARGET" ]; then
    echo "[i] Installing from local folder..."
    "$VENV/bin/python" -m pip install --upgrade "$INSTALL_TARGET"
  else
    echo "[i] Installing MaxClipper from remote source..."
    "$VENV/bin/python" -m pip install --upgrade "$INSTALL_TARGET"
  fi
  echo "[ok] Update completed!"
  exit 0
fi

if [ "${1:-}" = "uninstall" ]; then
  echo "This will remove ~/.maxclipper and the maxclipper symlink."
  read -p "Proceed? [y/N] " -n 1 -r
  echo ""
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf "$HOME/.maxclipper"
    if [ -L "$HOME/.local/bin/maxclipper" ]; then
      rm "$HOME/.local/bin/maxclipper"
    fi
    echo "[ok] Max Clipper uninstalled."
  else
    echo "Uninstall cancelled."
  fi
  exit 0
fi

main "$@"