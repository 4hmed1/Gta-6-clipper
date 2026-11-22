import os
import subprocess
import uuid
from pathlib import Path
from typing import Dict, Any, List
from app.config import CLIPS_DIR
from app.subtitle_engine import generate_ass_subtitles

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

    # 1. Generate Kinetic ASS Subtitles
    has_subtitles = bool(words)
    if has_subtitles:
        generate_ass_subtitles(
            words=words,
            clip_start=start_time,
            clip_end=end_time,
            output_ass_path=sub_path,
            style_name=subtitle_style
        )

    # 2. Construct ffmpeg filter graph
    escaped_sub = escape_ffmpeg_path(sub_path)
    
    if layout == "split_blur":
        # 9:16 Vertical Short with Blurred Background & Centered Crisp Foreground
        filter_complex = (
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
            f"boxblur=24:6,eq=brightness=-0.18[bg];"
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
        "-ss", str(start_time),
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
        "-preset", "veryfast",
        "-crf", "22",
        "-c:a", "aac",
        "-b:a", "160k",
        "-movflags", "+faststart",
        output_path
    ]

    print(f"[VideoEngine] Rendering clip {output_filename} ({duration:.1f}s)...")
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
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
