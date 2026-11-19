import os
import uuid
import threading
import traceback
import asyncio
import logging
import time
from typing import Dict, Any, Optional, List
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
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
    """Locate the yt-dlp executable, falling back to the current venv's bin dir."""
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

async def _fetch_metadata_and_captions(url: str) -> Dict[str, Any]:
    """Fetch metadata + caption tracks without downloading the video."""
    import json
    try:
        cmd = [
            _ytdlp_bin(), "--no-playlist", "--skip-download", "--dump-json", url,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        if proc.returncode != 0:
            raise Exception(f"yt-dlp failed: {stderr.decode('utf-8', errors='replace')}")
        data = json.loads(stdout.decode("utf-8", errors="replace"))
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
    yt_bin = _ytdlp_bin()
    audio_path = str(DOWNLOADS_DIR / f"audio_{uuid.uuid4().hex[:8]}.wav")
    # Use a simple format: best audio, then ffmpeg converts to wav
    cmd = [
        yt_bin,
        "-o", audio_path,
        "--format", "bestaudio/best",
        "--quiet", "--no-warnings", "--noplaylist",
        "--retries", "3", "--fragment-retries", "3",
        "--socket-timeout", "30",
        "--extract-audio",
        "--audio-format", "wav",
        "--audio-quality", "192",
        url,
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=180)
        if proc.returncode == 0 and Path(audio_path).exists():
            return audio_path
        err = stderr.decode("utf-8", errors="replace")[:500] if stderr else "Unknown error"
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
    """Download ONLY chosen video sections via yt-dlp --download-sections."""
    ranges = [f"{s['start']}:{s['end']}" for s in sections if s.get("end", 0) > s.get("start", 0)]
    if not ranges:
        return {"success": False, "error": "No valid sections specified"}
    yt_bin = _ytdlp_bin()
    cmd = [
        yt_bin,
        "-o", output_path,
        "--format", f"best[height<={target_height}]/best",
        "--download-ranges", ",".join(ranges),
        "--quiet", "--no-warnings", "--noplaylist",
        "--retries", "3", "--fragment-retries", "3",
        "--socket-timeout", "30",
        url,
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await asyncio.wait_for(proc.communicate(), timeout=300)
        if proc.returncode == 0 and Path(output_path).exists():
            file_size = Path(output_path).stat().st_size
            return {"success": True, "filepath": str(output_path), "file_size_mb": round(file_size / 1e6, 2)}
        err = proc.stderr.decode("utf-8", errors="replace")[:500] if proc.stderr else "Unknown error"
        return {"success": False, "error": f"yt-dlp sections download failed: {err}"}
    except Exception as e:
        pipeline_logger.error(f"Sections download error: {e}")
        return {"success": False, "error": str(e)}


def _run_async(coro):
    """Run an async coroutine from a sync background-task thread."""
    try:
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Pipeline worker ──

def run_processing_pipeline(task_id: str, req: ProcessRequest):
    """Background worker executing the complete pipeline with structured logging."""
    start_time = time.time()

    def set_status(msg: str, progress: int, stage: str = "processing"):
        tasks_state[task_id]["message"] = msg
        tasks_state[task_id]["progress"] = progress
        tasks_state[task_id]["stage"] = stage
        pipeline_logger.info(f"[{task_id}] [{stage}] p={progress}% | {msg}")

    def record_stage(stage_name: str, details: str = ""):
        elapsed = time.time() - start_time
        pipeline_logger.info(
            f"[{task_id}] STAGE_COMPLETE: {stage_name} in {elapsed:.2f}s | {details}"
        )

    # ── NEW: Profiler integration ──
    profiler_stages = {
        "metadata": {"total_expected": 0},
        "audio_download": {"total_expected": 0},
        "transcribe": {"total_expected": 0},
        "selection": {"total_expected": 0},
        "download_sections": {"total_expected": 0},
        "render": {"total_expected": 0},
    }
    stage_checkpoints = {}

    try:
        # ── Step 1: Metadata (tiny, no download) ──
        stage_ckpt = start_stage("metadata", **profiler_stages["metadata"])
        stage_checkpoints["metadata"] = stage_ckpt
        if req.url:
            set_status("Fetching video metadata and captions...", 5, "ingesting")
            meta_res = _run_async(_fetch_metadata_and_captions(req.url))
            if not meta_res.get("success"):
                tasks_state[task_id]["status"] = "failed"
                tasks_state[task_id]["error"] = meta_res.get("error", "Metadata fetch failed")
                pipeline_logger.error(f"[{task_id}] META_FAILED")
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
            tasks_state[task_id]["status"] = "failed"
            tasks_state[task_id]["error"] = "No valid URL or video file provided."
            pipeline_logger.error(f"[{task_id}] NO_INPUT")
            return

        source_video = video_meta.get("filepath", "")
        tasks_state[task_id]["video_info"] = video_meta
        record_stage("ingest", f"title={video_meta.get('title')}")

        # ── Step 2: Audio-only download (fast, ~2 MB for a 3-min video) ──
        stage_ckpt = start_stage("audio_download", **profiler_stages["audio_download"])
        stage_checkpoints["audio_download"] = stage_ckpt
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
            cmd = ["ffmpeg", "-y", "-i", source_video, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", "-loglevel", "error", audio_path]
            subprocess.run(cmd, check=False, capture_output=True)
            if not Path(audio_path).exists():
                audio_path = ""

        if audio_path and Path(audio_path).exists():
            # Update progress bytes for download stage
            set_status("Audio downloaded successfully", 20, "analyzing")
            try:
                file_size = Path(audio_path).stat().st_size
                update_progress("audio_download", 95, "Audio ready", bytes_downloaded=file_size, bytes_total=file_size)
            except:
                pass
        else:
            pipeline_logger.warning(f"[{task_id}] Audio download failed – proceeding with captions only")

        # ── Step 3: Transcribe with word timing ──
        stage_ckpt = start_stage("transcribe", **profiler_stages["transcribe"])
        stage_checkpoints["transcribe"] = stage_ckpt
        # Primary source: YouTube captions (word timing, free, fast).
        # Fallback: offline faster-whisper on the downloaded low-bitrate audio.
        trans_res = None
        if req.url:
            set_status("Reading YouTube captions...", 22, "transcribing")
            from app.youtube_captions import fetch_youtube_captions
            cap_res = fetch_youtube_captions(
                req.url,
                progress_callback=lambda m, p: set_status(m, 22 + int(p / 10), "transcribing"),
            )
            if cap_res.get("success") and cap_res.get("words"):
                trans_res = cap_res
                set_status(f"Captions loaded: {len(cap_res['words'])} words", 30, "transcribing")
            else:
                pipeline_logger.warning(f"[{task_id}] Caption fetch failed: {cap_res.get('error')} — falling back to offline STT")

        if trans_res is None:
            # Fallback: offline STT on downloaded audio (or local file)
            set_status("Transcribing with offline speech model...", 25, "transcribing")
            trans_input = audio_path if (audio_path and Path(audio_path).exists()) else (source_video if source_video else req.filepath)
            if not trans_input or not os.path.exists(trans_input):
                tasks_state[task_id]["status"] = "failed"
                tasks_state[task_id]["error"] = "Could not read YouTube captions and no audio is available for offline transcription. Try again or upload the video locally."
                pipeline_logger.error(f"[{task_id}] NO_TRANSCRIPT_SOURCE")
                return
            trans_res = transcribe_audio(
                trans_input,
                progress_callback=lambda m, p: update_progress("transcribe", 25 + int(p / 4), "transcribing", bytes_downloaded=0, bytes_total=0),
            )
        if not trans_res.get("success") or not trans_res.get("words"):
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
        stage_ckpt = start_stage("selection", **profiler_stages["selection"])
        stage_checkpoints["selection"] = stage_ckpt
        set_status("Analyzing hooks, speech pacing & retention scores...", 55, "analyzing")
        clips_candidates = detect_viral_clips(
            trans_res,
            method=req.ai_method,
            api_key=req.api_key or "",
            progress_callback=lambda m, p: set_status(m, p, "analyzing"),
        )
        end_stage("selection", stage_ckpt, success=bool(clips_candidates),
                  error="No clips found" if not clips_candidates else "",
                  cpu_percent=None, peak_ram_mb=None)

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

        # ── Step 5: Download ONLY chosen sections ──
        stage_ckpt = start_stage("download_sections", **profiler_stages["download_sections"])
        stage_checkpoints["download_sections"] = stage_ckpt
        set_status(f"Downloading {min(len(clips_candidates), req.max_clips)} selected sections...", 70, "downloading")
        selected = clips_candidates[: req.max_clips]
        downloaded_sections: List[Dict[str, Any]] = []

        for idx, cand in enumerate(selected):
            target_h = 480 if req.measured_speed_mbps < 0.5 else 720
            section_path = str(CLIPS_DIR / f"section_{task_id}_{idx}_{int(cand['start'])}to{int(cand['end'])}.mp4")
            dl_res = _run_async(_download_sections(
                req.url,
                [{"start": cand["start"], "end": cand["end"]}],
                section_path,
                target_height=target_h,
            ))
            if dl_res.get("success"):
                downloaded_sections.append({"clip_info": cand, "filepath": dl_res["filepath"]})
            else:
                pipeline_logger.warning(f"[{task_id}] Section {idx} download failed: {dl_res.get('error')}")

        if not downloaded_sections:
            tasks_state[task_id]["status"] = "failed"
            tasks_state[task_id]["error"] = "Failed to download any selected video sections."
            pipeline_logger.error(f"[{task_id}] SECTION_DOWNLOAD_FAILED")
            return

        # Get bytes written from the downloaded sections
        total_bytes_written = 0
        for ds in downloaded_sections:
            fp = Path(ds.get("filepath", ""))
            if fp.exists():
                total_bytes_written += fp.stat().st_size
        update_progress("download_sections", 90, f"{len(downloaded_sections)} sections ready", bytes_downloaded=total_bytes_written, bytes_total=total_bytes_written)

        record_stage("download_sections", f"sections={len(downloaded_sections)}")

        # ── Step 6: Render clips ──
        set_status(f"Rendering {len(downloaded_sections)} vertical shorts...", 85, "rendering")
        rendered_clips = []

        for idx, section in enumerate(downloaded_sections):
            cand = section["clip_info"]
            filepath = section["filepath"]
            set_status(
                f"Rendering clip {idx + 1}/{len(downloaded_sections)}: '{cand.get('headline', 'Clip')}'...",
                int(85 + (idx / len(downloaded_sections)) * 13),
                "rendering",
            )
            render_res = render_clip(
                source_video=filepath,
                start_time=cand["start"],
                end_time=cand["end"],
                words=words,
                headline=cand.get("headline", ""),
                layout=req.layout,
                subtitle_style=req.subtitle_style,
            )
            if render_res.get("success"):
                render_res["score"] = cand.get("score", 90)
                render_res["reason"] = cand.get("reason", "Strong viral hook.")
                render_res["source_video"] = source_video
                render_res["clip_words"] = [
                    w for w in words
                    if w["end"] >= cand["start"] and w["start"] <= cand["end"]
                ]
                # End render stage profiling
                try:
                    peak_ram = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
                except:
                    peak_ram = 0
                end_stage("render", stage_checkpoints.get("render", ""),
                          success=render_res.get("success"),
                          error=render_res.get("error", "")[:200],
                          bytes_written=int(Path(render_res.get("filepath", "")).stat().st_size) if render_res.get("success") and Path(render_res.get("filepath", "")).exists() else 0,
                          cpu_percent=None, peak_ram_mb=peak_ram)
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
    """Serve the bundled frontend."""
    return HTMLResponse(content=(STATIC_DIR / "index.html").read_text(encoding="utf-8"), media_type="text/html")


@app.post("/api/process")
def process_video_endpoint(req: ProcessRequest, background_tasks: BackgroundTasks):
    """Start background video clipping pipeline."""
    task_id = str(uuid.uuid4())[:8]
    tasks_state[task_id] = {
        "status": "processing",
        "progress": 0,
        "message": "Initializing pipeline...",
        "clips": [],
        "error": None,
    }
    background_tasks.add_task(run_processing_pipeline, task_id, req)
    return {"success": True, "task_id": task_id}


@app.post("/api/upload")
async def upload_file_endpoint(file: UploadFile = File(...)):
    """Upload a local video file directly."""
    contents = await file.read()
    result = save_uploaded_file(contents, file.filename)
    return result


@app.get("/api/status/{task_id}")
def get_task_status(task_id: str):
    """Poll pipeline processing status and generated clips."""
    state = tasks_state.get(task_id)
    if not state:
        raise HTTPException(status_code=404, detail="Task not found")
    return state


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=3000, reload=True)
