import os
import subprocess
import uuid
from pathlib import Path
from typing import Dict, Any, List
from app.config import CLIPS_DIR
from app.captions.track import caption_track_from_json3, caption_track_from_words, Word, STYLES

def escape_ffmpeg_path(path: str) -> str:
    """Escape path for ffmpeg filtergraph syntax."""
    # Replace backslashes with forward slashes, escape colons and special chars
    p = str(path).replace("\\", "/")
    p = p.replace(":", "\\:")
    p = p.replace("'", "\\'")
    p = p.replace("[", "\\[")
    p = p.replace("]", "\\]")
    return p

def extract_thumbnail(video_path: str, output_thumb: str, timestamp: float = 1.0) -> str:
    """Generate high-quality JPEG thumbnail."""
    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(timestamp),
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            output_thumb
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return output_thumb
    except Exception as e:
        print(f"[VideoEngine] Thumbnail error: {e}")
        return ""

def render_clip(
    source_video: str,
    start_time: float,
    end_time: float,
    words: List[Dict[str, Any]],
    headline: str = "",
    layout: str = "split_blur",  # "split_blur", "center_crop", "original"
    subtitle_style: str = "hormozi",
    output_filename: str = ""
) -> Dict[str, Any]:
    """
    Cuts video clip, reframes to 9:16 vertical, and burns kinetic subtitles with ffmpeg.
    """
    clip_id = str(uuid.uuid4())[:8]
    if not output_filename:
        output_filename = f"clip_{clip_id}_{int(start_time)}_{int(end_time)}.mp4"
        
    output_path = str(CLIPS_DIR / output_filename)
    sub_path = str(CLIPS_DIR / f"sub_{clip_id}.ass")
    thumb_path = str(CLIPS_DIR / f"thumb_{clip_id}.jpg")

    duration = max(1.0, end_time - start_time)

    # PROVE TIME BASE CONTRACT: words are source-relative times, clip_start/end are applied at render seek
    import subprocess
    try:
        ffprobe_cmd = ["ffprobe", "-hide_banner", "-show_entries",
                       "format=duration,start_time", "-v", "error",
                       source_video]
        probe = subprocess.run(ffprobe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
        lines = [l for l in probe.stdout.strip().split('\n') if ':' in l]
        source_start = float([l for l in lines if l.startswith('start_time:')][0].split(':')[1])
        source_duration = float([l for l in lines if l.startswith('duration:')][0].split(':')[1])
        source_end = source_start + source_duration
        # Validate that clip_start/end are within source bounds
        assert source_start <= start_time < source_end, f"clip_start {start_time} outside source [{source_start}, {source_end})"
        assert 0 <= end_time <= source_end, f"clip_end {end_time} outside source [0, {source_end})"
    except Exception as e:
        print(f"[VideoEngine] PROBE ERROR: {e}")
        source_start, source_duration = 0.0, duration

    print(f"[VideoEngine] Clip #{clip_id}: source={source_start:.1f}..{source_end:.1f}s, requested={start_time:.1f}..{end_time:.1f}s (duration={duration:.1f}s)")
    print(f"[VideoEngine] Clip #{clip_id}: First word (if any): {words[0] if words else 'NONE'} ... Last word: {words[-1] if words else 'NONE'}")

    # 1. Generate Kinetic ASS Subtitles using the new captions/track.py module
    has_subtitles = bool(words)
    if has_subtitles:
        ass_content, meta = caption_track_from_words(
            words=words,
            clip_start=start_time,
            clip_end=end_time,
            style_name=subtitle_style,
            words_per_batch=3,
            pause_threshold=0.35,
            max_words_per_group=4,
            mask_profanity=True,
            censor_mode="OFF",
            margin_v=420,
            wrap_style=2,
            max_lines=2,
            max_chars_per_line=16,
            font_name="DejaVu Sans",  # Fallback to system font
            font_size=28,
            uppercase=True,
        )
        # Write the ASS file
        Path(sub_path).parent.mkdir(parents=True, exist_ok=True)
        Path(sub_path).write_text(ass_content, encoding="utf-8")

        # FAIL LOUDLY: Validate that ASS actually has Dialogue events
        dialogue_count = ass_content.count('Dialogue:')
        if dialogue_count == 0:
            print(f"[VideoEngine] CRITICAL ERROR: Caption generation produced NO Dialogue events for clip {clip_id}")
            raise ValueError(f"CAPTIONS_FAILED: Generated ASS has no Dialogue events (words={len(words)}, style={subtitle_style})")

        first_diag_line = [l for l in ass_content.split('\n') if l.startswith('Dialogue:')][0]
        first_time = eval(first_diag_line.split(',')[2].strip())  # Start time in ASS format (s.s)
        first_real_time = first_time + start_time  # Convert ASS time to source time

        print(f"[VideoEngine] Clip #{clip_id}: ASS generated with {dialogue_count} Dialogue events")
        print(f"[VideoEngine] Clip #{clip_id}: First Dialogue at ASS_time={first_time:.2f}s -> Real_time={first_real_time:.2f}s")
        print(f"[VideoEngine] Clip #{clip_id}: Meta: {meta}")

    # 2. Construct ffmpeg filter graph
    escaped_sub = escape_ffmpeg_path(sub_path)
    
    if layout == "split_blur":
        # 9:16 Vertical Short with Blurred Background & Centered Crisp Foreground
        # OPTIMIZATION: Blur at 270x480 (low res) then upscale - much faster than blurring 1080x1920
        filter_complex = (
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
            f"scale=270:480,boxblur=24:6,eq=brightness=-0.18,"
            f"scale=1080:1920[bg];"
            f"[0:v]scale=1080:-2[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2[base]"
        )
        if has_subtitles:
            filter_complex += f";[base]subtitles='{escaped_sub}'[final]"
            map_out = "[final]"
        else:
            map_out = "[base]"

    elif layout == "center_crop":
        # Direct Center 9:16 Vertical Crop
        base_filter = "scale=-2:1920,crop=1080:1920"
        if has_subtitles:
            filter_complex = f"{base_filter},subtitles='{escaped_sub}'"
        else:
            filter_complex = base_filter
        map_out = None

    else:
        # Original Aspect Ratio
        if has_subtitles:
            filter_complex = f"subtitles='{escaped_sub}'"
            map_out = None
        else:
            filter_complex = ""
            map_out = None

    cmd = [
        "ffmpeg",
        "-y",
        "-nostdin",
        "-ss", str(start_time),   # Seek BEFORE input for faster seeking
        "-i", source_video,
        "-t", str(duration)
    ]

    if filter_complex:
        if layout == "split_blur":
            cmd += ["-filter_complex", filter_complex, "-map", map_out, "-map", "0:a?"]
        else:
            cmd += ["-vf", filter_complex]

    cmd += [
        "-c:v", "libx264",
        "-preset", "ultrafast",  # Faster than veryfast; quality still good for social
        "-crf", "28",           # Higher CRF = smaller file, faster encode
        "-pix_fmt", "yuv420p",  # Ensure compatibility
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        output_path
    ]

    print(f"[VideoEngine] Rendering clip {output_filename} ({duration:.1f}s)...")
    try:
        subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,     # Drain to /dev/null (no buffering risk)
            stderr=subprocess.DEVNULL,
            check=True,
            timeout=max(300, duration * 10),  # 300s max, or 10x clip duration
        )
        # Extract thumbnail
        extract_thumbnail(output_path, thumb_path, timestamp=min(1.5, duration / 2))

        # Cleanup subtitle file
        if os.path.exists(sub_path):
            os.remove(sub_path)

        return {
            "success": True,
            "clip_id": clip_id,
            "filename": output_filename,
            "filepath": output_path,
            "thumbnail": f"/api/clips/thumb/{Path(thumb_path).name}" if os.path.exists(thumb_path) else "",
            "start": round(start_time, 2),
            "end": round(end_time, 2),
            "duration": round(duration, 1),
            "headline": headline,
            "download_url": f"/api/clips/download/{output_filename}"
        }
    except subprocess.CalledProcessError as e:
        print(f"[VideoEngine] Render error: {e.stderr.decode('utf-8', errors='ignore')}")
        return {
            "success": False,
            "error": "FFmpeg encoding error during clip synthesis."
        }
