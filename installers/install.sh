#!/usr/bin/env bash
set -euo pipefail

REPO_ZIP="https://github.com/4hmed1/clipforge/archive/refs/heads/main.zip"
BASE="$HOME/.clipforge"
VENV="$BASE/venv"

main() {
  echo "=================================="
  echo "   ClipForge installer"
  echo "=================================="

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
    echo "Ubuntu/Debian: sudo apt install python3-venv"
    exit 1
  fi

  echo "Installing ClipForge (2-5 minutes, please wait)..."
  "$VENV/bin/python" -m pip install --quiet --upgrade pip
  "$VENV/bin/python" -m pip install --quiet --upgrade "clipforge[stt] @ $REPO_ZIP"

  SP=$("$VENV/bin/python" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
  for d in static config templates assets; do
    if [ -d "$SP/app/$d" ] && [ ! -d "$SP/$d" ]; then
      cp -r "$SP/app/$d" "$SP/$d"
    fi
  done

  if [ ! -x "$VENV/bin/clipforge" ]; then
    echo "ERROR: install finished but the clipforge program was not created."
    exit 1
  fi

  mkdir -p "$HOME/.local/bin"
  ln -sf "$VENV/bin/clipforge" "$HOME/.local/bin/clipforge"

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
  "$HOME/.local/bin/clipforge" doctor || true

  echo ""
  echo "=================================="
  echo " Installed!"
  echo " Open a NEW terminal and type:  clipforge"
  echo "=================================="
}

main "$@"