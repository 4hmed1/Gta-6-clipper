"""YouTube caption fetching module.

Fetches YouTube captions in json3 format with word-level timing.
This is the fastest way to get transcriptions (no AI model needed).
"""

import os
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List
from app.config import DOWNLOADS_DIR

def fetch_youtube_captions(url: str, progress_callback=None) -> Dict[str, Any]:
    """
    Fetch YouTube captions in json3 format with word-level timestamps.
    Returns the same format as transcribe_audio for direct use.
    
    Args:
        url: YouTube video URL
        progress_callback: Optional progress callback
        
    Returns:
        Dict with 'success', 'language', 'duration', 'text', 'segments', 'words'
        Same format as transcriber output
    """
    if progress_callback:
        progress_callback("Fetching YouTube captions...", 10)
    
    # Extract video ID from URL
    video_id = url.split("v=")[-1].split("&")[0].split("/")[0]
    
    # Output file for captions
    caption_file = DOWNLOADS_DIR / f"captions_{video_id}.json"
    
    try:
        # Use yt-dlp to fetch json3 captions (word-level timing)
        import yt_dlp
        
        opts = {
            "write_subs": True,
            "write-auto-subs": True,
            "sub_format": "json3",
            "outtmpl": str(DOWNLOADS_DIR / f"temp_{video_id}"),
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,  # Don't download video
        }
        
        if progress_callback:
            progress_callback("Downloading caption tracks...", 20)
            
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        
        # Find the caption file (usually ends with .json3)
        caption_files = list(DOWNLOADS_DIR.glob(f"temp_{video_id}*.json3"))
        if not caption_files:
            caption_files = list(DOWNLOADS_DIR.glob(f"temp_{video_id}*.json"))
            
        if not caption_files:
            return {
                "success": False,
                "error": "No caption files found",
                "language": None,
                "duration": 0,
                "text": "",
                "segments": [],
                "words": []
            }
        
        caption_file = caption_files[0]
        
        # Parse json3 captions
        with open(caption_file, 'r', encoding='utf-8') as f:
            caption_data = json.load(f)
        
        # Convert to same format as transcriber
        segments_data = []
        all_words = []
        full_text = []
        
        # json3 format: array of segments, each with words
        for i, segment in enumerate(caption_data.get("events", [])):
            if not isinstance(segment, dict) or "words" not in segment:
                continue
                
            seg_start = segment.get("start", 0)
            seg_end = segment.get("end", 0)
            seg_text = segment.get("text", "").strip()
            
            if not seg_text:
                continue
                
            # Add segment
            seg_obj = {
                "id": i,
                "start": round(seg_start, 2),
                "end": round(seg_end, 2),
                "text": seg_text,
                "words": []
            }
            
            # Add words with timing
            for word in segment.get("words", []):
                if not isinstance(word, dict):
                    continue
                    
                word_text = word.get("word", "").strip()
                if not word_text:
                    continue
                    
                word_obj = {
                    "word": word_text,
                    "start": round(word.get("start", seg_start), 2),
                    "end": round(word.get("end", seg_end), 2),
                    "probability": 1.0  # YouTube captions are assumed to be accurate
                }
                
                seg_obj["words"].append(word_obj)
                all_words.append(word_obj)
            
            segments_data.append(seg_obj)
            full_text.append(seg_text)
        
        # Get duration from last segment
        duration = segments_data[-1]["end"] if segments_data else 0
        
        # Clean up temp files
        for temp_file in DOWNLOADS_DIR.glob(f"temp_{video_id}*"):
            try:
                os.remove(temp_file)
            except:
                pass
        
        if progress_callback:
            progress_callback(f"Loaded {len(all_words)} caption words", 100)
        
        return {
            "success": True,
            "language": caption_data.get("language", "en"),
            "duration": duration,
            "text": " ".join(full_text),
            "segments": segments_data,
            "words": all_words,
            "source": "youtube_captions"
        }
        
    except subprocess.CalledProcessError as e:
        error_msg = f"Caption fetch failed: {e.stderr.decode('utf-8', errors='replace') if e.stderr else str(e)}"
        return {
            "success": False,
            "error": error_msg,
            "language": None,
            "duration": 0,
            "text": "",
            "segments": [],
            "words": []
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "language": None,
            "duration": 0,
            "text": "",
            "segments": [],
            "words": []
        }
    finally:
        # Clean up temp files even on error
        for temp_file in DOWNLOADS_DIR.glob(f"temp_{video_id}*"):
            try:
                os.remove(temp_file)
            except:
                pass