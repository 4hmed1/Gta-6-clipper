import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = BASE_DIR / "outputs"
DOWNLOADS_DIR = OUTPUTS_DIR / "downloads"
CLIPS_DIR = OUTPUTS_DIR / "clips"
UPLOADS_DIR = OUTPUTS_DIR / "uploads"
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

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
