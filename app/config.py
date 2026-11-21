import os
from pathlib import Path

# Base Paths (relative to this config.py inside app/)
BASE_DIR = Path(__file__).resolve().parent  # points to app/
OUTPUTS_DIR = BASE_DIR / "outputs"
DOWNLOADS_DIR = OUTPUTS_DIR / "downloads"
CLIPS_DIR = OUTPUTS_DIR / "clips"
UPLOADS_DIR = OUTPUTS_DIR / "uploads"
STATIC_DIR = BASE_DIR / "static"  # app/static/
TEMPLATES_DIR = BASE_DIR / "templates"  # app/templates/

# Fallback: when installed as a wheel (no source tree), locate the
# bundled static assets wherever pip put them.
# NOTE: in a venv, sys.executable is <venv>/bin/python, so the real
# site-packages is <venv>/lib/pythonX.Y/site-packages — NOT
# <venv>/bin/site-packages (which does not exist). Also: pip installs
# ``data-files`` under ``sys.prefix`` (the venv root), so the assets may
# live at <venv>/clipforge/static rather than inside site-packages.
if not STATIC_DIR.exists():
    import os as _os
    import sys as _sys

    # sys.prefix is venv-aware: in a venv it is the venv root, and the
    # venv python is a symlink to the system interpreter. Resolving
    # sys.executable therefore points at /usr/bin/python3.14 and loses
    # the venv entirely — so we use sys.prefix instead.
    _venv_root = Path(_sys.prefix)
    _sp = _venv_root / "lib" / f"python{_sys.version_info.major}.{_sys.version_info.minor}" / "site-packages"

    def _find_static():
        for base in (_sp, _venv_root):
            for cand in (
                base / "static",
                base / "clipforge" / "static",
                base / "clipforge_static",
            ):
                if cand.exists():
                    return cand
        # Walk the venv root as a last resort (data-files layout varies).
        # Require all three bundled assets so we never match an unrelated
        # "static" folder that happens to contain an index.html.
        for _root, _dirs, _files in _os.walk(_venv_root):
            if (
                "index.html" in _files
                and "app.js" in _files
                and "style.css" in _files
                and _root.endswith("static")
            ):
                return Path(_root)
        return None

    _found = _find_static()
    if _found:
        STATIC_DIR = _found
    else:
        # Final fallback: copy from the source tree if available
        _src = Path(__file__).resolve().parent.parent / "static"
        if _src.exists():
            STATIC_DIR = _src

# Ensure all working directories exist
for directory in [OUTPUTS_DIR, DOWNLOADS_DIR, CLIPS_DIR, UPLOADS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Configuration Defaults
DEFAULT_WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")  # tiny, base, small, medium, large-v3
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

# Video Settings
DEFAULT_ASPECT_RATIO = "9:16"  # "9:16", "1:1", "16:9"
DEFAULT_TARGET_WIDTH = 1080
DEFAULT_TARGET_HEIGHT = 1920
DEFAULT_SUBTITLE_STYLE = "vibrant_gold"  # "vibrant_gold", "neon_green", "cyber_cyan", "minimal"

# Clip Rules
MIN_CLIP_DURATION = int(os.getenv("MIN_CLIP_DURATION", "20"))  # seconds
MAX_CLIP_DURATION = int(os.getenv("MAX_CLIP_DURATION", "60"))  # seconds
MAX_CLIPS_TO_GENERATE = int(os.getenv("MAX_CLIPS_TO_GENERATE", "5"))
