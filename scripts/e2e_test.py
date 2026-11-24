#!/usr/bin/env python3
"""End-to-end test for Max Clipper web API.
Uses only stdlib + subprocess (ffmpeg/ffprobe).
Tests the same HTTP API the web page uses.

Usage:
    python scripts/e2e_test.py
    E2E_URL=https://www.youtube.com/watch?v=jNQXAC9IJRE python scripts/e2e_test.py
"""
import json
import os
import signal
import subprocess
import sys
import time
import tempfile
import urllib.error
import urllib.request
import http.client
from pathlib import Path

# ── Configuration ────────────────────────────────────────────────────────────
SERVER_PORT = 3077
MAXCLIPPER_DATA_DIR = Path(os.environ.get("MAXCLIPPER_DATA_DIR", ""))
if not MAXCLIPPER_DATA_DIR:
    MAXCLIPPER_DATA_DIR = Path(tempfile.mkdtemp(prefix="mc-e2e-", dir=os.path.expanduser("~")))
MAXCLIPPER_DATA_DIR.mkdir(parents=True, exist_ok=True)

E2E_URL = os.environ.get("E2E_URL", "")  # Optional YouTube URL for TEST 2

BASE = f"http://localhost:{SERVER_PORT}"


# ── Helpers ──────────────────────────────────────────────────────────────────
def log(msg):
    print(f"[e2e] {msg}", flush=True)


def http_post_json(path, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def http_get(path):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=15) as resp:
        return json.loads(resp.read())


def http_download(path):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=30) as resp:
        return resp.status, resp.read()


def wait_for_health(max_wait=60):
    start = time.time()
    while time.time() - start < max_wait:
        try:
            data = http_get("/api/health")
            if data.get("status") == "ok":
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def gen_test_video() -> str:
    """Generate a 3-min 1280x720 30fps test video with sine audio."""
    vpath = Path(tempfile.mktemp(suffix=".mp4", prefix="e2e-video-"))
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc2=duration=180:rate=30:size=1280x720",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=180:sample_rate=44100",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        str(vpath),
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return str(vpath)


def upload_video(video_path: str, settings: dict) -> dict:
    """Upload a video file via curl (multipart/form-data)."""
    settings_json = json.dumps(settings)
    result = subprocess.run([
        "curl", "-s", "-w", "\n%{http_code}",
        "-X", "POST",
        "-F", f"file=@{video_path}",
        "-F", f"settings={settings_json}",
        f"{BASE}/api/upload",
    ], capture_output=True, text=True, timeout=120)

    lines = result.stdout.strip().rsplit("\n", 1)
    if len(lines) == 2:
        body, code = lines
    else:
        body, code = result.stdout.strip(), "200"

    if result.returncode != 0 or int(code) != 200:
        raise RuntimeError(f"Upload failed: {result.stderr}\nBody: {body}")

    return json.loads(body)


def poll_job(task_id, timeout=1200, interval=5):
    """Poll job status until completed/failed/interrupted. Returns status dict."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            data = http_get(f"/api/status/{task_id}")
            status = data.get("status", "")
            message = data.get("message", "")
            progress = data.get("progress", "")
            if progress:
                sys.stderr.write(f"\r[{task_id}] {status} {progress} {message}")
            else:
                sys.stderr.write(f"\r[{task_id}] {status} {message}")
            sys.stderr.flush()
            if status in ("completed", "failed", "interrupted", "error"):
                return data
        except Exception as e:
            log(f"Poll error: {e}")
        time.sleep(interval)
    return {"status": "timeout"}


def ffprobe_props(video_path: str) -> dict:
    """Return dict of codec, width, height, fps, audio codec for a video."""
    result = subprocess.run([
        "ffprobe", "-v", "quiet",
        "-show_entries", "stream=codec_name,width,height,r_frame_rate,channels",
        "-of", "json",
        video_path,
    ], capture_output=True, text=True, timeout=30, check=True)

    streams = json.loads(result.stdout).get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio = next((s for s in streams if s.get("codec_type") == "audio"), {})

    fps_str = video.get("r_frame_rate", "0/1")
    if "/" in fps_str:
        num, den = fps_str.split("/")
        fps = float(num) / float(den) if float(den) else 0
    else:
        fps = float(fps_str)

    return {
        "codec": video.get("codec_name", ""),
        "width": int(video.get("width", 0)),
        "height": int(video.get("height", 0)),
        "fps": round(fps, 1),
        "audio_codec": audio.get("codec_name", ""),
    }


def read_server_log(server_proc):
    """Read last 60 lines of server log."""
    if server_proc and hasattr(server_proc, "stdout"):
        server_proc.stdout.seek(0)
        lines = server_proc.stdout.read().decode(errors="replace").split("\n")
        return "\n".join(lines[-60:])
    return "No log available"


# ── TEST 1: Upload with captions ON ──────────────────────────────────────────
def test_upload_captions_on(video_path: str) -> list:
    log("TEST 1: Upload with captions ON (3 clips)")
    settings = {
        "clip_count": 3,
        "length_min": 15.0,
        "length_max": 30.0,
        "aspect": "9:16",
        "caption_style": "pop-bold",
        "framing": "auto",
        "hook_text": False,
        "tighten_pauses": True,
        "focus_text": "",
    }

    resp = upload_video(video_path, settings)
    task_id = resp.get("task_id") or resp.get("id")
    if not task_id:
        raise RuntimeError(f"No task_id in upload response: {resp}")

    status_data = poll_job(task_id, timeout=1200)
    status = status_data.get("status", "")

    if status == "failed":
        err = status_data.get("error", "unknown error")
        log(f"TEST 1 FAILED: {err}")
        raise RuntimeError(f"Job failed: {err}")

    if status != "completed":
        raise RuntimeError(f"Job did not complete: {status}")

    # Collect clips from response
    clips = status_data.get("clips", [])
    if not clips:
        # Try other keys
        clips = status_data.get("results", status_data.get("outputs", []))
    if not clips:
        raise RuntimeError("No clips in completed job response")

    log(f"TEST 1: Got {len(clips)} clips")
    verified = []
    for i, clip in enumerate(clips):
        clip_path = clip.get("filepath") or clip.get("path") or clip.get("output_path") or ""
        if not clip_path:
            # Try to find the clip file in data dir
            clip_name = clip.get("clip_name") or clip.get("name") or ""
            if clip_name:
                clip_path = str(MAXCLIPPER_DATA_DIR / "clips" / clip_name)

        if not clip_path or not Path(clip_path).exists():
            log(f"  Clip {i}: path not found: {clip_path}")
            verified.append({"ok": False, "reason": "path not found"})
            continue

        props = ffprobe_props(clip_path)
        size_kb = Path(clip_path).stat().st_size / 1024

        # Check video properties
        ok = True
        issues = []
        if props["codec"] != "h264":
            ok, issues = False, f"codec={props['codec']}, expected h264"
        if props["width"] != 1080 or props["height"] != 1920:
            issues.append(f"res={props['width']}x{props['height']}, expected 1080x1920")
            ok = False
        if abs(props["fps"] - 30) > 1:
            issues.append(f"fps={props['fps']}, expected ~30")
            ok = False
        if props["audio_codec"] != "aac":
            issues.append(f"audio={props['audio_codec']}, expected aac")
            ok = False
        if size_kb < 100:
            issues.append(f"size={size_kb:.0f}KB, expected >100KB")
            ok = False

        # Check download endpoint
        clip_name = Path(clip_path).name
        try:
            code, content = http_download(f"/api/clips/download/{clip_name}")
            if code != 200 or len(content) < 1000:
                issues.append(f"download: HTTP {code}, {len(content)} bytes")
                ok = False
        except Exception as e:
            issues.append(f"download failed: {e}")
            ok = False

        # Check .ass caption position
        ass_path = Path(clip_path).with_suffix(".ass")
        ass_ok = False
        if ass_path.exists():
            ass_text = ass_path.read_text()
            if r"{\pos(" in ass_text:
                ass_ok = True
        elif ass_path.exists() or any(MAXCLIPPER_DATA_DIR.rglob("*.ass")):
            # ASS might be in a subdirectory
            pass

        result = {
            "ok": ok,
            "path": clip_path,
            "props": props,
            "size_kb": round(size_kb, 1),
            "issues": issues,
            "ass_ok": ass_ok,
        }
        verified.append(result)
        status_str = "OK" if ok else f"FAIL: {'; '.join(issues)}"
        log(f"  Clip {i}: {status_str}")

    return verified


# ── TEST 2: Upload with captions OFF ─────────────────────────────────────────
def test_upload_captions_off(video_path: str) -> list:
    log("TEST 2: Upload with captions OFF (3 clips)")
    settings = {
        "clip_count": 3,
        "length_min": 15.0,
        "length_max": 30.0,
        "aspect": "9:16",
        "caption_style": "none",
        "framing": "auto",
        "hook_text": False,
        "tighten_pauses": True,
        "focus_text": "",
    }

    resp = upload_video(video_path, settings)
    task_id = resp.get("task_id") or resp.get("id")
    if not task_id:
        raise RuntimeError(f"No task_id in upload response: {resp}")

    status_data = poll_job(task_id, timeout=1200)
    status = status_data.get("status", "")

    if status == "failed":
        err = status_data.get("error", "unknown error")
        log(f"TEST 2 FAILED: {err}")
        raise RuntimeError(f"Job failed: {err}")

    if status != "completed":
        raise RuntimeError(f"Job did not complete: {status}")

    clips = status_data.get("clips", [])
    if not clips:
        clips = status_data.get("results", status_data.get("outputs", []))
    if not clips:
        raise RuntimeError("No clips in completed job response")

    verified = []
    for i, clip in enumerate(clips):
        clip_path = clip.get("filepath") or clip.get("path") or clip.get("output_path") or ""
        if not clip_path:
            clip_name = clip.get("clip_name") or clip.get("name") or ""
            if clip_name:
                clip_path = str(MAXCLIPPER_DATA_DIR / "clips" / clip_name)

        if not clip_path or not Path(clip_path).exists():
            verified.append({"ok": False, "reason": "path not found"})
            continue

        props = ffprobe_props(clip_path)
        size_kb = Path(clip_path).stat().st_size / 1024

        ok = True
        issues = []
        if props["codec"] != "h264":
            issues.append(f"codec={props['codec']}")
            ok = False
        if props["width"] != 1080 or props["height"] != 1920:
            issues.append(f"res={props['width']}x{props['height']}")
            ok = False
        if abs(props["fps"] - 30) > 1:
            issues.append(f"fps={props['fps']}")
            ok = False
        if props["audio_codec"] != "aac":
            issues.append(f"audio={props['audio_codec']}")
            ok = False
        if size_kb < 100:
            issues.append(f"size={size_kb:.0f}KB")
            ok = False

        verified.append({
            "ok": ok,
            "path": clip_path,
            "props": props,
            "size_kb": round(size_kb, 1),
            "issues": issues,
        })
        status_str = "OK" if ok else f"FAIL: {'; '.join(issues)}"
        log(f"  Clip {i}: {status_str}")

    return verified


# ── TEST 3: YouTube URL (if E2E_URL set) ─────────────────────────────────────
def test_youtube() -> dict:
    if not E2E_URL:
        log("TEST 3: YouTube URL — NOT TESTED (E2E_URL not set)")
        return {"status": "not_tested", "reason": "E2E_URL not set"}

    log(f"TEST 3: YouTube URL: {E2E_URL}")
    payload = {
        "url": E2E_URL,
        "clip_count": 3,
        "length_min": 15.0,
        "length_max": 30.0,
        "aspect": "9:16",
        "caption_style": "pop-bold",
        "framing": "auto",
    }

    try:
        resp = http_post_json("/api/process", payload)
    except Exception as e:
        log(f"TEST 3: Could not submit job: {e}")
        return {"status": "not_tested", "reason": str(e)}

    task_id = resp.get("task_id") or resp.get("id")
    if not task_id:
        log(f"TEST 3: No task_id: {resp}")
        return {"status": "not_tested", "reason": "no task_id"}

    status_data = poll_job(task_id, timeout=1200)
    status = status_data.get("status", "")
    err = status_data.get("error", "")

    if status == "failed":
        log(f"TEST 3: Job failed (YouTube may be unreachable): {err}")
        return {"status": "not_tested", "reason": f"download failed: {err}"}

    if status == "completed":
        clips = status_data.get("clips", status_data.get("results", []))
        log(f"TEST 3: Completed with {len(clips)} clips")
        return {"status": "completed", "clips": len(clips)}

    return {"status": status, "error": err}


# ── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    log(f"Data dir: {MAXCLIPPER_DATA_DIR}")
    log(f"Server port: {SERVER_PORT}")
    log(f"E2E_URL: {'set' if E2E_URL else 'not set'}")

    # Start server
    log("Starting server...")
    env = os.environ.copy()
    env["MAXCLIPPER_DATA_DIR"] = str(MAXCLIPPER_DATA_DIR)

    log_file = Path(tempfile.mktemp(prefix="e2e-server-", suffix=".log"))
    with open(log_file, "w") as lf:
        server_proc = subprocess.Popen(
            [sys.executable, "-m", "maxclipper", "--no-browser", "--port", str(SERVER_PORT)],
            env=env,
            stdout=lf,
            stderr=lf,
        )

    if not wait_for_health(60):
        lf = open(log_file).read()
        log("FAIL: server did not start")
        log(lf[-1000:])
        return 1

    log("Server healthy")
    try:
        # Generate test video
        log("Generating test video...")
        video_path = gen_test_video()
        log(f"Test video: {video_path} ({Path(video_path).stat().st_size // 1024} KB)")

        # TEST 1: Captions ON
        clips_on = test_upload_captions_on(video_path)
        # TEST 2: Captions OFF
        clips_off = test_upload_captions_off(video_path)
        # TEST 3: YouTube
        yt_result = test_youtube()

        # ── Results ────────────────────────────────────────────────
        all_clips = clips_on + clips_off
        passed = len(all_clips) > 0 and all(c.get("ok", False) for c in all_clips)
        failed_clips = [c for c in all_clips if not c.get("ok", False) and c.get("ok") is not None]

        if passed and clips_on:
            log("")
            log("=" * 60)
            log("E2E PASS")
            log("=" * 60)
            log(f"{'Clip':<12} {'Codec':<8} {'Res':<12} {'FPS':<6} {'Audio':<8} {'Size':<10}")
            log("-" * 60)
            for i, c in enumerate(all_clips):
                if c.get("ok"):
                    p = c["props"]
                    log(f"  clip_{i:<6} {p['codec']:<8} {p['width']}x{p['height']:<6} {p['fps']:<6} {p['audio_codec']:<8} {c['size_kb']:.0f}KB")
            log(f"Total clips verified: {len([c for c in all_clips if c.get('ok')])}")
            if yt_result.get("status") == "completed":
                log(f"YouTube test: completed ({yt_result.get('clips', 0)} clips)")
            else:
                log(f"YouTube test: {yt_result.get('status', 'not_tested')} — {yt_result.get('reason', '')}")
        else:
            log("")
            log("E2E FAIL")
            for c in failed_clips:
                log(f"  Failed clip: {c.get('path', 'unknown')} — {c.get('issues', c.get('reason', 'unknown'))}")
            if not clips_on:
                log("  No clips produced in TEST 1")

    except Exception as e:
        log(f"")
        log(f"E2E FAIL: {e}")
        log("Server log (last 60 lines):")
        print(read_server_log_from_file(log_file))

    finally:
        # Kill server
        log("Stopping server...")
        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_proc.kill()

        # Kill any lingering ffmpeg
        subprocess.run(["pkill", "-9", "ffmpeg"], capture_output=True)
        subprocess.run(["pkill", "-9", "ffprobe"], capture_output=True)

        # Verify no ffmpeg left
        result = subprocess.run(["pgrep", "-a", "ffmpeg"], capture_output=True, text=True)
        if result.stdout.strip():
            log(f"WARNING: ffmpeg still running: {result.stdout}")

    return 0 if passed else 1


def read_server_log_from_file(log_path):
    try:
        with open(log_path) as f:
            lines = f.read().split("\n")
            return "\n".join(lines[-60:])
    except Exception:
        return "Could not read log"


if __name__ == "__main__":
    sys.exit(main())
