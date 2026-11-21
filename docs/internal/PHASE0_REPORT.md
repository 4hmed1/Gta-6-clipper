# PHASE 0 — UNDERSTAND AND STABILIZE

## Reproduction Results (2026-11-18)

### Test 1: Rick Astley (213s, 4K Remaster) — task `b27359c7`
| Stage | Duration | Notes |
|-------|----------|-------|
| metadata | 5.67s | ✅ Title, duration, captions fetched |
| download_full_video | ~7.5 min | ❌ Downloaded 11.28 MiB full video |
| transcribe | ~621.67s | ✅ 413 real words via faster-whisper |
| selection | 0.04s | ✅ 5 candidates found |
| download_sections | 0s | ❌ No section download — reused full video |
| render | ongoing | ❌ Rendering from full video, not sections |

### Test 2: 3 Minutes Of INSPIRATION (187s) — task `6a62d278`
Same pattern: full video downloaded (~9.56 MiB), then transcribed, then rendered from full video.

### Root Cause Confirmed
1. **`app/main.py` line 152-163**: Downloads the FULL video via `download_youtube_video()` before any analysis
2. **`app/main.py` line 247-251**: Skips section download entirely — reuses the full video for all clips
3. **`app/main.py` line 169-185**: Extracts audio from the full video via ffmpeg (slow, wasteful)
4. **`app/main.py` line 205-213**: Transcribes from the extracted audio (works, but slow)

### What Works
- Metadata fetch (yt-dlp skip_download)
- Transcription (faster-whisper, 413 real words)
- Clip selection (heuristic scoring)
- Rendering (FFmpeg, vertical 9:16, captions burned)
- UI serves correctly from any working directory

### What's Broken
- Full video download instead of audio-first + section-only
- No parallel fragment download (`-N 4`)
- No `--download-sections` for chosen clips
- No hardware encoder detection (uses x264 veryfast)
- No structured logging with stage timing
- No exception swallowing removed

### Next Steps
1. Fix download strategy (audio-first, section-only)
2. Add structured logging with stage timing
3. Add hardware encoder detection
4. Test with real 3-5 minute video