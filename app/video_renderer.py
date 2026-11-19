import subprocess
from pathlib import Path
from typing import Dict, Any

def render_final_clip(
    source_video: str,
    crop_coords: Dict[str, Any],
    output_path: str,
    subtitle_path: str,
    whoosh_effect: str = "static/assets/whoosh.wav"
) -> str:
    """
    Renders a viral clip using a complex FFmpeg filtergraph:
    1. Smart Crop/Split-screen
    2. Dynamic Zoom on peaks
    3. Cinematic Color Grading
    4. Subtitle burn-in
    5. High-speed 60fps export
    """

    # 1. Define Filtergraph
    # Color grading
    color_filter = "eq=contrast=1.08:saturation=1.15"

    # Crop/Layout
    if crop_coords["type"] == "split":
        # Stacked layout logic
        layout_filter = "crop=iw:ih/2:0:0[top];crop=iw:ih/2:0:ih/2[bottom];[top][bottom]vstack=inputs=2"
    else:
        # Standard dynamic crop from smart_cropper.py
        x = crop_coords.get("x", 0)
        w = crop_coords.get("w", 1080)
        layout_filter = f"crop={w}:1920:{x}:0"

    # Dynamic zoom filter (105% punch-in zoom every 4.5s)
    # Using 'zoompan' filter for dynamic movement
    zoom_filter = "zoompan=z='min(zoom+0.001,1.05)':d=270:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920"

    # Combined complex filter
    filter_complex = f"[0:v]{layout_filter},{color_filter},{zoom_filter}[v];[v]subtitles='{subtitle_path}'[finalv]"

    # 2. Build FFmpeg command
    cmd = [
        "ffmpeg", "-y",
        "-i", source_video,
    ]

    if Path(whoosh_effect).exists():
        cmd += ["-i", whoosh_effect]
        # Mix audio: whoosh on hard cuts (simplified for this pipeline)
        cmd += ["-filter_complex", f"{filter_complex};[1:a]amix=inputs=2[finala]"]
        map_args = ["-map", "[finalv]", "-map", "[finala]"]
    else:
        cmd += ["-filter_complex", filter_complex]
        map_args = ["-map", "[finalv]", "-map", "0:a"]

    cmd += [
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-r", "60",
        "-c:a", "aac",
        "-b:a", "192k",
        output_path
    ]

    subprocess.run(cmd, check=True, timeout=max(300, duration * 10))
    return output_path
