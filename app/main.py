import os
import uuid
import signal
import threading
import traceback
import asyncio
import logging
import time
from typing import Dict, Any, Optional, List
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import (
    BASE_DIR, OUTPUTS_DIR, CLIPS_DIR, DOWNLOADS_DIR, UPLOADS_DIR,
    STATIC_DIR, DEFAULT_SUBTITLE_STYLE, DEFAULT_ASPECT_RATIO
)
from app.downloader import download_youtube_video, save_uploaded_file
from app.transcriber import transcribe_audio
from app.viral_detector import detect_viral_clips
from app.video_engine import render_clip
from app.clip_editor import adjust_and_reexport_clip

app = FastAPI(
    title="GTA 6 Clipper",
    description="Free, local-first desktop app that turns YouTube/Twitch links into ready-to-post vertical Shorts with a CapCut-style editor.",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# In-memory task state tracking for real-time progress
tasks_state: Dict[str, Dict[str, Any]] = {}

# Track the PID of each running pipeline worker
# so the orphan detector can distinguish a genuinely-dead worker
# from a slow subprocess call (yt-dlp, FFmpeg).
_active_workers: Dict[str, int] = {}

# ── Error Classifier ──

def _worker_alive(pid: object) -> bool:
    """Check whether the worker with this PID is still alive.

    In-process BackgroundTasks share the process lifetime, so we treat a
    missing/invalid PID as dead and any traceable PID as alive. This avoids
    false-positive orphan kills during long yt-dlp/FFmpeg operations.
    """
    if not pid:
        return False
    try:
        os.kill(str(pid), 0)
    except ProcessLookupError:
        return False
    except (PermissionError, OSError):
        # PermissionError on Linux can mean the PID exists under another user;
        # treat as alive to avoid killing our own in-process workers.
        return True
    return True


def _classify_ytdlp_error(err_msg: str) -> Dict[str, str]:
    """Classify yt-dlp/FFmpeg errors into user-friendly categories."""
    err_lower = err_msg.lower() if err_msg else ""
    
    if "sign in to confirm" in err_lower or "not a bot" in err_lower:
        return {
            "user_msg": "YouTube thinks you're a bot. Use cookies or try a different network.",
            "tech_detail": err_msg,
            "fix": "Use --cookies-from-browser chrome, or export cookies to cookies.txt and use --cookies cookies.txt. Alternatively, upload the video file locally."
        }
    elif "private" in err_lower or "unavailable" in err_lower:
        return {
            "user_msg": "This video is private, removed, or unavailable.",
            "tech_detail": err_msg,
            "fix": "Check if the video is still available on YouTube. If it's your video, make sure it's public or unlisted."
        }
    elif "geo" in err_lower or "blocked" in err_lower:
        return {
            "user_msg": "This video is not available in your region.",
            "tech_detail": err_msg,
            "fix": "Use a VPN or proxy, or upload the video file locally."
        }
    elif "403" in err_msg or "404" in err_msg:
        return {
            "user_msg": "YouTube returned an error (403/404). The video may be private or removed.",
            "tech_detail": err_msg,
            "fix": "Try a different video or upload the file locally."
        }
    elif "timed out" in err_lower or "timeout" in err_lower:
        return {
            "user_msg": "YouTube did not respond in time. Check your internet connection.",
            "tech_detail": err_msg,
            "fix": "Retry, or upload the video file locally."
        }
    elif "no such file" in err_lower or "not found" in err_lower:
        return {
            "user_msg": "The video URL is invalid or the video was removed.",
            "tech_detail": err_msg,
            "fix": "Check the URL and try again."
        }
    else:
        return {
            "user_msg": "Download failed.",
            "tech_detail": err_msg,
            "fix": "Retry with a different network, use cookies, or upload the video file locally."
        }


def _check_and_clear_orphan_tasks():
    """Mark orphaned tasks as INTERRUPTED.

    A task is an orphan when its worker PID no longer exists. Because
    FastAPI BackgroundTasks run in-thread (same process), we guard against
    false positives: any task with a live worker PID is considered alive
    regardless of heartbeat age. No heuristic-age cutoff means yt-dlp/FFmpeg
    downloads that take minutes are never killed by mistake.
    """
    now = time.time()
    for task_id, state in list(tasks_state.items()):
        status = state.get("status", "")
        if status not in ("running", "working", "processing"):
            continue
        pid = _active_workers.get(task_id)
        # If the task never registered a worker, skip (it hasn't started yet)
        if pid is None:
            continue
        if _worker_alive(pid):
            continue  # Worker still alive → not an orphan
        # Worker truly dead → mark interrupted
        pipeline_logger.warning(
            f"[{task_id}] ORPHAN_TASK: status={status}, worker_pid={pid} dead"
        )
        state["status"] = "interrupted"
        state["error"] = "The job's worker stopped unexpectedly."
        state["message"] = "Job interrupted. Retry or delete."
        state["can_resume"] = True
        state["can_delete"] = True
        state["heartbeat"] = now


class ProcessRequest(BaseModel):
    url: Optional[str] = None
    filepath: Optional[str] = None
    ai_method: str = "heuristic"
    api_key: Optional[str] = ""
    subtitle_style: str = "hormozi"
    layout: str = "split_blur"
    min_duration: float = 20.0
    max_duration: float = 60.0
    max_clips: int = 5
    measured_speed_mbps: float = 1.0
    # New fields from UI Create screen
    clip_count: Optional[int] = None
    length_min: Optional[float] = None
    length_max: Optional[float] = None
    aspect: Optional[str] = "9:16"
    caption_style: Optional[str] = "pop-bold"
    framing: Optional[str] = "auto"
    hook_text: Optional[bool] = False
    tighten_pauses: Optional[bool] = True
    focus_text: Optional[str] = ""
    range_start: Optional[float] = None
    range_end: Optional[float] = None


class EditRequest(BaseModel):
    source_video: str
    start_time: float
    end_time: float
    headline: str
    layout: str = "split_blur"
    subtitle_style: str = "hormozi"
    custom_text: Optional[str] = ""
    words: Optional[list] = []


# ── Structured logging ──
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
pipeline_logger = logging.getLogger("clipforge.pipeline")
pipeline_logger.setLevel(logging.INFO)
_fh = logging.FileHandler(LOGS_DIR / "pipeline.log")
_fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
pipeline_logger.addHandler(_fh)


def _ytdlp_bin() -> str:
    """Locate the yt-dlp executable in the active Python environment."""
    import shutil
    import sys
    found = shutil.which("yt-dlp")
    if found:
        return found
    candidates = [
        Path(sys.executable).parent / "yt-dlp",
        Path(sys.executable).parent / "yt-dlp.exe",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    raise FileNotFoundError(
        "yt-dlp not found on PATH or in the active Python environment. "
        "Install it with: pip install yt-dlp"
    )


# ── Module-level async helpers ──

async def _run_subprocess_async(
    cmd: List[str],
    timeout: float,
    label: str = "",
) -> Dict[str, Any]:
    """Run a subprocess with guaranteed termination within ``timeout`` seconds.

    Why this helper exists (confirmed root cause of stuck jobs):
    yt-dlp can hang on network timeouts. A naive
    ``await asyncio.wait_for(proc.wait(), ...)`` followed by ``proc.kill()``
    + ``await proc.wait()`` can itself hang on Python 3.12+ when the
    subprocess ignores SIGTERM or pipes stay open after the kill.
    This helper:
      1. runs the child in its own process group (start_new_session) so
         every grandchild (yt-dlp -> ffprobe, etc.) is killed together,
      2. drains stdout/stderr in the background from the start,
      3. on timeout sends SIGKILL to the whole process group (cannot be ignored),
      4. always returns within ``timeout`` + a small grace period.

    Returns a dict: ``{returncode, stdout, stderr, timed_out}``.
    """
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.DEVNULL,
        start_new_session=True,  # own process group -> killpg on timeout
    )

    async def _drain():
        out, err = await proc.communicate()
        return out, err

    drain_task = asyncio.ensure_future(_drain())
    timed_out = False
    try:
        await asyncio.wait_for(proc.wait(), timeout=timeout)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        timed_out = True
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, OSError):
            try:
                proc.kill()
            except (ProcessLookupError, OSError):
                pass
    try:
        out, err = await asyncio.wait_for(drain_task, timeout=5.0)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        out = err = b""
        drain_task.cancel()
    return {
        "returncode": proc.returncode,
        "stdout": out,
        "stderr": err,
        "timed_out": timed_out,
    }


async def _fetch_metadata_and_captions(url: str) -> Dict[str, Any]:
    """Fetch metadata + caption tracks without downloading the video."""
    import json
    try:
        yt = _ytdlp_bin()
        cmd = [yt, "--no-playlist", "--skip-download", "--dump-json", "--socket-timeout", "15", "--js-runtimes", "node", url]
        res = await _run_subprocess_async(cmd, timeout=30.0, label="metadata")
        if res["timed_out"]:
            raise Exception("YouTube did not respond in 30s (metadata fetch timed out)")
        if res["returncode"] != 0:
            err = res["stderr"].decode("utf-8", errors="replace")[:500]
            raise Exception(f"yt-dlp failed: {err}")
        data = json.loads(res["stdout"].decode("utf-8", errors="replace"))
        captions = data.get("automatic_captions", {}) or {}
        manual_captions = data.get("captions", {}) or {}
        all_caps = {**manual_captions, **captions}
        return {
            "success": True,
            "title": data.get("title", "Untitled"),
            "duration": data.get("duration", 0),
            "thumbnail": data.get("thumbnail", ""),
            "available_captions": list(all_caps.keys()),
            "video_id": data.get("id", ""),
        }
    except Exception as e:
        pipeline_logger.error(f"Metadata fetch error: {e}")
        return {"success": False, "error": str(e)}


async def _download_audio_from_url(url: str) -> str:
    """Download low-bitrate audio (~64 kbps) from a URL for analysis only."""
    if not url:
        return ""
    yt = _ytdlp_bin()
    audio_path = str(DOWNLOADS_DIR / f"audio_{uuid.uuid4().hex[:8]}.wav")
    cmd = [
        yt,
        "-o", audio_path,
        "--format", "bestaudio/best",
        "--quiet", "--no-warnings", "--no-playlist",
        "--retries", "3", "--fragment-retries", "3",
        "--socket-timeout", "15",
        "--js-runtimes", "node",
        "--extract-audio",
        "--audio-format", "wav",
        "--audio-quality", "192",
        url,
    ]
    try:
        res = await _run_subprocess_async(cmd, timeout=180.0, label="audio-download")
        if res["timed_out"]:
            pipeline_logger.warning("Audio download timed out (180s)")
            return ""
        if res["returncode"] == 0 and Path(audio_path).exists():
            return audio_path
        err = res["stderr"].decode("utf-8", errors="replace")[:500] if res["stderr"] else "Unknown error"
        pipeline_logger.error(f"Audio download failed: {err}")
        try:
            Path(audio_path).unlink(missing_ok=True)
        except Exception:
            pass
        return ""
    except Exception as e:
        pipeline_logger.error(f"Audio download error: {e}")
        return ""


async def _download_sections(
    url: str,
    sections: List[Dict[str, float]],
    output_path: str,
    target_height: int = 720,
) -> Dict[str, Any]:
    """Download the full video at low resolution for local cutting.

    Uses multiple player clients (android, web, ios, tv) to bypass YouTube bot checks.
    We download once at low quality and let FFmpeg cut locally (faster and more reliable).
    """
    if not sections:
        return {"success": False, "error": "No valid sections specified"}
    player_clients = ["android", "web", "ios", "tv_embedded"]

    for client in player_clients:
        yt = _ytdlp_bin()
        cmd = [
            yt,
            "-o", output_path,
            "--format", f"best[height<={target_height}]/best",
            "--quiet", "--no-warnings", "--no-playlist",
            "--retries", "3", "--fragment-retries", "3",
            "--socket-timeout", "15",
            "--js-runtimes", "node",
            "--extractor-args", f"youtube:player_client={client}",
            url,
        ]
        try:
            res = await _run_subprocess_async(cmd, timeout=300.0, label=f"download-{client}")
            if res["timed_out"]:
                pipeline_logger.warning(f"player_client={client} timed out (300s)")
                continue
            if res["returncode"] == 0 and Path(output_path).exists():
                file_size = Path(output_path).stat().st_size
                pipeline_logger.info(f"Download succeeded with player_client={client} ({file_size/1e6:.1f} MB)")
                return {"success": True, "filepath": str(output_path), "file_size_mb": round(file_size / 1e6, 2)}
            err = res["stderr"].decode("utf-8", errors="replace")[:200] if res["stderr"] else "Unknown error"
            pipeline_logger.warning(f"player_client={client} failed: {err}")
        except Exception as e:
            pipeline_logger.warning(f"player_client={client} exception: {e}")

    return {"success": False, "error": "All player clients failed. Try --cookies-from-browser or a local upload."}


def _run_async(coro):
    """Run an async coroutine from a sync background-task thread."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None
    if loop and not loop.is_closed():
        return loop.run_until_complete(coro)
    return asyncio.run(coro)


# ── Pipeline worker ──

def run_processing_pipeline(task_id: str, req: ProcessRequest):
    """Background worker executing the complete pipeline with structured logging."""
    start_time = time.time()

    def set_status(msg: str, progress: int, stage: str = "processing"):
        tasks_state[task_id]["message"] = msg
        tasks_state[task_id]["progress"] = progress
        tasks_state[task_id]["stage"] = stage
        tasks_state[task_id]["heartbeat"] = time.time()
        pipeline_logger.info(f"[{task_id}] [{stage}] p={progress}% | {msg}")

    def fail_with(message: str, raw: str = ""):
        """Mark job failed with a classified, plain-language error."""
        classified = _classify_ytdlp_error(raw or message)
        tasks_state[task_id]["status"] = "failed"
        tasks_state[task_id]["progress"] = 0
        tasks_state[task_id]["heartbeat"] = time.time()
        tasks_state[task_id]["error"] = message or classified["user_msg"]
        tasks_state[task_id]["error_detail"] = classified["tech_detail"]
        tasks_state[task_id]["suggested_fix"] = classified["fix"]
        pipeline_logger.error(f"[{task_id}] JOB_FAILED: {message}")

    def fail_with(message: str, raw: str = ""):
        """Mark job failed with a classified, plain-language error."""
        classified = _classify_ytdlp_error(raw or message)
        tasks_state[task_id]["status"] = "failed"
        tasks_state[task_id]["progress"] = 0
        tasks_state[task_id]["heartbeat"] = time.time()
        tasks_state[task_id]["error"] = message or classified["user_msg"]
        tasks_state[task_id]["error_detail"] = classified["tech_detail"]
        tasks_state[task_id]["suggested_fix"] = classified["fix"]
        pipeline_logger.error(f"[{task_id}] JOB_FAILED: {message}")

    def record_stage(stage_name: str, details: str = ""):
        elapsed = time.time() - start_time
        pipeline_logger.info(f"[{task_id}] STAGE_COMPLETE: {stage_name} in {elapsed:.2f}s | {details}")

    try:
        # ── Step 0: Validate user-provided range server-side ──
        if req.range_start is not None or req.range_end is not None:
            r_start = req.range_start if req.range_start is not None else 0.0
            r_end = req.range_end if req.range_end is not None else None
            if r_start < 0 or (r_end is not None and r_end <= 0):
                tasks_state[task_id]["status"] = "failed"
                tasks_state[task_id]["error"] = "Invalid time range: times must be positive (use mm:ss or h:mm:ss)."
                pipeline_logger.error(f"[{task_id}] BAD_RANGE: start={r_start} end={r_end}")
                return
            if r_end is not None and r_end <= r_start:
                tasks_state[task_id]["status"] = "failed"
                tasks_state[task_id]["error"] = "Invalid time range: 'To' must be later than 'From'."
                pipeline_logger.error(f"[{task_id}] BAD_RANGE: start={r_start} >= end={r_end}")
                return
        if req.length_min is not None and req.length_max is not None and req.length_max < req.length_min:
            tasks_state[task_id]["status"] = "failed"
            tasks_state[task_id]["error"] = "Invalid clip length: max is shorter than min."
            pipeline_logger.error(f"[{task_id}] BAD_LENGTH: min={req.length_min} max={req.length_max}")
            return

        # ── Step 1: Metadata (tiny, no download) ──
        if req.url:
            set_status("Fetching video metadata and captions...", 5, "ingesting")
            meta_res = _run_async(_fetch_metadata_and_captions(req.url))
            if not meta_res.get("success"):
                fail_with("YouTube did not answer; retry, try cookies, or upload the file.", meta_res.get("error", "Metadata fetch failed"))
                return
            video_meta = meta_res
            set_status(f"Metadata: {video_meta.get('title','Video')} ({video_meta.get('duration',0)}s)", 10, "ingesting")
        elif req.filepath and os.path.exists(req.filepath):
            set_status("Loading local video file...", 5, "loading")
            video_meta = {
                "title": Path(req.filepath).stem,
                "duration": 0,
                "filepath": req.filepath,
                "available_captions": [],
            }
        else:
            fail_with("No valid URL or video file provided.")
            return

        source_video = video_meta.get("filepath", "")
        tasks_state[task_id]["video_info"] = video_meta
        record_stage("ingest", f"title={video_meta.get('title')}")

        # ── Step 2: Audio-only download (fast, ~2 MB for a 3-min video) ──
        set_status("Downloading low-bitrate audio for analysis...", 12, "analyzing")
        audio_path = ""
        if req.url:
            try:
                audio_path = _run_async(_download_audio_from_url(req.url))
            except Exception as e:
                pipeline_logger.error(f"[{task_id}] Audio download exception: {e}")
        elif source_video and Path(source_video).exists():
            # For local files, extract audio with ffmpeg
            import subprocess
            audio_path = str(Path(source_video).with_suffix(".wav"))
            cmd = ["ffmpeg", "-y", "-nostdin", "-i", source_video, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", "-loglevel", "error", audio_path]
            subprocess.run(cmd, check=False, capture_output=True, timeout=60)
            if not Path(audio_path).exists():
                audio_path = ""

        if audio_path and Path(audio_path).exists():
            set_status("Audio downloaded successfully", 20, "analyzing")
        else:
            pipeline_logger.warning(f"[{task_id}] Audio download failed – proceeding with captions only")

        # ── Step 3: Transcribe with word timing ──
        set_status("Extracting word-level timestamps...", 25, "transcribing")
        trans_input = audio_path if (audio_path and Path(audio_path).exists()) else (source_video if source_video else req.filepath)
        if not trans_input or not os.path.exists(trans_input):
            tasks_state[task_id]["status"] = "failed"
            tasks_state[task_id]["error"] = "Audio download failed and no local file available for transcription."
            pipeline_logger.error(f"[{task_id}] NO_AUDIO_FOR_TRANSCRIBE")
            return
        trans_res = transcribe_audio(
            trans_input,
            progress_callback=lambda m, p: set_status(m, p, "transcribing"),
        )
        if not trans_res.get("success"):
            tasks_state[task_id]["status"] = "failed"
            tasks_state[task_id]["error"] = "Transcription failed."
            pipeline_logger.error(f"[{task_id}] TRANSCRIBE_FAILED")
            return

        words = trans_res.get("words", [])
        for w in words:
            if isinstance(w.get("start"), (float,)):
                w["start"] = float(w["start"])
            if isinstance(w.get("end"), (float,)):
                w["end"] = float(w["end"])
        trans_res["words"] = words
        tasks_state[task_id]["transcript_words"] = words
        record_stage("transcribe", f"words={len(words)},is_mock={trans_res.get('is_mock', False)}")

        # ── Step 4: Clip selection ──
        # Use new UI fields for clip count and length
        clip_count = req.clip_count if req.clip_count and req.clip_count > 0 else req.max_clips
        length_min = req.length_min if req.length_min is not None else req.min_duration
        length_max = req.length_max if req.length_max is not None else req.max_duration

        set_status("Analyzing hooks, speech pacing & retention scores...", 55, "analyzing")
        clips_candidates = detect_viral_clips(
            trans_res,
            method=req.ai_method,
            api_key=req.api_key or "",
            min_duration=length_min,
            max_duration=length_max,
            max_clips=clip_count,
            progress_callback=lambda m, p: set_status(m, p, "analyzing"),
        )

        if not clips_candidates:
            if trans_res.get("is_mock") and not trans_res.get("words"):
                tasks_state[task_id]["status"] = "failed"
                tasks_state[task_id]["error"] = "No viral clips found and no real transcript available. Enable offline STT or provide a video with captions."
                pipeline_logger.error(f"[{task_id}] NO_CLIPS_NO_TRANSCRIPT")
                return
            tasks_state[task_id]["status"] = "failed"
            tasks_state[task_id]["error"] = "No viral clips could be identified."
            pipeline_logger.error(f"[{task_id}] NO_CLIPS_FOUND")
            return

        record_stage("select", f"candidates={len(clips_candidates)}")

        # ── Step 5: Download the video ONCE (low quality), cut locally ──
        selected = clips_candidates[: req.max_clips]
        video_for_render = source_video  # local file, if provided

        if req.url:
            set_status("Downloading video (low quality, cut locally)...", 70, "downloading")
            target_h = 480 if req.measured_speed_mbps < 0.5 else 720
            section_path = str(DOWNLOADS_DIR / f"video_{task_id}.mp4")
            dl_res = _run_async(_download_sections(
                req.url,
                selected,
                section_path,
                target_height=target_h,
            ))
            if dl_res.get("success"):
                video_for_render = dl_res["filepath"]
                set_status(f"Video downloaded ({dl_res.get('file_size_mb', 0)} MB)", 80, "downloading")
            else:
                fail_with("Download failed.", dl_res.get("error", "unknown error"))
                return
        elif not (video_for_render and Path(video_for_render).exists()):
            tasks_state[task_id]["status"] = "failed"
            tasks_state[task_id]["error"] = "No video file available to render clips."
            pipeline_logger.error(f"[{task_id}] NO_VIDEO_FILE")
            return

        record_stage("download_sections", f"video={video_for_render}")

        # ── Step 6: Render clips (cut each from the downloaded video) ──
        set_status(f"Rendering {len(selected)} vertical shorts...", 85, "rendering")
        rendered_clips = []

        for idx, cand in enumerate(selected):
            set_status(
                f"Rendering clip {idx + 1}/{len(selected)}: '{cand.get('headline', 'Clip')}'...",
                int(85 + (idx / len(selected)) * 13),
                "rendering",
            )
            render_res = render_clip(
                source_video=video_for_render,
                start_time=cand["start"],
                end_time=cand["end"],
                words=words,
                headline=cand.get("headline", ""),
                layout=req.layout,
                subtitle_style=req.caption_style or req.subtitle_style,
            )
            if render_res.get("success"):
                render_res["score"] = cand.get("score", 90)
                render_res["reason"] = cand.get("reason", "Strong viral hook.")
                render_res["source_video"] = video_for_render
                render_res["clip_words"] = [
                    w for w in words
                    if w["end"] >= cand["start"] and w["start"] <= cand["end"]
                ]
                rendered_clips.append(render_res)
            else:
                pipeline_logger.error(f"[{task_id}] Render failed for clip {idx}: {render_res.get('error')}")

        tasks_state[task_id]["status"] = "completed"
        tasks_state[task_id]["progress"] = 100
        tasks_state[task_id]["message"] = f"Successfully generated {len(rendered_clips)} viral shorts!"
        tasks_state[task_id]["clips"] = rendered_clips

        # Cleanup temp audio
        if audio_path and Path(audio_path).exists():
            try:
                Path(audio_path).unlink(missing_ok=True)
            except Exception:
                pass

    except Exception as e:
        tb = traceback.format_exc()
        pipeline_logger.error(f"[{task_id}] PIPELINE_CRASH: {type(e).__name__}: {e}\n{tb}")
        tasks_state[task_id]["status"] = "failed"
        tasks_state[task_id]["error"] = f"{type(e).__name__}: {str(e)}"
        tasks_state[task_id]["message"] = "Pipeline crashed — check logs/pipeline.log for details."


# ── FastAPI HTTP Routes ──

@app.get("/")
def serve_index():
    """Serve the bundled frontend studio."""
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/process")
def process_video_endpoint(req: ProcessRequest, background_tasks: BackgroundTasks):
    """Start background video clipping pipeline."""
    task_id = str(uuid.uuid4())[:8]
    tasks_state[task_id] = {
        "task_id": task_id,
        "status": "processing",
        "progress": 0,
        "message": "Initializing pipeline...",
        "clips": [],
        "error": None,
        "heartbeat": time.time(),
    }
    _check_and_clear_orphan_tasks()
    background_tasks.add_task(run_processing_pipeline, task_id, req)
    return {"success": True, "task_id": task_id}


@app.post("/api/upload")
async def upload_file_endpoint(file: UploadFile = File(...)):
    """Upload a local video file directly into system."""
    contents = await file.read()
    result = save_uploaded_file(contents, file.filename)
    return result


@app.get("/api/status/{task_id}")
def get_task_status(task_id: str):
    """Poll pipeline processing status and generated clips."""
    state = tasks_state.get(task_id)
    if not state:
        raise HTTPException(status_code=404, detail="Task not found")
    # Include heartbeat age for stuck detection
    now = time.time()
    heartbeat_age = now - state.get("heartbeat", now)
    return {
        **state,
        "heartbeat_age": round(heartbeat_age, 1),
        "is_stuck": heartbeat_age > 60 and state.get("status") in ("running", "working", "processing"),
    }


@app.post("/api/edit")
def edit_clip_endpoint(req: EditRequest):
    """Adjust timestamps, captions, or layout and re-render."""
    res = adjust_and_reexport_clip(
        source_video=req.source_video,
        start_time=req.start_time,
        end_time=req.end_time,
        words=req.words or [],
        headline=req.headline,
        layout=req.layout,
        subtitle_style=req.subtitle_style,
        custom_text=req.custom_text or "",
    )
    return res


@app.get("/api/clips/download/{filename}")
def download_clip_endpoint(filename: str):
    """Stream or download a generated MP4 clip."""
    file_path = CLIPS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type="video/mp4", filename=filename)


@app.get("/api/clips/thumb/{filename}")
def get_clip_thumbnail(filename: str):
    """Serve a video thumbnail image."""
    file_path = CLIPS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return FileResponse(file_path, media_type="image/jpeg")


@app.get("/api/clips")
def list_clips():
    """List all previously generated clips."""
    files = list(CLIPS_DIR.glob("*.mp4"))
    clips = []
    for f in sorted(files, key=lambda p: p.stat().st_mtime, reverse=True):
        thumb_name = f"thumb_{f.stem.replace('clip_', '').split('_')[0]}.jpg"
        thumb_path = CLIPS_DIR / thumb_name
        clips.append({
            "filename": f.name,
            "filepath": str(f),
            "download_url": f"/api/clips/download/{f.name}",
            "thumbnail": f"/api/clips/thumb/{thumb_path.name}" if thumb_path.exists() else "",
        })
    return {"clips": clips}


# ── NEW: Create-screen endpoints ──

# ── Startup: Recover orphan tasks & start janitor ──

@app.on_event("startup")
async def startup_event():
    """On startup, recover orphan tasks and start the janitor."""
    import asyncio
    _check_and_clear_orphan_tasks()
    # Start background janitor (runs every 10s)
    asyncio.create_task(_janitor_loop())


async def _janitor_loop():
    """Background loop that checks for orphaned tasks every 10 seconds."""
    while True:
        await asyncio.sleep(10)
        _check_and_clear_orphan_tasks()


@app.get("/api/validate")
def validate_endpoint(url: str = ""):
    """Validate a YouTube URL and return title/duration when available."""
    if not url:
        raise HTTPException(status_code=400, detail="url is required")
    import re
    yt_re = re.compile(
        r"^(https?:\/\/)?(www\.|m\.)?(youtube\.com\/(watch\?v=|shorts\/|embed\/)|youtu\.be\/)[\w-]{6,}",
        re.IGNORECASE,
    )
    if not yt_re.match(url):
        return {"success": False, "error": "That does not look like a YouTube link."}
    try:
        cmd = [
            _ytdlp_bin(), "--no-playlist", "--skip-download", "--dump-json", url,
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        if proc.returncode == 0:
            import json as _json
            data = _json.loads(proc.stdout.decode("utf-8", errors="replace"))
            return {
                "success": True,
                "title": data.get("title", url),
                "duration": data.get("duration", 0),
                "thumbnail": data.get("thumbnail", ""),
            }
    except Exception:
        pass
    return {"success": True, "title": url, "duration": 0, "thumbnail": ""}


@app.get("/api/tasks")
def list_tasks_endpoint():
    """List all persisted tasks for the Library tab."""
    return {"tasks": list(tasks_state.values())}


@app.post("/api/tasks/cancel")
def cancel_task_endpoint(task_id: str):
    """Cancel a running task."""
    state = tasks_state.get(task_id)
    if not state:
        raise HTTPException(status_code=404, detail="Task not found")
    state["status"] = "cancelled"
    state["message"] = "Cancelled by user."
    return {"success": True}


@app.get("/api/videos/folder")
def videos_folder_endpoint(task_id: str = ""):
    """Return the output folder path for a task."""
    return {"path": str(OUTPUTS_DIR)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=3000, reload=True)