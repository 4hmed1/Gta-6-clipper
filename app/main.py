import os
import uuid
import threading
import traceback
import asyncio
import logging
import time
from typing import Dict, Any, Optional
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
from clipforge.resilience import ErrorClassifier

# ── Structured logging ──
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
pipeline_logger = logging.getLogger("clipforge.pipeline")
pipeline_logger.setLevel(logging.INFO)
_fh = logging.FileHandler(LOGS_DIR / "pipeline.log")
_fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
pipeline_logger.addHandler(_fh)

app = FastAPI(
    title="ViralForge AI - Open Source AI Video Clipper",
    description="Turn long-form videos into viral vertical shorts with AI hook detection and kinetic subtitles.",
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
    ai_method: str = "heuristic"  # "heuristic", "gemini", "ollama"
    api_key: Optional[str] = ""
    subtitle_style: str = "hormozi"
    layout: str = "split_blur"
    min_duration: float = 20.0
    max_duration: float = 60.0
    max_clips: int = 5

class EditRequest(BaseModel):
    source_video: str
    start_time: float
    end_time: float
    headline: str
    layout: str = "split_blur"
    subtitle_style: str = "hormozi"
    custom_text: Optional[str] = ""
    words: Optional[list] = []

def run_processing_pipeline(task_id: str, req: ProcessRequest):
    """Background worker executing the complete pipeline with structured logging and resilience."""
    import shutil
    start_time = time.time()

    def set_status(msg: str, progress: int, stage: str = "processing"):
        tasks_state[task_id]["message"] = msg
        tasks_state[task_id]["progress"] = progress
        tasks_state[task_id]["stage"] = stage
        pipeline_logger.info(f"[{task_id}] [{stage}] p={progress}% | {msg}")

    def record_stage(stage_name: str, elapsed: float, details: str = ""):
        elapsed = time.time() - start_time if start_time else elapsed
        pipeline_logger.info(
            f"[{task_id}] STAGE_COMPLETE: {stage_name} in {elapsed:.2f}s | {details}"
        )

    error_classifier = ErrorClassifier()

    try:
        # ── Step 1: Video Metadata & Captions (TINY download, NO full video) ──
        if req.url:
            set_status("Fetching video metadata and captions...", 5, "ingesting")
            meta_res = asyncio.create_task(_fetch_metadata_and_captions(req.url))
            # Run with timeout
            import concurrent.futures
            try:
                meta_res = concurrent.futures.ThreadPoolExecutor().submit(
                    lambda: asyncio.get_event_loop().run_until_complete(_fetch_metadata_and_captions(req.url))
                ).result(timeout=30)
            except Exception:
                tasks_state[task_id]["status"] = "failed"
                tasks_state[task_id]["error"] = "Metadata fetch timed out"
                pipeline_logger.error(f"[{task_id}] META_TIMEOUT")
                return
            
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
        record_stage("ingest", time.time(), f"title={video_meta.get('title')}")

        # ── Step 2: Low-bitrate Audio Analysis ──
        set_status("Downloading low-bitrate audio for analysis...", 15, "analyzing")
        audio_path = asyncio.create_task(_download_audio_only(source_video))
        try:
            audio_path = asyncio.get_event_loop().run_until_complete(audio_path)
        except Exception:
            audio_path = ""
        
        if audio_path and Path(audio_path).exists():
            set_status("Audio downloaded successfully", 20, "analyzing")
        else:
            pipeline_logger.warning(f"[{task_id}] Audio download failed, proceeding with captions")

        # ── Step 3: Transcribe with word timing ──
        set_status("Extracting word-level timestamps...", 25, "transcribing")
        trans_res = transcribe_audio(
            source_video if source_video else req.filepath,
            progress_callback=lambda m, p: set_status(m, p, "transcribing")
        )
        if not trans_res.get("success"):
            tasks_state[task_id]["status"] = "failed"
            tasks_state[task_id]["error"] = "Transcription failed."
            pipeline_logger.error(f"[{task_id}] TRANSCRIBE_FAILED")
            return

        # Convert numpy types in words to plain Python floats
        words = trans_res.get("words", [])
        for w in words:
            if isinstance(w.get("start"), (float,)):
                w["start"] = float(w["start"])
            if isinstance(w.get("end"), (float,)):
                w["end"] = float(w["end"])
        trans_res["words"] = words

        tasks_state[task_id]["transcript_words"] = words
        record_stage("transcribe", time.time(), f"words={len(words)},is_mock={trans_res.get('is_mock', False)}")

        # ── Step 4: Clip Selection ───────────────────────────────
        set_status("Analyzing hooks, speech pacing & retention scores...", 55, "analyzing")
        clips_candidates = detect_viral_clips(
            trans_res,
            method=req.ai_method,
            api_key=req.api_key or "",
            progress_callback=lambda m, p: set_status(m, p, "analyzing")
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

        record_stage("select", time.time(), f"candidates={len(clips_candidates)}")

        # ── Step 5: Download ONLY chosen sections ──
        set_status(f"Downloading {min(len(clips_candidates), req.max_clips)} selected sections...", 70, "downloading")
        selected = clips_candidates[:req.max_clips]
        downloaded_sections = []

        for idx, cand in enumerate(selected):
            target_h = 480 if req.measured_speed_mbps < 0.5 else 720
            section_path = str(CLIPS_DIR / f"section_{task_id}_{idx}_{int(cand['start'])}to{int(cand['end'])}.mp4")
            dl_res = asyncio.create_task(_download_sections(
                req.url,
                [{"start": cand["start"], "end": cand["end"]}],
                section_path,
                target_height=target_h
            ))
            try:
                dl_res = asyncio.get_event_loop().run_until_complete(dl_res)
            except Exception:
                dl_res = {"success": False, "error": "Section download timed out"}
            
            if dl_res.get("success"):
                downloaded_sections.append({
                    "clip_info": cand,
                    "filepath": dl_res["filepath"],
                })
            else:
                pipeline_logger.warning(f"[{task_id}] Section {idx} download failed: {dl_res.get('error')}")

        if not downloaded_sections:
            tasks_state[task_id]["status"] = "failed"
            tasks_state[task_id]["error"] = "Failed to download any selected video sections."
            pipeline_logger.error(f"[{task_id}] SECTION_DOWNLOAD_FAILED")
            return

        record_stage("download_sections", time.time(), f"sections={len(downloaded_sections)}")

        # ── Step 6: Render Vertical Clips ──
        set_status(f"Rendering {len(downloaded_selections)} vertical shorts...", 85, "rendering")
        rendered_clips = []

        for idx, section in enumerate(downloaded_selections):
            cand = section["clip_info"]
            filepath = section["filepath"]

            set_status(
                f"Rendering clip {idx+1}/{len(downloaded_selections)}: '{cand.get('headline', 'Clip')}'...",
                int(85 + (idx / len(downloaded_selections)) * 13),
                "rendering"
            )
            render_res = render_clip(
                source_video=filepath,
                start_time=cand["start"],
                end_time=cand["end"],
                words=words,
                headline=cand.get("headline", ""),
                layout=req.layout,
                subtitle_style=req.subtitle_style
            )
            if render_res.get("success"):
                render_res["score"] = cand.get("score", 90)
                render_res["reason"] = cand.get("reason", "Strong viral hook.")
                render_res["source_video"] = source_video
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

        # Cleanup temp files
        if audio_path and Path(audio_path).exists() if isinstance(audio_path, str) else False:
            try:
                # audio_path is a task result, not a direct path - skip cleanup for now
                pass
            except:
                pass

    except Exception as e:
        tb = traceback.format_exc()
        pipeline_logger.error(f"[{task_id}] PIPELINE_CRASH: {type(e).__name__}: {e}\n{tb}")
        tasks_state[task_id]["status"] = "failed"
        tasks_state[task_id]["error"] = f"{type(e).__name__}: {str(e)}"
        tasks_state[task_id]["message"] = "Pipeline crashed — check logs/pipeline.log for details."

    # ── Helper async functions ──

    async def _fetch_metadata_and_captions(url: str) -> Dict[str, Any]:
        """Fetch metadata + caption tracks from YouTube without downloading video."""
        import json
        try:
            cmd = [
                "yt-dlp",
                "--no-playlist",
                "--skip-download",
                "--dump-json",
                url,
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            if proc.returncode != 0:
                raise Exception(f"yt-dlp failed: {stderr.decode('utf-8', errors='replace')}")
            data = json.loads(stdout.decode("utf-8", errors="replace"))
            
            # Extract caption tracks
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
            pipeline_logger.error(f"[{task_id}] Metadata fetch error: {e}")
            return {"success": False, "error": str(e)}

    async def _download_audio_only(source_video: str) -> str:
        """Download low-bitrate audio (64 kbps) for analysis only."""
        if not source_video or not Path(source_video).exists():
            return ""
        
        audio_path = str(Path(source_video).with_suffix(".wav"))
        ydl_opts = {
            "format": "bestaudio[abr<=64]/worstaudio",
            "skip_download": False,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "retries": 3,
            "fragment_retries": 3,
            "socket_timeout": 30,
            "outtmpl": audio_path,
        }
        
        try:
            cmd = [
                "yt-dlp",
                "-o", ydl_opts["outtmpl"],
                "--format", ydl_opts["format"],
                "--quiet", "--no-warnings", "--noplaylist",
                "--retries", "3", "--fragment-retries", "3",
                "--socket-timeout", "30",
                source_video,
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await asyncio.wait_for(proc.communicate(), timeout=120)
            
            if proc.returncode == 0 and Path(audio_path).exists():
                return audio_path
            else:
                try:
                    Path(audio_path).unlink(missing_ok=True)
                except:
                    pass
                return ""
        except Exception as e:
            pipeline_logger.error(f"[{task_id}] Audio download error: {e}")
            return ""

    async def _download_sections(
        url: str,
        sections: List[Dict[str, float]],
        output_path: str,
        target_height: int = 720,
    ) -> Dict[str, Any]:
        """Download ONLY chosen video sections via yt-dlp --download-sections."""
        # Build download-ranges argument
        ranges = []
        for s in sections:
            start = s.get("start", 0)
            end = s.get("end", 0)
            if start >= 0 and end > start:
                ranges.append(f"{start}:{end}")
        
        if not ranges:
            return {"success": False, "error": "No valid sections specified"}
        
        ydl_opts = {
            "format": f"best[height<={target_height}]/best",
            "skip_download": False,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "retries": 3,
            "fragment_retries": 3,
            "http_chunk_size": 10485760,
            "socket_timeout": 30,
            "geo_bypass": True,
        }
        
        download_arg = f"--download-ranges {','.join(ranges)}" if ranges else ""
        
        try:
            cmd = [
                "yt-dlp",
                "-o", output_path,
                "--format", ydl_opts["format"],
                download_arg,
                "--quiet", "--no-warnings", "--noplaylist",
                "--retries", "3", "--fragment-retries", "3",
                "--socket-timeout", "30",
                "--geo-bypass",
                url,
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await asyncio.wait_for(proc.communicate(), timeout=300)
            
            if proc.returncode == 0 and Path(output_path).exists():
                file_size = Path(output_path).stat().st_size
                return {
                    "success": True,
                    "filepath": str(output_path),
                    "file_size_mb": round(file_size / 1e6, 2),
                }
            else:
                err = proc.stderr.decode("utf-8", errors="replace")[:500] if proc.stderr else "Unknown error"
                return {"success": False, "error": f"yt-dlp sections download failed: {err}"}
        except Exception as e:
            pipeline_logger.error(f"[{task_id}] Sections download error: {e}")
            return {"success": False, "error": str(e)}