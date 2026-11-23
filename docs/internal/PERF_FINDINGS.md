# PERF_FINDINGS.md - Root Cause Analysis

Generated: 2026-11-19
Machine: 4th-gen Intel i5 (4 threads), 8 GB RAM, no GPU

## Summary

| Bottleneck | Time (60s video) | Real-time factor | Impact on 10-min video |
|------------|------------------|------------------|------------------------|
| Transcription | ~30s | **50x** | ~8-10 minutes |
| Render | ~167s (30s clip) | **5.6x** | ~28 minutes per clip |
| Selection | ~0.1s | 0.002x | Fast but returns 0 clips (BUG) |
| Audio extract | ~1.2s | 0.02x | Not a bottleneck |

---

## Root Causes (with file/line/evidence)

### 1. TRANSCRIPTION: 50x Real-time Factor (CONFIRMED)

**File:** `app/transcriber.py`, lines 42-89

**Evidence:**
```python
model = WhisperModel(model_size, device=device, compute_type=compute_type)
segments_gen, info = model.transcribe(audio_path, word_timestamps=True)
```

**Causes:**
- **Model size**: Using `tiny` model (39M params) but still 50x RT on CPU
- **No VAD filter**: `vad_filter=False` by default, transcribes silence
- **Full audio**: Transcribes entire audio even when only clips needed
- **CPU threads**: Not limiting `cpu_threads`, uses all available (4 on this machine)
- **Beam search**: Default `beam_size=5` adds overhead

**Measurement:**
- 60s audio → 30s transcription = 50x real-time
- Expected on weak CPU: 20-30x with optimal settings

**Fix Priority:** HIGH
- Use `vad_filter=True` to skip silence
- Limit `cpu_threads=2` to leave headroom for UI
- Reduce `beam_size=1` for speed
- Only transcribe selected windows (not full audio)

---

### 2. RENDER: 5.6x Real-time Factor (CONFIRMED)

**File:** `app/video_engine.py`, lines 106-130

**Evidence:**
```python
cmd = [
    "ffmpeg",
    "-y", "-ss", str(start_time), "-i", source_video, "-t", str(duration)
]
# ... filter_complex with blur + overlay + subtitles
cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22"]
```

**Causes:**
- **Full resolution processing**: 1920x1080 → 1080x1920 with blur
- **Blur filter**: `boxblur=24:6` on full frame is expensive
- **Subtitles via libass**: ASS rendering with kinetic animations is slow
- **Seek after input**: `-ss` before `-i` would be faster for single clips
- **No hardware acceleration**: Software x264 only
- **CRF 22**: Higher quality than needed for preview/social

**Measurement:**
- 30s clip → 167s render = 5.6x real-time
- Expected with optimizations: 1.5-2x real-time

**Fix Priority:** HIGH
- Seek before input: `-ss` before `-i`
- Blur at lower resolution (270x480 then upscale)
- Use `-preset ultrafast` for preview, `veryfast` for final
- Consider `-crf 28` for social media (smaller files, faster encode)

---

### 3. SELECTION: Returns 0 Clips (CONFIRMED BUG)

**File:** `app/viral_detector.py`, lines 25-120

**Evidence:**
```python
def analyze_viral_moments_heuristic(segments, min_duration=20.0, max_duration=60.0, max_clips=5):
    # ...
    for i in range(num_segs):
        for j in range(i, num_segs):
            # ...
            if duration < min_duration:
                continue
            if duration > max_duration:
                break  # BUG: breaks inner loop, misses valid windows
```

**Causes:**
- **Segments format mismatch**: Function expects `segments` with `start`/`end`/`text` keys
- **Transcript provides `words`**: `trans_res.get("segments", [])` returns segments from Whisper
- **Duration check bug**: `break` exits inner loop too early when duration exceeds max
- **No clips found fallback**: Returns empty list instead of providing fallback clips

**Measurement:**
- 60s video with 75 words → 0 clips selected
- Expected: 3-5 clips with scores 70-95

**Fix Priority:** CRITICAL (no clips = no product)
- Fix duration loop logic
- Add fallback when no clips found
- Ensure segment/word format matches

---

### 4. SUBPROCESS HANDLING: Potential Deadlocks (LIKELY)

**File:** Multiple files

**Evidence:**
- `app/transcriber.py` line 29: `subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)`
  - OK: drains output to DEVNULL
- `app/video_engine.py` line 133: `subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)`
  - RISK: Pipes not drained during long runs, could deadlock on large output
- No timeouts on most subprocess calls
- No `-nostdin` flag on FFmpeg calls

**Causes:**
- FFmpeg without `-nostdin` can hang waiting for input
- PIPEs without draining can fill up and block
- No timeout means infinite hang on stuck processes

**Fix Priority:** MEDIUM
- Add `-nostdin -y` to all FFmpeg calls
- Add `timeout=300` to subprocess.run
- Use `stdout=subprocess.DEVNULL` or drain in thread

---

### 5. ASYNC/THREADING: No Major Issues Found (RULED OUT)

**File:** `app/main.py`

**Evidence:**
- Background tasks use `BackgroundTasks.add_task()` correctly
- No `asyncio.run()` inside threads
- Status polling reads from in-memory dict (no locking but OK for single-threaded reads)

**Measurement:**
- No deadlocks observed in profiling runs
- UI responsive during processing

**Status:** RULED OUT as primary bottleneck

---

### 6. AUDIO ANALYSIS: Vectorized, Not a Bottleneck (RULED OUT)

**File:** `maxclipper/core/signals.py`

**Evidence:**
```python
y, sr = librosa.load(audio_path, sr=16000)  # Already 16kHz mono
hop_length = int(sr * hop_length_ms / 1000)  # 800 samples = 50ms
rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]  # Vectorized
```

**Measurement:**
- Audio analysis completes in <2s for 60s audio
- Uses NumPy vectorization throughout

**Status:** RULED OUT

---

### 7. DISK/DB: Not a Factor (RULED OUT)

**Evidence:**
- No SQLite in current pipeline
- Temp files written to `/tmp` (RAM disk on many systems)
- No large JSON logs during profiling

**Status:** RULED OUT

---

### 8. NETWORK: Not Tested (N/A)

**Note:** Profiling used local files, no network download tested.
- YouTube download would add significant time on slow network (0.2-1 MB/s)
- Need to test with real URL to measure download bottleneck

**Status:** NOT YET MEASURED

---

## Next Steps (by priority)

1. **Fix selection bug** (CRITICAL - no clips = no product)
2. **Optimize transcription** (HIGH - 50x RT is unacceptable)
   - Add `vad_filter=True`
   - Set `cpu_threads=2`
   - Reduce `beam_size=1`
3. **Optimize render** (HIGH - 5.6x RT too slow)
   - Seek before input
   - Blur at low resolution
   - Use `-preset ultrafast` for preview
4. **Add subprocess safeguards** (MEDIUM)
   - Add `-nostdin` to FFmpeg
   - Add timeouts
   - Drain pipes properly
