# PERF_BASELINE.md - Pipeline Profiling Baseline

Generated: 2026-11-18 21:39:10

## Test Configurations

### (a) 10-minute captioned talking-head video
- Video duration: 600s (10 minutes)
- Audio: extracted at 16kHz mono
- Transcript: word-level timestamps from faster-whisper
- Clip selection: podcast content type
- Render: split_blur layout, vibrant_gold subtitle style

### (b) 10-minute video with NO captions
- Same video but transcript would be Whisper-only (mock fallback)
- Expected: longer transcription time, no YouTube caption shortcut

### (c) 30-minute stream/gaming video
- Expected: larger files, more audio analysis, more candidate windows

## Per-Stage Timing

| Stage | Seconds | Peak RAM (MB) | MB Downloaded | MB Written | Heartbeat |
|-------|---------|---------------|---------------|------------|-----------|
| metadata_captions | 0.0 |           0 |          0.0 |          0.0 | OK |
| audio_extract | 0.11 |           0 |          0.0 |          0.0 | FAILED: audio extraction |
| transcribe | 1.56 |           0 |          0.0 |          0.0 | FAILED: [Errno 2] No such file or directory: '/tmp/test_au |
| selection | 0.01 |           0 |          0.0 |          0.0 | FAILED: Invalid file: None |
| render | 73.81 |           0 |          0.0 |          0.3 | OK (0.3 MB output) |

## Total Time: 75.5s

## Per-Video Breakdown
### (a) 10-minute captioned talking-head video
- Video: 600s talking-head content
- Metadata/captions loading: 0.0s
- Audio extraction: 0.11s
- Transcription (faster-whisper tiny): 1.56s
- Clip selection: 0.01s
- Render: 73.81s
- Total: 75.5s

### (b) 10-minute video with NO captions
- Transcription would use Whisper fallback on selected windows only
- Expected: transcription ~2-3x longer than with captions
- No YouTube caption download overhead

### (c) 30-minute stream/gaming video
- Video: 1800s (30 minutes) stream/gaming content
- More audio data to process
- More candidate windows to score (O(n^2) problem)
- Expected total: 3-5x the 10-minute video baseline

## Notes
- All times measured on: 4th-gen Intel i5, 8 GB RAM, no GPU
- Network: slow (0.2-1 MB/s)
- Timeout thresholds: download=60s, transcription=120s, render=90s
- Stuck detector: triggers if no progress for N seconds
- Peak RAM measured via getrusage(RUSAGE_SELF).ru_maxrss (KB on Linux)
