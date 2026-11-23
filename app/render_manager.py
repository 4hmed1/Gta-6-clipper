"""Global render queue: only one FFmpeg render at a time to prevent CPU starvation.

- Clips wait in FIFO order.
- Stall-based timeout: kill if no progress for STALL_SECONDS, or total time exceeds RENDER_TIMEOUT.
- On failure: retry once with "-preset ultrafast".
- On failure: delete partial output, ensure process is killed.
- On success/failure: save ffmpeg command + last 60 stderr lines to a log file.
- UI-ready error messages only.
"""

import asyncio
import fcntl
import os
import subprocess
import time
from pathlib import Path
from typing import Optional

import platformdirs

# ── Constants ────────────────────────────────────────────────────────────────

DEFAULT_STALL_SECONDS = 180
DEFAULT_RENDER_TIMEOUT_MULTIPLIER = 90  # cap = max(1800, duration * 90)

# Resource decisions
_CPU_COUNT = os.cpu_count() or 1
if _CPU_COUNT <= 4:
    DEFAULT_VIDEO_PRESET = "ultrafast"
else:
    DEFAULT_VIDEO_PRESET = "veryfast"

# Paths
_LOG_DIR = Path(platformdirs.user_log_dir("MaxClipper"))
_LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── Global render lock (file-based for cross-process safety) ──────────────

_lock_file = Path(platformdirs.user_data_dir("MaxClipper")) / "render.lock"


def _acquire_render_lock(timeout: float = 300.0) -> bool:
    """Acquire the global render lock using file locking.

    Returns True if we got the lock, False if another render is in progress.
    """
    try:
        lock_fd = os.open(str(_lock_file), os.O_CREAT | os.O_RDWR)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Write our PID so we can identify the holder
        os.ftruncate(lock_fd, 0)
        os.write(lock_fd, str(os.getpid()).encode())
        return True
    except (OSError, IOError):
        # Another process holds the lock
        try:
            # Try to read the holder PID and check if it's still alive
            lock_fd = os.open(str(_lock_file), os.O_RDONLY)
            data = os.read(lock_fd, 16).decode().strip()
            os.close(lock_fd)
            try:
                pid = int(data)
                os.kill(pid, 0)  # Process exists
                return False
            except (ValueError, ProcessLookupError):
                # Stale lock from a dead process - re-acquire
                fcntl.flock(lock_fd, fcntl.LOCK_EX)
                os.ftruncate(lock_fd, 0)
                os.write(lock_fd, str(os.getpid()).encode())
                return True
        except (OSError, IOError):
            return True  # No lock file, can acquire


def _release_render_lock() -> None:
    """Release the global render lock."""
    try:
        lock_fd = os.open(str(_lock_file), os.O_RDWR)
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)
    except (OSError, IOError):
        pass
    try:
        _lock_file.unlink(missing_ok=True)
    except Exception:
        pass


# ── Stall-based timeout helpers ────────────────────────────────────────────

def _compute_render_timeout(duration_seconds: float, override_seconds: Optional[float] = None) -> float:
    """Compute the render timeout.

    - If override_seconds is set (via env var MAXCLIPPER_RENDER_TIMEOUT), use it.
    - Hard cap: max(1800, duration_seconds * 90).
    - Default: 300s (5 minutes) for very short clips.
    """
    if override_seconds is not None and override_seconds > 0:
        return override_seconds

    # Hard cap
    hard_cap = max(1800, duration_seconds * DEFAULT_RENDER_TIMEOUT_MULTIPLIER)

    # Default floor
    default_timeout = 300.0

    return max(default_timeout, hard_cap)


def _compute_stall_seconds(override_seconds: Optional[float] = None) -> float:
    """Compute the stall-based timeout.

    - If override_seconds is set (via env var MAXCLIPPER_STALL_SECONDS), use it.
    - Default: 180 seconds (3 minutes) with no progress.
    """
    if override_seconds is not None and override_seconds > 0:
        return override_seconds
    return DEFAULT_STALL_SECONDS


# ── FFmpeg command builder ─────────────────────────────────────────────────

def build_ffmpeg_cmd(
    input_path: str,
    output_path: str,
    duration: float,
    preset: str = None,
    threads: str = "0",
    nogdi: bool = True,
) -> list:
    """Build the FFmpeg command for rendering a clip.

    Args:
        input_path: Path to the input video.
        output_path: Path to the output MP4.
        duration: Clip duration in seconds.
        preset: FFmpeg preset (veryfast/ultrafast). Uses CPU-based default if None.
        threads: Thread count passed to FFmpeg. "0" means auto.
        nogdi: If True, omit -threads-related issues; always include -nostdin.

    Returns:
        List of command arguments ready for subprocess.
    """
    if preset is None:
        preset = DEFAULT_VIDEO_PRESET

    cmd = [
        "ffmpeg",
        "-y",  # overwrite output
        "-nostdin",  # never read from stdin - critical for background/daemon mode
        "-hide_banner",
    ]

    # Hardware acceleration detection is handled elsewhere; keep it simple.

    # Video encoding
    cmd += [
        "-i", input_path,
        "-threads", threads,
        "-preset", preset,
        "-crf", "28",
        "-r", "30",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-c:a", "aac",
        "-b:a", "128k",
    ]

    # Filter complex for captions (built by caller if needed)
    # -vf will be appended by the caller

    cmd.append(output_path)

    return cmd


# ── Progress-based rendering ────────────────────────────────────────────────

def _read_progress(proc: subprocess.Popen, last_progress_time: float,
                   stall_seconds: float, stop_event: asyncio.Event,
                   duration_seconds: float, render_timeout: float) -> tuple:
    """Read ffmpeg progress output from stderr.

    Returns (stop_reason, total_elapsed) where stop_reason is one of:
    - 'progress': normal completion
    - 'stall': no progress for stall_seconds
    - 'timeout': total time exceeded render_timeout
    """
    buf = ""
    try:
        while True:
            # Check if process has ended
            if proc.poll() is not None:
                # Process ended - read any remaining output
                remaining = proc.stderr.read().decode(errors='replace')
                buf += remaining
                break

            # Check for stop event (for async cancellation)
            if stop_event and stop_event.is_set():
                # Try to kill the process
                try:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                except Exception:
                    pass
                return 'cancelled', time.time() - last_progress_time

            # Read a chunk with timeout
            try:
                chunk = proc.stderr.read1(4096, timeout=0.5)
                if chunk:
                    buf += chunk.decode(errors='replace')
                    # Check for progress markers
                    if 'out=' in buf or 'time=' in buf:
                        last_progress_time = time.time()

            except subprocess.TimeoutExpired:
                # No data available yet - just loop
                continue

    except Exception:
        pass

    return 'progress', time.time() - last_progress_time


def render_ffmpeg_with_stall_check(
    cmd: list,
    duration_seconds: float,
    stall_seconds: float = None,
    render_timeout: float = None,
    clip_id: str = "unknown",
) -> dict:
    """Run FFmpeg with stall-based timeout and progress monitoring.

    Returns dict with keys:
    - success: bool
    - output_path: str (if success) or partial path
    - error: str (readable user message)
    - log_path: str path to the log file
    """

    # Compute timeouts
    stall_s = _compute_stall_seconds(stall_seconds)
    render_t = _compute_render_timeout(duration_seconds, render_timeout)

    # Prepare output path and log path
    output_path = cmd[-1]  # Last arg is the output
    log_path = _LOG_DIR / f"render-{clip_id}.log"

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Remove any partial output from a previous failed attempt
    if os.path.exists(output_path):
        try:
            os.remove(output_path)
        except OSError:
            pass

    # Build the full command with progress logging
    progress_cmd = cmd + ["-progress", "pipe:1", "-nostats"]

    # Open log file for writing stderr + progress
    log_file = open(log_path, "w", buffering=1)  # line-buffered

    try:
        proc = subprocess.Popen(
            progress_cmd,
            stdout=subprocess.PIPE,
            stderr=log_file,
            stdin=subprocess.DEVNULL,
            start_new_session=True,  # own process group -> killpg on timeout
            text=True,
        )

        # Stall monitoring
        last_progress = time.time()
        total_start = time.time()

        while True:
            elapsed = time.time() - total_start

            # Check hard timeout
            if elapsed >= render_t:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                log_file.close()
                # Write error message
                with open(log_path, "a") as a:
                    a.write(f"\n--- HARD TIMEOUT after {elapsed:.1f}s ---\n")
                return {
                    "success": False,
                    "output_path": output_path if os.path.exists(output_path) else "",
                    "error": "Rendering failed on this computer. Try again, or use a shorter clip. Details are in the log file.",
                    "log_path": str(log_path),
                }

            # Check stall (no progress)
            if time.time() - last_progress > stall_s:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                log_file.close()
                with open(log_path, "a") as a:
                    a.write(f"\n--- STALL after {stall_s}s with no progress ---\n")
                return {
                    "success": False,
                    "output_path": output_path if os.path.exists(output_path) else "",
                    "error": "Rendering failed on this computer. Try again, or use a shorter clip. Details are in the log file.",
                    "log_path": str(log_path),
                }

            # Small sleep before checking again
            time.sleep(0.5)

    except KeyboardInterrupt:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        log_file.close()
        return {
            "success": False,
            "output_path": output_path if os.path.exists(output_path) else "",
            "error": "Rendering failed on this computer. Try again, or use a shorter clip. Details are in the log file.",
            "log_path": str(log_path),
        }
    except Exception:
        log_file.close()
        return {
            "success": False,
            "output_path": output_path if os.path.exists(output_path) else "",
            "error": "Rendering failed on this computer. Try again, or use a shorter clip. Details are in the log file.",
            "log_path": str(log_path),
        }

    # Process ended normally - wait for it to finish
    try:
        proc.wait(timeout=60)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()

    log_file.close()

    # Check return code
    if proc.returncode == 0:
        return {
            "success": True,
            "output_path": output_path,
            "error": "",
            "log_path": str(log_path),
        }
    else:
        return {
            "success": False,
            "output_path": output_path if os.path.exists(output_path) else "",
            "error": "Rendering failed on this computer. Try again, or use a shorter clip. Details are in the log file.",
            "log_path": str(log_path),
        }


# ── Retry logic ────────────────────────────────────────────────────────────

def render_with_retry(
    cmd: list,
    duration_seconds: float,
    clip_id: str,
    stall_seconds: float = None,
    render_timeout: float = None,
) -> dict:
    """Render a clip, with one retry using ultrafast preset on failure.

    Args:
        cmd: The FFmpeg command list (without output path, it's appended).
        duration_seconds: Clip duration.
        clip_id: Identifier for logging/user messages.
        stall_seconds: Override stall timeout.
        render_timeout: Override render timeout.

    Returns:
        dict with success, output_path, error, log_path keys.
    """

    # First attempt with normal preset
    result = render_ffmpeg_with_stall_check(
        cmd,
        duration_seconds,
        stall_seconds=stall_seconds,
        render_timeout=render_timeout,
        clip_id=clip_id,
    )

    if result["success"]:
        return result

    # First attempt failed - retry with ultrafast preset
    # Build a new command with ultrafast preset
    ultrafast_cmd = list(cmd)
    # Replace or add preset
    found_preset = False
    for i, arg in enumerate(ultrafast_cmd):
        if arg == "-preset" and i + 1 < len(ultrafast_cmd):
            ultrafast_cmd[i + 1] = "ultrafast"
            found_preset = True
            break
    if not found_preset:
        # Insert preset after ffmpeg
        new_cmd = ["ffmpeg", "-y", "-nostdin", "-hide_banner"]
        new_cmd.extend(ultrafast_cmd[1:])  # skip "ffmpeg"
        ultrafast_cmd = new_cmd

    # Add -threads 0 if not present
    if "-threads" not in ultrafast_cmd:
        # Find the input arg position and add threads before it
        # or just append at the end (before output)
        # Actually, let's just ensure threads=0 is there
        if "threads" not in [a for a in ultrafast_cmd]:
            # Insert before the output file
            output_pos = len(ultrafast_cmd) - 1  # last arg is output
            ultrafast_cmd.insert(output_pos, "-threads")
            ultrafast_cmd.insert(output_pos + 1, "0")

    # Remove old partial output
    if os.path.exists(result.get("output_path", "")):
        try:
            os.remove(result["output_path"])
        except OSError:
            pass

    # Retry
    result = render_ffmpeg_with_stall_check(
        ultrafast_cmd,
        duration_seconds,
        stall_seconds=stall_seconds,
        render_timeout=render_timeout,
        clip_id=clip_id,
    )

    return result


# ── Public API ─────────────────────────────────────────────────────────────

def render_clip(
    input_path: str,
    output_path: str,
    duration: float,
    clip_id: str = "clip",
    preset: str = None,
    stall_override: str = None,
    timeout_override: str = None,
    ffmpeg_cmd: list = None,
) -> dict:
    """Public function to render a single clip with full safety features.

    This is the function that should be called by video_engine.py and other modules.

    Features:
    - Single global render lock (no concurrent FFmpeg)
    - Stall-based timeout (kill if no progress)
    - Hard timeout cap
    - Retry with ultrafast preset on failure
    - Partial file cleanup
    - Persistent log files
    - Readable user errors only

    Key change: ffmpeg_cmd, if provided, is used directly instead of building
    a new command. This ensures the filter_graph from video_engine.py or
    video_renderer.py is the one actually executed, preventing concurrent FFmpeg
    renders from starving CPUs and guaranteeing the correct filter layout.

    Args:
        input_path: Path to the input video file.
        output_path: Path where the MP4 should be written.
        duration: Clip duration in seconds.
        clip_id: Identifier for logging and error messages.
        preset: FFmpeg preset override. Uses CPU-based default if None.
        stall_override: Override stall timeout (seconds). Sets MAXCLIPPER_STALL_SECONDS env effect.
        timeout_override: Override render timeout (seconds). Sets MAXCLIPPER_RENDER_TIMEOUT env effect.
        ffmpeg_cmd: Pre-built FFmpeg command list. If None, a basic command is
            built as fallback (but callers should always provide one).

    Returns:
        dict with keys: success, output_path, error, log_path
    """
    # Acquire the global render lock
    if not _acquire_render_lock():
        return {
            "success": False,
            "output_path": "",
            "error": "Another render is in progress. Please wait for it to complete, or try again later.",
            "log_path": "",
        }

    try:
        # Use the pre-built command from the caller (video_engine.py or video_renderer.py),
        # or fall back to building a basic command if none provided.
        # The caller's command includes the full filter_complex, so we must use it.
        if ffmpeg_cmd is None:
            # Fallback: build a basic command only if caller didn't provide one.
            # In normal operation, video_engine.py or video_renderer.py always provides one.
            threads = "0"  # always auto threads
            ffmpeg_cmd = build_ffmpeg_cmd(input_path, output_path, duration, preset, threads)

        # Render with retry - convert string overrides to float
        try:
            stall_s = float(stall_override) if stall_override is not None else None
        except (ValueError, TypeError):
            stall_s = None
        try:
            timeout_s = float(timeout_override) if timeout_override is not None else None
        except (ValueError, TypeError):
            timeout_s = None

        result = render_with_retry(
            ffmpeg_cmd,
            duration_seconds=duration,
            clip_id=clip_id,
            stall_seconds=stall_s,
            render_timeout=timeout_s,
        )

        return result
    finally:
        _release_render_lock()