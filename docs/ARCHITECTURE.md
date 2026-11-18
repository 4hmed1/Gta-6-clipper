# ARCHITECTURE.md — GTA 6 Clipper (ClipForge core)

## Entry Points

| Entry | Description |
|-------|-------------|
| `app/main.py` | FastAPI application: serves UI, API routes, background pipeline |
| `clipforge/cli.py` | CLI entry point (`clipforge` / `gta6-clipper`) — starts server, runs doctor |
| `installers/install.sh` | macOS/Linux one-command installer |
| `installers/install.ps1` | Windows one-command installer |

### Start Commands

```bash
# From project root (inside venv or with dependencies installed):
python -m app.main        # Development (auto-reload)
clipforge                  # Installed package (port 3000, opens browser)
clipforge --port 8080      # Custom port
clipforge --no-browser     # Don't auto-open browser
clipforge doctor           # System diagnostics
```

## Data Flow

```
User pastes URL → FastAPI /api/process
  │
  ├─ [INGEST] _fetch_metadata_and_captions() → yt-dlp (skip_download=True)
  │           Returns: title, duration, thumbnail, caption track list
  │
  ├─ [AUDIO]  _download_audio_from_url() → yt-dlp (bestaudio only, 64kbps)
  │           Returns: .wav file path
  │
  ├─ [TRANSCRIBE] transcribe_audio() → faster-whisper → openai-whisper → mock fallback
  │           Returns: word-level timestamps, segments, full text
  │
  ├─ [SELECT] detect_viral_clips() → heuristic / gemini / ollama
  │           Returns: ranked clips (start, end, score, headline, reason)
  │
  ├─ [SECTIONS] _download_sections() → yt-dlp download_ranges (only selected clips)
  │           Returns: per-clip .mp4 file paths
  │
  └─ [RENDER] render_clip() → ffmpeg (vertical 9:16, captions burned)
              Returns: clip .mp4, thumbnail .jpg, download URL
```

## Module Map

| Module | Role |
|--------|------|
| `app/main.py` | FastAPI app, routes, background pipeline orchestrator |
| `app/config.py` | Paths, defaults, environment variables |
| `app/downloader.py` | yt-dlp wrapper (full, audio-only, section downloads) |
| `app/transcriber.py` | Whisper fallback chain → word timestamps |
| `app/viral_detector.py` | Heuristic scoring (hooks, emotion, velocity, length) |
| `app/video_engine.py` | FFmpeg render (vertical, captions, layouts) |
| `app/subtitle_engine.py` | ASS subtitle generation |
| `app/caption_engine.py` | Caption styling, timing repair, safe zones |
| `app/clip_editor.py` | Post-render edit and re-export |
| `app/audio_processor.py` | DSP feature extraction (loudness, spectral, silence) |
| `app/smart_cropper.py` | Face-follow reframing logic |
| `app/youtube_captions.py` | YouTube caption track fetcher |
| `clipforge/cli.py` | CLI commands (start, doctor, update, uninstall) |
| `clipforge/ingest/` | Next-gen ingestion modules |
| `clipforge/resilience/` | Error classifier, fallback ladders, checkpointing |
| `clipforge/security/` | Path traversal prevention, URL validation |
| `clipforge/core/` | Brand config, shared utilities |
| `tests/` | Unit tests, chaos tests, e2e tests |
| `static/` | Frontend (HTML/CSS/JS, served by FastAPI) |
| `config/` | YAML scoring presets, hook rules |

## Known Historical Bugs (Fixed / Verified)

1. **Full-video fallback**: Mock transcription produced 5 even segments; when each exceeded max_duration, detector returned entire video as one clip. **Fix**: Return empty list instead of full-video fallback in `viral_detector.py` line 126.
2. **Exception swallowing**: Pipeline crashed silently with no traceback. **Fix**: Added structured logging with full traceback in `app/main.py`.
3. **Numpy serialization**: `np.float64` in word timestamps broke JSON responses. **Fix**: Convert to plain Python floats.
4. **Static file path resolution**: UI disappeared when run from different working directories. **Fix**: Use `Path(__file__).resolve().parent.parent` for all paths.

## Configuration Files

| File | Purpose |
|------|---------|
| `pyproject.toml` | Package metadata, dependencies, CLI entry |
| `config/scoring/*.yaml` | Per-content-type scoring weights |
| `app/config.py` | Runtime defaults (whisper model, dimensions, subtitles) |

## Directories (Runtime)

| Directory | Contents |
|-----------|----------|
| `outputs/downloads/` | Downloaded audio and video files |
| `outputs/clips/` | Rendered clip MP4s and thumbnails |
| `outputs/uploads/` | User-uploaded video files |
| `logs/` | Pipeline logs |
