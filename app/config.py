import os
from pathlib import Path

# Base Paths
APP_DIR = Path(__file__).resolve().parent  # app/
BASE_DIR = APP_DIR  # Base for bundled resources
OUTPUTS_DIR = BASE_DIR / "outputs"
DOWNLOADS_DIR = OUTPUTS_DIR / "downloads"
CLIPS_DIR = OUTPUTS_DIR / "clips"
UPLOADS_DIR = OUTPUTS_DIR / "uploads"
STATIC_DIR = APP_DIR / "static"
TEMPLATES_DIR = APP_DIR / "templates"
ASSETS_DIR = APP_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"

# Fallback: when installed as a wheel (no source tree), locate the
# bundled static assets wherever pip put them.
# NOTE: in a venv, sys.executable is <venv>/bin/python, so the real
# site-packages is <venv>/lib/pythonX.Y/site-packages — NOT
# <venv>/bin/site-packages (which does not exist). Also: pip installs
# ``data-files`` under ``sys.prefix`` (the venv root), so the assets may
# live at <venv>/maxclipper/static rather than inside site-packages.
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
                base / "maxclipper" / "static",
                base / "maxclipper_static",
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

# Bundled caption fonts: when installed as a wheel the source tree
# (BASE_DIR/assets/fonts) does not exist, so locate the fonts wherever
# pip put them. Only open-license fonts are ever bundled.
if not FONTS_DIR.exists():
    import sys as _sys_f

    _vroot_f = Path(_sys_f.prefix)
    _sp_f = _vroot_f / "lib" / f"python{_sys_f.version_info.major}.{_sys_f.version_info.minor}" / "site-packages"

    def _find_fonts():
        for base in (_sp_f, _vroot_f):
            for rel in (
                "app/assets/fonts",
                "assets/fonts",
                "maxclipper/assets/fonts",
                "maxclipper_fonts",
            ):
                cand = base / rel
                if cand.exists() and any(cand.glob("*.ttf")):
                    return cand
        # Last resort: walk the venv for a folder holding our known fonts.
        for _root, _dirs, _files in _os.walk(_vroot_f):
            if any(f.startswith("Montserrat-") and f.endswith(".ttf") for f in _files):
                return Path(_root)
        return None

    _found_f = _find_fonts()
    if _found_f:
        FONTS_DIR = _found_f

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
