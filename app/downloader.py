import os
import re
import uuid
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
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
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
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
    if total:
        pct = min(95.0, (downloaded / total) * 100)
        msg = f"Downloading video stream... {pct:.1f}% ({downloaded/1e6:.1f}/{total/1e6:.1f} MB, {speed/1e6:.1f} MB/s, ETA {int(eta)}s)"
        progress_callback(msg, 10 + (pct * 0.12))
    else:
        progress_callback(f"Downloading video stream... {downloaded/1e6:.1f} MB", 15)


def download_youtube_video(url: str, progress_callback=None) -> Dict[str, Any]:
    """
    Download a video from YouTube or any supported site via yt-dlp.
    Falls back to yt-dlp CLI if library isn't directly imported.
    """
    video_id = str(uuid.uuid4())[:8]
    output_template = str(DOWNLOADS_DIR / f"%(title)s_{video_id}.%(ext)s")
    
    print(f"[Downloader] Initiating download for URL: {url}")
    if progress_callback:
        progress_callback("Connecting to video source and fetching stream...", 10)

    try:
        import yt_dlp

        ydl_opts = {
            # Cap at 1080p — 4K grabs 300MB+ files and stalls on slow links.
            # Prefer mp4, fall back to any format, merge audio.
            'format': 'best[height<=1080]/best',
            'extract_flat': False,
            'extractor_args': {'youtube': {'player_client': ['android', 'web', 'ios', 'tv_embedded', 'mweb']}},
            'outtmpl': output_template,
            'merge_output_format': 'mp4',
            'noplaylist': True,
            'quiet': False,
            'no_warnings': True,
            'progress_hooks': [lambda d: _yt_progress(d, progress_callback)],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if progress_callback:
                progress_callback("Extracting video metadata...", 25)
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            # Ensure mp4 extension if merged
            base, _ = os.path.splitext(filename)
            mp4_file = f"{base}.mp4"
            final_file = mp4_file if os.path.exists(mp4_file) else filename

            meta = get_video_metadata(final_file)
            return {
                "success": True,
                "title": info.get("title", "Untitled Video"),
                "duration": meta["duration"] or info.get("duration", 0),
                "filepath": final_file,
                "thumbnail": info.get("thumbnail", ""),
                "author": info.get("uploader", "Unknown"),
                "width": meta["width"],
                "height": meta["height"]
            }

    except ImportError:
        # Fallback to system yt-dlp CLI if module not installed
        print("[Downloader] yt_dlp python module not found, attempting system command...")
        final_mp4 = str(DOWNLOADS_DIR / f"video_{video_id}.mp4")
        cmd = [
            "yt-dlp",
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "--merge-output-format", "mp4",
            "-o", final_mp4,
            url
        ]
        subprocess.run(cmd, check=True)
        meta = get_video_metadata(final_mp4)
        return {
            "success": True,
            "title": f"Video_{video_id}",
            "duration": meta["duration"],
            "filepath": final_mp4,
            "thumbnail": "",
            "author": "Online Stream",
            "width": meta["width"],
            "height": meta["height"]
        }
    except Exception as e:
        print(f"[Downloader] Download error: {e}")
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
