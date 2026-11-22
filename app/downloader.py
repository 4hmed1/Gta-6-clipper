import os
import re
import uuid
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List
from app.config import DOWNLOADS_DIR, UPLOADS_DIR

def clean_filename(title: str) -> str:
    """Sanitize title for safe filesystem use."""
    clean = re.sub(r'[\\/*?:"<>|]', "", title)
    return clean[:50].strip().replace(" ", "_")

def get_video_metadata(filepath: str) -> Dict[str, Any]:
    """Extract video duration, resolution and format using ffprobe."""
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration:stream=width,height,codec_type",
            "-of", "json",
            filepath
        ]
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            timeout=60,
        )
        data = json.loads(res.stdout)
        
        duration = float(data.get("format", {}).get("duration", 0))
        width = 1920
        height = 1080
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                width = int(stream.get("width", 1920))
                height = int(stream.get("height", 1080))
                break
                
        return {
            "duration": round(duration, 2),
            "width": width,
            "height": height,
            "filepath": filepath
        }
    except Exception as e:
        print(f"[Downloader] ffprobe error: {e}")
        return {
            "duration": 0,
            "width": 1920,
            "height": 1080,
            "filepath": filepath
        }

def _yt_progress(d: Dict[str, Any], progress_callback) -> None:
    """Push real download progress back through the pipeline callback."""
    if not progress_callback or not isinstance(d, dict):
        return
    status = d.get("_status") or d.get("status")
    if status != "downloading":
        return
    total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
    downloaded = d.get("downloaded_bytes") or 0
    speed = d.get("speed") or 0
    eta = d.get("eta") or 0
    
    # Calculate more accurate stage based on what's being downloaded
    info = d.get('info_dict', {})
    is_audio = info.get('vcodec') == 'none'
    prefix = "Downloading audio analysis stream..." if is_audio else "Downloading video sections..."

    if total:
        pct = (downloaded / total) * 100
        speed_mb = speed / (1024 * 1024) if speed else 0
        msg = f"{prefix} {pct:.1f}% ({downloaded/1e6:.1f}/{total/1e6:.1f} MB, {speed_mb:.2f} MB/s, ETA {int(eta)}s)"
        # Map 0-100% download to a sub-range of the overall pipeline progress
        progress_callback(msg, 10 + (pct * 0.15))
    else:
        progress_callback(f"{prefix} {downloaded/1e6:.1f} MB", 15)


def download_youtube_video(url: str, progress_callback=None, audio_only: bool = False, sections: List[Dict[str, float]] = None) -> Dict[str, Any]:
    """
    Download a video from YouTube or any supported site via yt-dlp.
    Optimized for slow networks:
    - Audio-only first for fast analysis
    - Parallel fragment downloads (-N 4)
    - Section downloads (--download-sections) for final clips
    """
    video_id = str(uuid.uuid4())[:8]
    suffix = "wav" if audio_only else "mp4"
    output_template = str(DOWNLOADS_DIR / f"%(title)s_{video_id}.%(ext)s")
    
    print(f"[Downloader] Ingesting {url} (audio_only={audio_only}, sections={len(sections) if sections else 0})")
    if progress_callback:
        progress_callback("Connecting to video source and fetching stream...", 10)

    try:
        import yt_dlp

        ydl_opts = {
            'extract_flat': False,
            'extractor_args': {'youtube': {'player_client': ['android', 'web', 'ios', 'tv_embedded', 'mweb']}},
            'outtmpl': output_template,
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'progress_hooks': [lambda d: _yt_progress(d, progress_callback)],
            # --- Performance Optimizations ---
            'concurrent_fragment_downloads': 4,
            'retries': 5,
            'fragment_retries': 5,
            'socket_timeout': 30,
            'continuedl': True,
        }

        # yt-dlp now requires a JavaScript runtime to extract YouTube formats
        # (older extractor is deprecated). Use node/deno/bun if present.
        for _rt in ("node", "deno", "bun", "qjs"):
            if shutil.which(_rt):
                ydl_opts['js_runtimes'] = {_rt: {}}
                break

        if audio_only:
            # Lowest bitrate audio for fast analysis (approx 64k-128k)
            ydl_opts['format'] = 'ba[abr<=64]/ba[abr<=128]/worstaudio'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
                'preferredquality': '192',
            }]
        else:
            # Smart section download or 720p/1080p
            ydl_opts['format'] = 'best[height<=1080][ext=mp4]/best[height<=1080]/best'
            ydl_opts['merge_output_format'] = 'mp4'
            
            if sections:
                # Add pre-roll/post-roll margins for cleaner cuts (0.5s each)
                ydl_opts['download_ranges'] = lambda info, dict_obj: [
                    {'start_time': max(0, s['start'] - 0.5), 'end_time': s['end'] + 0.5}
                    for s in sections
                ]
                ydl_opts['force_keyframes_at_cuts'] = True

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # Fix filename after post-processing
            if audio_only:
                filename = str(Path(filename).with_suffix(".wav"))
            else:
                base, ext = os.path.splitext(filename)
                if ext != ".mp4" and os.path.exists(f"{base}.mp4"):
                    filename = f"{base}.mp4"

            meta = get_video_metadata(filename)
            return {
                "success": True,
                "title": info.get("title", "Untitled Video"),
                "duration": meta["duration"] or info.get("duration", 0),
                "filepath": filename,
                "thumbnail": info.get("thumbnail", ""),
                "author": info.get("uploader", "Unknown"),
                "width": meta["width"],
                "height": meta["height"]
            }

    except Exception as e:
        print(f"[Downloader] Error: {type(e).__name__}: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def save_uploaded_file(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """Save user-uploaded video file and inspect metadata."""
    file_id = str(uuid.uuid4())[:8]
    ext = Path(filename).suffix or ".mp4"
    saved_name = f"upload_{file_id}_{clean_filename(Path(filename).stem)}{ext}"
    saved_path = UPLOADS_DIR / saved_name
    
    with open(saved_path, "wb") as f:
        f.write(file_bytes)
        
    meta = get_video_metadata(str(saved_path))
    return {
        "success": True,
        "title": Path(filename).stem,
        "duration": meta["duration"],
        "filepath": str(saved_path),
        "thumbnail": "",
        "author": "Local Upload",
        "width": meta["width"],
        "height": meta["height"]
    }
