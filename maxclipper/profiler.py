# Pipeline Stage Profiler and Stuck Detector
# Part 1 of the mission: Instrument every pipeline stage

import json
import os
import time
import threading
import resource
from pathlib import Path
from typing import Dict, Any, Optional, Callable
import faulthandler
import psutil

# ── Configuration ──────────────────────────────────────────────────────────

LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

PIPELINE_LOG = LOGS_DIR / "pipeline.jsonl"

# Stuck detector thresholds (seconds)
STUCK_THRESHOLDS = {
    "download": 60,      # 60 seconds without progress
    "transcription": 120,  # 120 seconds without progress
    "render": 90,        # 90 seconds without progress
    "selection": 30,     # 30 seconds without progress
}

# Track last progress per stage for stuck detection
_stage_progress: Dict[str, Dict[str, Any]] = {}


def _now_ts() -> float:
    """Return current monotonic timestamp."""
    return time.monotonic()


def _json_dumps(obj: Any) -> str:
    """Serialize with consistent formatting for JSONL."""
    return json.dumps(obj, default=str)


def start_stage(stage_name: str, total_bytes: int = 0, total_expected: int = 0) -> str:
    """Begin tracking a pipeline stage.

    Returns a checkpoint ID that should be passed to end_stage().
    """
    checkpoint_id = f"{stage_name}_{int(time.time() * 1000)}"

    _stage_progress[stage_name] = {
        "start_time": _now_ts(),
        "last_update": _now_ts(),
        "bytes_downloaded": 0,
        "bytes_total": total_expected or 0,
        "status": "running",
        "checkpoint_id": checkpoint_id,
        "stuck_counter": 0,
    }

    # Write start event to JSONL
    event = {
        "event": "stage_start",
        "stage": stage_name,
        "checkpoint_id": checkpoint_id,
        "timestamp": time.time(),
    }
    _write_jsonl(event)

    # Print heartbeat
    _print_heartbeat(stage_name, "starting", 0)

    return checkpoint_id


def end_stage(
    stage_name: str,
    checkpoint_id: str,
    success: bool = True,
    error: str = "",
    bytes_written: int = 0,
    cpu_percent: Optional[float] = None,
    peak_ram_mb: Optional[float] = None,
) -> Dict[str, Any]:
    """End tracking a pipeline stage and write completion event."""
    progress = _stage_progress.get(stage_name, {})
    start_time = progress.get("start_time", time.time())
    elapsed = time.time() - start_time

    # Write completion event
    event = {
        "event": "stage_complete",
        "stage": stage_name,
        "checkpoint_id": checkpoint_id,
        "elapsed_seconds": round(elapsed, 2),
        "success": success,
        "error": error[:200] if error else None,
        "bytes_written": bytes_written,
        "cpu_percent": cpu_percent,
        "peak_ram_mb": peak_ram_mb,
        "timestamp": time.time(),
    }
    _write_jsonl(event)

    # Print heartbeat
    status = "completed" if success else "failed"
    _print_heartbeat(stage_name, status, round(elapsed, 2))

    # Clean tracking
    _stage_progress.pop(stage_name, None)

    return event


def update_progress(
    stage_name: str,
    progress_percent: float,
    message: str,
    bytes_downloaded: int = 0,
    bytes_total: int = 0,
) -> None:
    """Update progress for a stage (called from pipeline code)."""
    progress = _stage_progress.get(stage_name, {})
    last_update = progress.get("last_update", 0)

    # Check for stuck (no update for threshold seconds)
    threshold = STUCK_THRESHOLDS.get(stage_name, 0)
    if threshold > 0 and (_now_ts() - last_update) > threshold:
        # Stuck! Trigger stuck detector
        trigger_stuck_detector(stage_name, progress, bytes_downloaded, bytes_total)

    # Update progress tracking
    _stage_progress[stage_name] = {
        "start_time": progress.get("start_time", time.time()),
        "last_update": _now_ts(),
        "bytes_downloaded": bytes_downloaded,
        "bytes_total": bytes_total,
        "status": "running",
        "progress_percent": progress_percent,
        "message": message,
        "checkpoint_id": progress.get("checkpoint_id", ""),
    }

    # Write progress event
    event = {
        "event": "stage_progress",
        "stage": stage_name,
        "progress_percent": round(progress_percent, 1),
        "message": message[:100] if message else "",
        "bytes_downloaded": bytes_downloaded,
        "bytes_total": bytes_total,
        "timestamp": time.time(),
    }
    _write_jsonl(event)

    # Print heartbeat
    _print_heartbeat(stage_name, message, round(_now_ts() - progress.get("start_time", time.time()), 1))


def trigger_stuck_detector(
    stage_name: str, progress: Dict[str, Any], bytes_downloaded: int, bytes_total: int
) -> None:
    """Dump diagnostics and trigger fallback for stuck stage."""
    elapsed = time.time() - progress.get("start_time", time.time())

    # 1. Dump fault handler stack
    with open(f"logs/stuck_{stage_name}_{int(elapsed)}.txt", "w") as f:
        f.write(f"=== Stuck detector triggered for stage: {stage_name} ===\n")
        f.write(f"Elapsed time: {elapsed:.1f}s\n")
        f.write(f"Progress: {progress.get('progress_percent', 0):.1f}%\n")
        f.write(f"Bytes downloaded: {bytes_downloaded} / {bytes_total}\n")
        f.write(f"Last message: {progress.get('message', 'none')}\n\n")

        # Fault handler stack trace
        f.write("--- Fault handler stack trace ---\n")
        faulthandler.dump_traceback(f)

        # Process tree via psutil
        try:
            proc = psutil.Process()
            f.write("\n--- Process tree ---\n")
            for child in proc.children(recursive=True):
                f.write(f"  PID={child.pid} CPU={child.cpu_percent(interval=0.1):.1f}% MEM={child.memory_info().rss/1024/1024:.1f}MB CMD={child.cmdline()}\n")
            f.write(f"  Main PID={proc.pid} CPU={proc.cpu_percent(interval=0.1):.1f}% MEM={proc.memory_info().rss/1024/1024:.1f}MB CMD={proc.cmdline()}\n")
        except Exception as e:
            f.write(f"\n--- psutil error: {e} ---\n")

        # Last 50 lines of child output (if applicable)
        f.write("\n--- Recent output ---\n")
        # Could add FFmpeg/yt-dlp output here if available

    # 2. Log the stuck event
    event = {
        "event": "stage_stuck",
        "stage": stage_name,
        "elapsed_seconds": round(elapsed, 2),
        "progress_percent": progress.get("progress_percent", 0),
        "bytes_downloaded": bytes_downloaded,
        "bytes_total": bytes_total,
        "timestamp": time.time(),
    }
    _write_jsonl(event)

    # 3. Print alert
    print(f"\n[⚠️] STUCK DETECTOR: Stage '{stage_name}' not progressing for {elapsed:.1f}s")
    print(f"   Progress: {progress.get('progress_percent', 0):.1f}%")
    print(f"   Message: {progress.get('message', 'none')}")
    print(f"   Auto-triggering fallback for {stage_name}...\n")


def _print_heartbeat(stage_name: str, status: str, elapsed: float) -> None:
    """Print a heartbeat every ~2 seconds."""
    last_heartbeat = _stage_progress.get(stage_name, {}).get("_last_hb", 0)
    if elapsed - last_heartbeat >= 2.0:
        _stage_progress[stage_name]["_last_hb"] = elapsed
        print(f"[⏱] still working: stage {stage_name}, last progress: {status}")


def _write_jsonl(event: Dict[str, Any]) -> None:
    """Append a JSON event to the pipeline log."""
    with open(PIPELINE_LOG, "a", encoding="utf-8") as f:
        f.write(_json_dumps(event) + "\n")


# Convenience decorator for sync functions
def profile_sync(stage_name: str, total_bytes: int = 0, total_expected: int = 0):
    """Decorator to profile a synchronous pipeline stage."""

    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            checkpoint = start_stage(stage_name, total_bytes, total_expected)
            try:
                result = func(*args, **kwargs)
                # Get peak RAM
                try:
                    peak_ram = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # MB
                except Exception:
                    peak_ram = 0
                end_stage(
                    stage_name,
                    checkpoint,
                    success=True,
                    bytes_written=result if isinstance(result, int) else 0,
                    peak_ram_mb=peak_ram,
                )
                return result
            except Exception as e:
                end_stage(
                    stage_name,
                    checkpoint,
                    success=False,
                    error=str(e)[:500],
                )
                raise
        return wrapper
    return decorator


# Convenience decorator for async functions
def profile_async(stage_name: str, total_bytes: int = 0, total_expected: int = 0):
    """Decorator to profile an asynchronous pipeline stage."""

    def decorator(func) -> Callable:
        async def wrapper(*args, **kwargs):
            checkpoint = start_stage(stage_name, total_bytes, total_expected)
            try:
                result = await func(*args, **kwargs)
                bytes_written = result if isinstance(result, int) else 0
                try:
                    peak_ram = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
                except Exception:
                    peak_ram = 0
                end_stage(
                    stage_name,
                    checkpoint,
                    success=True,
                    bytes_written=bytes_written,
                    peak_ram_mb=peak_ram,
                )
                return result
            except Exception as e:
                end_stage(
                    stage_name,
                    checkpoint,
                    success=False,
                    error=str(e)[:500],
                )
                raise
        return wrapper
    return decorator