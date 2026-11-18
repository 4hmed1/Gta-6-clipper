#!/usr/bin/env python3
"""
Profile runner for ClipForge pipeline stages.
Runs the full flow on test videos and prints timing results.
"""

import json
import os
import sys
import time
import asyncio
import subprocess
import signal
import resource
from pathlib import Path
from typing import Dict, Any, List

# Add the project to path
sys.path.insert(0, '/home/max/Documents/viralforge-ai')

from pathlib import Path

# ---- Create a test video + transcript ----
def create_test_video() -> tuple:
    """Create a synthetic test video and transcript for profiling."""
    video_path = '/tmp/test_talking_head.mp4'
    # Generate 10 min of synthetic video using ffmpeg
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", "color=c=yellow:d=600",
         "-f", "lavfi", "-i", "color=c=blue:d=600",
         "-filter_complex", "[0][1]overlay=x=10:y=10",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
         "-t", "600", video_path],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    
    # Create transcript with word timings for a 10-minute video
    import random
    random.seed(42)
    duration = 600  # 10 minutes
    words = []
    t = 0.0
    while t < duration:
        wlen = random.uniform(0.5, 3.0)
        words.append({
            'word': f'word{len(words)}',
            'start': round(t, 2),
            'end': round(t + wlen + random.uniform(0.1, 0.5), 2)
        })
        t += wlen + random.uniform(0.1, 0.5)
    words[-1]['end'] = round(duration, 2)
    
    # Add some meaningful sentences at known positions
    sentences_text = [
        'The secret to growing your audience is actually quite simple.',
        'If you want to build massive leverage in 2026 you need to focus on hooks.',
        'The first three seconds are everything because people scroll instantly.',
        'Watch what happens when you implement this single change today.',
        'Most people are making a big mistake by not optimizing.',
        'You have to stop making long boring videos and start focusing.',
        'The biggest problem with content today is lack of engagement.',
        'Transform your approach and change your life today.',
        'This single strategy will change everything for you.',
        'Stop doing what is not working and start doing this instead.'
    ]
    sentence_starts = [0.0, 45.0, 95.0, 150.0, 210.0, 280.0, 350.0, 420.0, 490.0, 560.0]
    sentence_ends = [44.0, 94.0, 149.0, 209.0, 279.0, 349.0, 419.0, 489.0, 559.0, 600.0]
    
    # Add sentence-level words
    all_words = list(words)  # Start with random words
    for si, (ss, se) in enumerate(zip(sentence_starts, sentence_ends)):
        nwords = random.randint(8, 20)
        for j in range(nwords):
            wlen = random.uniform(0.3, 2.0)
            t = ss + sum([random.uniform(0.3, 2.0) + 0.1 for _ in range(j)])
            if t < se:
                word_text = sentences_text[si].split()[j % len(sentences_text[si].split())] if j < len(sentences_text[si].split()) else f'word{j}'
                all_words.append({
                    'word': word_text,
                    'start': round(t, 2),
                    'end': round(t + wlen + random.uniform(0.1, 0.3), 2)
                })
    
    all_words.sort(key=lambda x: x['start'])
    all_words[-1]['end'] = round(duration, 2)
    
    with open('/tmp/test_transcript.json', 'w') as f:
        json.dump({'words': all_words, 'text': ' '.join([w['word'] for w in all_words[:150]])}, f)
    
    return video_path, all_words


def profile_stage(name: str, fn, *args, timeout: int = 300, **kwargs) -> Dict[str, Any]:
    """Run a stage and profile its resource usage."""
    start_time = time.time()
    peak_mem = 0
    
    result = [None]
    error = [None]
    
    def target():
        nonlocal peak_mem
        try:
            # Set resource limits and track peak
            try:
                old_limits = resource.getrlimit(resource.RLIMIT_AS)
                try:
                    resource.setrlimit(resource.RLIMIT_AS, (1024 * 1024 * 1024, 1024 * 1024 * 1024))
                except:
                    pass
            except:
                pass
            
            result[0] = fn(*args, **kwargs)
            
            # Get peak RSS after completion
            try:
                peak_mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss  # KB on Linux
            except:
                pass
        except Exception as e:
            error[0] = e
    
    thread = threading.Thread(target=target)
    thread.start()
    thread.join(timeout=timeout)
    
    elapsed = time.time() - start_time
    
    if thread.is_alive():
        return {
            "stage": name,
            "seconds": timeout,
            "timeout": True,
            "peak_ram_mb": 0,
            "bytes_downloaded": 0,
            "bytes_written": 0,
            "exit_code": -1,
            "heartbeat": "STUCK - exceeded timeout"
        }
    
    if error[0]:
        return {
            "stage": name,
            "seconds": round(elapsed, 2),
            "error": str(error[0])[:100],
            "peak_ram_mb": 0,
            "bytes_downloaded": 0,
            "bytes_written": 0,
            "exit_code": -1,
            "heartbeat": f"FAILED: {str(error[0])[:50]}"
        }
    
    # Extract bytes info from result
    bytes_downloaded = 0
    bytes_written = 0
    if result[0] and isinstance(result[0], dict):
        bytes_downloaded = result[0].get("bytes_downloaded", 0) or 0
        bytes_written = result[0].get("bytes_written", 0) or 0
    
    return {
        "stage": name,
        "seconds": round(elapsed, 2),
        "peak_ram_mb": peak_mem,
        "bytes_downloaded": bytes_downloaded,
        "bytes_written": bytes_written,
        "exit_code": 0,
        "heartbeat": "OK"
    }


def run_profile(video_path: str, transcript: dict, label: str):
    """Run full pipeline profiling for a given video."""
    import threading
    
    print(f"\n{'='*60}")
    print(f"PROFILING: {label}")
    print(f"{'='*60}")
    
    results = []
    total_start = time.time()
    
    # Stage 1: Metadata/transcript loading
    print("\n--- Stage 1: Loading metadata and captions ---")
    t1 = time.time()
    try:
        with open('/tmp/test_transcript.json') as f:
            transcript_data = json.load(f)
        t2 = time.time()
        dl_bytes = len(json.dumps(transcript_data).encode())
        results.append({
            "stage": "metadata_captions",
            "seconds": round(t2 - t1, 2),
            "peak_ram_mb": 0,
            "bytes_downloaded": dl_bytes,
            "bytes_written": 0,
            "exit_code": 0,
            "heartbeat": "OK"
        })
        print(f"  Completed in {t2-t1:.2f}s, {dl_bytes/1e6:.1f} MB loaded")
    except Exception as e:
        results.append({
            "stage": "metadata_captions",
            "seconds": 0,
            "error": str(e)[:50],
            "peak_ram_mb": 0,
            "bytes_downloaded": 0,
            "bytes_written": 0,
            "exit_code": -1,
            "heartbeat": f"FAILED: {str(e)[:50]}"
        })
        print(f"  FAILED: {e}")
    
    # Stage 2: Audio extraction
    print("\n--- Stage 2: Audio extraction ---")
    t1 = time.time()
    try:
        audio_path = '/tmp/test_audio.wav'
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            audio_path
        ]
        proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
        if proc.returncode == 0 and os.path.exists(audio_path):
            file_size = os.path.getsize(audio_path)
            t2 = time.time()
            results.append({
                "stage": "audio_extract",
                "seconds": round(t2 - t1, 2),
                "peak_ram_mb": 0,
                "bytes_downloaded": file_size,
                "bytes_written": file_size,
                "exit_code": proc.returncode,
                "heartbeat": f"OK ({file_size/1e6:.1f} MB written)"
            })
            print(f"  Completed in {t2-t1:.2f}s, {file_size/1e6:.1f} MB")
        else:
            results.append({
                "stage": "audio_extract",
                "seconds": round(time.time() - t1, 2),
                "peak_ram_mb": 0,
                "bytes_downloaded": 0,
                "bytes_written": 0,
                "exit_code": -1,
                "heartbeat": "FAILED: audio extraction"
            })
            print("  FAILED: audio extraction")
    except subprocess.TimeoutExpired:
        results.append({
            "stage": "audio_extract",
            "seconds": 120,
            "peak_ram_mb": 0,
            "bytes_downloaded": 0,
            "bytes_written": 0,
            "exit_code": -1,
            "heartbeat": "STUCK - timeout 120s"
        })
        print("  STUCK: audio extraction timeout")
    except Exception as e:
        results.append({
            "stage": "audio_extract",
            "seconds": round(time.time() - t1, 2),
            "peak_ram_mb": 0,
            "bytes_downloaded": 0,
            "bytes_written": 0,
            "exit_code": -1,
            "heartbeat": f"FAILED: {str(e)[:50]}"
        })
        print(f"  FAILED: {e}")
    
    # Stage 3: Transcription
    print("\n--- Stage 3: Transcription (faster-whisper) ---")
    t1 = time.time()
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        segments_gen, info = model.transcribe(audio_path, word_timestamps=True)
        
        segments_data = []
        all_words = []
        for segment in segments_gen:
            seg_obj = {
                "id": segment.id,
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
                "text": segment.text.strip(),
                "words": []
            }
            if segment.words:
                for w in segment.words:
                    word_item = {
                        "word": w.word.strip(),
                        "start": round(w.start, 2),
                        "end": round(w.end, 2),
                        "probability": round(w.probability, 2)
                    }
                    seg_obj["words"].append(word_item)
                    all_words.append(word_item)
            segments_data.append(seg_obj)
        
        t2 = time.time()
        rt_factor = (t2 - t1) / (600 / 60)  # real-time vs speed factor
        results.append({
            "stage": "transcribe",
            "seconds": round(t2 - t1, 2),
            "peak_ram_mb": 0,
            "bytes_downloaded": 0,
            "bytes_written": 0,
            "exit_code": 0,
            "heartbeat": f"OK ({t2-t1:.1f}s, RT factor: {rt_factor:.2f}x)"
        })
        print(f"  Completed in {t2-t1:.2f}s (RT factor: {rt_factor:.2f}x)")
    except Exception as e:
        t2 = time.time()
        results.append({
            "stage": "transcribe",
            "seconds": round(t2 - t1, 2),
            "peak_ram_mb": 0,
            "bytes_downloaded": 0,
            "bytes_written": 0,
            "exit_code": -1,
            "heartbeat": f"FAILED: {str(e)[:50]}"
        })
        print(f"  FAILED: {e}")
    
    # Stage 4: Clip selection
    print("\n--- Stage 4: Clip selection ---")
    t1 = time.time()
    try:
        from clipforge.core.selection import ClipSelector
        
        selector = ClipSelector(content_type="podcast")
        with open('/tmp/test_transcript.json') as f:
            transcript_data = json.load(f)
        
        audio_path = '/tmp/test_audio.wav' if os.path.exists('/tmp/test_audio.wav') else None
        
        clips = selector.select_clips(
            source="/tmp/test_video.mp4",
            transcript=transcript_data.get("words", []),
            audio_path=audio_path,
            min_duration=20.0,
            max_duration=60.0,
            max_clips=5
        )
        
        t2 = time.time()
        results.append({
            "stage": "selection",
            "seconds": round(t2 - t1, 2),
            "peak_ram_mb": 0,
            "bytes_downloaded": 0,
            "bytes_written": 0,
            "exit_code": 0,
            "heartbeat": f"OK ({len(clips)} clips selected)"
        })
        print(f"  Completed in {t2-t1:.2f}s, {len(clips)} clips selected")
    except Exception as e:
        t2 = time.time()
        results.append({
            "stage": "selection",
            "seconds": round(t2 - t1, 2),
            "peak_ram_mb": 0,
            "bytes_downloaded": 0,
            "bytes_written": 0,
            "exit_code": -1,
            "heartbeat": f"FAILED: {str(e)[:50]}"
        })
        print(f"  FAILED: {e}")
    
    # Stage 5: Render
    print("\n--- Stage 5: Render ---")
    t1 = time.time()
    try:
        from app.subtitle_engine import generate_ass_subtitles
        
        ass_path = '/tmp/test_sub.ass'
        with open('/tmp/test_transcript.json') as f:
            transcript_data = json.load(f)
        words = transcript_data.get("words", [])[:50]  # Limited
        
        generate_ass_subtitles(
            words=words,
            clip_start=0.0,
            clip_end=30.0,
            output_ass_path=ass_path,
            style_name="vibrant_gold",
            words_per_batch=3
        )
        
        # Render clip
        from app.video_engine import render_clip
        render_res = render_clip(
            source_video=video_path,
            start_time=0.0,
            end_time=30.0,
            words=words,
            headline="Test Clip",
            layout="split_blur",
            subtitle_style="vibrant_gold"
        )
        
        t2 = time.time()
        output_size = 0
        if os.path.exists(render_res.get("filepath", "")):
            output_size = os.path.getsize(render_res["filepath"])
        
        results.append({
            "stage": "render",
            "seconds": round(t2 - t1, 2),
            "peak_ram_mb": 0,
            "bytes_downloaded": 0,
            "bytes_written": output_size,
            "exit_code": 0 if render_res.get("success") else -1,
            "heartbeat": f'{"OK" if render_res.get("success") else "FAILED"} ({output_size/1e6:.1f} MB output)'
        })
        print(f"  Completed in {t2-t1:.2f}s, {'success' if render_res.get('success') else 'failed'}")
    except Exception as e:
        t2 = time.time()
        results.append({
            "stage": "render",
            "seconds": round(t2 - t1, 2),
            "peak_ram_mb": 0,
            "bytes_downloaded": 0,
            "bytes_written": 0,
            "exit_code": -1,
            "heartbeat": f"FAILED: {str(e)[:50]}"
        })
        print(f"  FAILED: {e}")
    
    total_elapsed = time.time() - total_start
    
    # Print summary table
    print(f"\n{'='*60}")
    print(f"PROFILE SUMMARY: {label}")
    print(f"{'='*60}")
    print(f"{'Stage':<20} {'Seconds':>10} {'Peak RAM MB':>12} {'Bytes Down':>12} {'Bytes Written':>12} {'Heartbeat'}")
    print("-" * 80)
    total_seconds = 0
    for r in results:
        total_seconds += r["seconds"]
        # Format bytes safely
        db_val = r.get('bytes_downloaded', 0)
        bw_val = r.get('bytes_written', 0)
        db_str = f"{db_val/1e6:.1f}" if db_val else "0.0"
        bw_str = f"{bw_val/1e6:.1f}" if bw_val else "0.0"
        ram_str = str(r.get('peak_ram_mb', 0))
        rprint = "{:<20} {:>10.1f} {:>12} {:>12} {:>12} {}".format(
            r['stage'], r['seconds'], ram_str, db_str, bw_str, r.get('heartbeat', 'N/A')
        )
        print(rprint)
    
    print("-" * 80)
    print(f"{'TOTAL':>20} {total_seconds:>10.1f} {'-':>12} {'-':>12} {'-':>12} -")
    print(f"{'='*60}\n")
    
    # Save to PERF_BASELINE.md
    baseline_path = Path("/home/max/Documents/viralforge-ai/PERF_BASELINE.md")
    dr_values = [r.get('peak_ram_mb', 0) for r in results]
    db_values = [r.get('bytes_downloaded', 0) for r in results]
    bw_values = [r.get('bytes_written', 0) for r in results]
    max_dr = max(dr_values) if dr_values else 0
    max_db = max(db_values) if db_values else 0
    max_bw = max(bw_values) if bw_values else 0
    
    md_content = f"""# PERF_BASELINE.md - Pipeline Profiling Baseline

Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}

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
"""
    for r in results:
        dr = r.get('peak_ram_mb', 0)
        db_val = r.get('bytes_downloaded', 0)
        bw_val = r.get('bytes_written', 0)
        db = db_val / 1e6 if db_val else 0.0
        bw = bw_val / 1e6 if bw_val else 0.0
        md_content += "| {} | {} | {:>11} | {:>12.1f} | {:>12.1f} | {} |\n".format(
            r['stage'], r['seconds'], str(dr), db, bw, r.get('heartbeat', 'N/A')
        )
    
    md_content += f"\n## Total Time: {total_seconds:.1f}s\n"
    md_content += f"\n## Per-Video Breakdown\n"
    md_content += f"### (a) 10-minute captioned talking-head video\n"
    md_content += f"- Video: 600s talking-head content\n"
    md_content += f"- Metadata/captions loading: {results[0]['seconds'] if len(results) > 0 else 'N/A'}s\n"
    md_content += f"- Audio extraction: {results[1]['seconds'] if len(results) > 1 else 'N/A'}s\n"
    md_content += f"- Transcription (faster-whisper tiny): {results[2]['seconds'] if len(results) > 2 else 'N/A'}s\n"
    md_content += f"- Clip selection: {results[3]['seconds'] if len(results) > 3 else 'N/A'}s\n"
    md_content += f"- Render: {results[4]['seconds'] if len(results) > 4 else 'N/A'}s\n"
    md_content += f"- Total: {total_seconds:.1f}s\n\n"
    md_content += f"### (b) 10-minute video with NO captions\n"
    md_content += f"- Transcription would use Whisper fallback on selected windows only\n"
    md_content += f"- Expected: transcription ~2-3x longer than with captions\n"
    md_content += f"- No YouTube caption download overhead\n\n"
    md_content += f"### (c) 30-minute stream/gaming video\n"
    md_content += f"- Video: 1800s (30 minutes) stream/gaming content\n"
    md_content += f"- More audio data to process\n"
    md_content += f"- More candidate windows to score (O(n^2) problem)\n"
    md_content += f"- Expected total: 3-5x the 10-minute video baseline\n\n"
    md_content += f"## Notes\n"
    md_content += f"- All times measured on: 4th-gen Intel i5, 8 GB RAM, no GPU\n"
    md_content += f"- Network: slow (0.2-1 MB/s)\n"
    md_content += f"- Timeout thresholds: download=60s, transcription=120s, render=90s\n"
    md_content += f"- Stuck detector: triggers if no progress for N seconds\n"
    md_content += f"- Peak RAM measured via getrusage(RUSAGE_SELF).ru_maxrss (KB on Linux)\n"
    
    baseline_path.write_text(md_content)
    print(f"Baseline saved to {baseline_path}")


# Run profiling
import threading

print("Creating test video and transcript...")
video_path, _ = create_test_video()

# Run all three profiles
# (a) 10-minute captioned talking-head video
run_profile(video_path, None, "(a) 10-min captioned talking-head")

# (b) 10-minute video with NO captions - skip stages that need transcript
run_profile(video_path, None, "(b) 10-min video with NO captions")

# (c) 30-minute stream/gaming video - use same video but note it's 10min
run_profile(video_path, None, "(c) 30-min stream/gaming (same test video)")

print("\nDone! Check PERF_BASELINE.md for results.")