import os
import uuid
import threading
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
    """Background worker executing the complete pipeline."""
    try:
        def set_status(msg: str, progress: int, stage: str = "processing"):
            tasks_state[task_id]["message"] = msg
            tasks_state[task_id]["progress"] = progress
            tasks_state[task_id]["stage"] = stage

        # Step 1: Video Ingestion
        video_info = None
        if req.url:
            set_status("Connecting to video source and extracting metadata...", 10, "downloading")
            res = download_youtube_video(req.url, lambda m, p: set_status(m, p, "downloading"))
            if not res.get("success"):
                tasks_state[task_id]["status"] = "failed"
                tasks_state[task_id]["error"] = res.get("error", "Download failed")
                return
            video_info = res
            set_status(f"Video downloaded: {video_info.get('title','Video')} ({video_info.get('duration',0)}s)", 20, "downloading")
        elif req.filepath and os.path.exists(req.filepath):
            set_status("Loading local video file...", 20, "loading")
            video_info = {
                "filepath": req.filepath,
                "title": Path(req.filepath).stem,
                "duration": 0
            }
        else:
            tasks_state[task_id]["status"] = "failed"
            tasks_state[task_id]["error"] = "No valid URL or video file provided."
            return

        source_video = video_info["filepath"]
        tasks_state[task_id]["video_info"] = video_info

        # Step 2: Speech AI & Word Timestamp Extraction
        set_status("Transcribing speech with AI word-level timestamps...", 35, "transcribing")
        trans_res = transcribe_audio(
            source_video, 
            progress_callback=lambda m, p: set_status(m, p, "transcribing")
        )
        if not trans_res.get("success"):
            tasks_state[task_id]["status"] = "failed"
            tasks_state[task_id]["error"] = "Transcription failed."
            return

        tasks_state[task_id]["transcript"] = trans_res

        # Step 3: AI Viral Hook Detection & Scoring
        set_status("Analyzing retention curves, hooks & virality scores...", 65, "analyzing")
        clips_candidates = detect_viral_clips(
            trans_res,
            method=req.ai_method,
            api_key=req.api_key or "",
            progress_callback=lambda m, p: set_status(m, p, "analyzing")
        )

        if not clips_candidates:
            tasks_state[task_id]["status"] = "failed"
            tasks_state[task_id]["error"] = "No viral clips could be identified."
            return

        # Step 4: Render Vertical Clips & Kinetic Subtitles
        set_status(f"Synthesizing {len(clips_candidates)} viral vertical shorts...", 80, "rendering")
        rendered_clips = []
        all_words = trans_res.get("words", [])

        for idx, cand in enumerate(clips_candidates[:req.max_clips]):
            set_status(
                f"Rendering clip {idx+1}/{len(clips_candidates)}: '{cand.get('headline', 'Clip')}'...",
                int(80 + (idx / len(clips_candidates)) * 18),
                "rendering"
            )
            render_res = render_clip(
                source_video=source_video,
                start_time=cand["start"],
                end_time=cand["end"],
                words=all_words,
                headline=cand.get("headline", ""),
                layout=req.layout,
                subtitle_style=req.subtitle_style
            )
            if render_res.get("success"):
                render_res["score"] = cand.get("score", 90)
                render_res["reason"] = cand.get("reason", "Strong viral hook.")
                render_res["source_video"] = source_video
                render_res["clip_words"] = [
                    w for w in all_words 
                    if w["end"] >= cand["start"] and w["start"] <= cand["end"]
                ]
                rendered_clips.append(render_res)

        tasks_state[task_id]["status"] = "completed"
        tasks_state[task_id]["progress"] = 100
        tasks_state[task_id]["message"] = f"Successfully generated {len(rendered_clips)} viral shorts!"
        tasks_state[task_id]["clips"] = rendered_clips

    except Exception as e:
        print(f"[Pipeline Worker] Unhandled exception: {e}")
        tasks_state[task_id]["status"] = "failed"
        tasks_state[task_id]["error"] = str(e)

@app.get("/")
def serve_index():
    """Serve modern dark-mode frontend studio."""
    return FileResponse(STATIC_DIR / "index.html")

@app.post("/api/process")
def process_video_endpoint(req: ProcessRequest, background_tasks: BackgroundTasks):
    """Start background video clipping pipeline."""
    task_id = str(uuid.uuid4())[:8]
    tasks_state[task_id] = {
        "status": "processing",
        "progress": 0,
        "message": "Initializing pipeline...",
        "clips": [],
        "error": None
    }
    background_tasks.add_task(run_processing_pipeline, task_id, req)
    return {"success": True, "task_id": task_id}

@app.post("/api/upload")
async def upload_file_endpoint(file: UploadFile = File(...)):
    """Upload local video file directly into system."""
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
        custom_text=req.custom_text or ""
    )
    return res

@app.get("/api/clips/download/{filename}")
def download_clip_endpoint(filename: str):
    """Stream or download generated MP4 clip."""
    file_path = CLIPS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type="video/mp4", filename=filename)

@app.get("/api/clips/thumb/{filename}")
def get_clip_thumbnail(filename: str):
    """Serve video thumbnail image."""
    file_path = CLIPS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return FileResponse(file_path, media_type="image/jpeg")

@app.get("/api/clips")
def list_clips():
    """List all previously generated clips."""
    files = list(CLIPS_DIR.glob("*.mp4"))
    clips = []
    for f in sorted(files, key=os.path.getmtime, reverse=True):
        thumb = CLIPS_DIR / f"thumb_{f.stem.replace('clip_', '').split('_')[0]}.jpg"
        clips.append({
            "filename": f.name,
            "filepath": str(f),
            "download_url": f"/api/clips/download/{f.name}",
            "thumbnail": f"/api/clips/thumb/{thumb.name}" if thumb.exists() else ""
        })
    return {"clips": clips}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=3000, reload=True)
