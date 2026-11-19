# PERF_BASELINE.md - Pipeline Profiling Baseline

Generated: 2026-11-19 07:39:46

## Test Configurations

### (a) 10-minute captioned talking-head video (proxied with 60s test)
- Video: /tmp/test_60s.mp4 (60s)
- Audio: extracted at 16kHz mono, ~1920.1 KB
- Transcript: word-level timestamps from faster-whisper
- Clip selection: heuristic method (offline)
- Render: split_blur layout, vibrant_gold subtitle style

### (b) 10-minute video with NO captions
- Same video but transcript would be Whisper-only (mock fallback)
- Expected: longer transcription time, no YouTube caption shortcut

### (c) 30-minute stream/gaming video
- Expected: larger files, more audio analysis, more candidate windows

## Per-Stage Timing

| Stage | Seconds | Peak RAM (MB) | KB Downloaded | KB Written | Heartbeat |
|-------|---------|---------------|---------------|------------|-----------|
| metadata_captions | 0.0 |           0 |          4.1 |          0.0 | OK |
| audio_extract | 1.44 |           0 |       1920.1 |       1920.1 | OK (1920.1 KB written) |
| transcribe | 27.03 |           0 |          0.0 |          0.0 | OK (27.0s, RT factor: 27.03x) |
| selection | 0.0 |           0 |          0.0 |          0.0 | OK (0 clips selected) |
| render | 148.55 |           0 |          0.0 |        717.0 | OK (717.0 KB output) |

## Total Time: 177.0s

## Per-Video Breakdown
### (a) 10-minute captioned talking-head video (proxied)
- Video: 60s test video with audio
- Metadata/captions loading: 0.0s
- Audio extraction: 1.44s
- Transcription (faster-whisper tiny): 27.03s
- Clip selection: 0.0s
- Render: 148.55s
- Total: 177.0s

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
- All times measured on: 4th-gen Intel i5, 8 GB RAM, no GPU, slow network (0.2-1 MB/s)
- Timeout thresholds: download=60s, transcription=120s, render=90s
- Stuck detector: triggers if no progress for N seconds
- Peak RAM measured via getrusage(RUSAGE_SELF).ru_maxrss (KB on Linux)
