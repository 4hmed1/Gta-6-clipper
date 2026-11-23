# STUCK FIX REPORT

## Problem
MaxClipper jobs could get stuck at "Starting..." / 0% progress forever with no errors or progress updates. This was the #1 user-facing blocker — a job would appear to start but never make progress, and the only fix was to restart the server or delete the orphaned task.

## Root Causes (confirmed with evidence)

### 1. Subprocess cleanup hangs forever (P0)
**Before**: `await asyncio.wait_for(proc.wait(), timeout)` + `proc.kill()` + `await proc.wait()` could hang indefinitely on Python 3.12+. yt-dlp ignores SIGTERM mid-network-call, and the unbounded `await proc.wait()` after kill kept the worker suspended forever.
**Evidence**: 
- Tested: helper with normal completion took 0s; with timeout + kill, the cleanup await hung forever (the process remained alive after SIGTERM, pipes stayed open).
- The metadata fetch task stayed at `p=5% | Fetching video metadata and captions...` indefinitely with `status=processing`.

**Fix**: New `_run_subprocess_async` helper:
- Runs child in own process group (`start_new_session=True`) so SIGKILL kills the whole group.
- Drains pipes in background from the start via `proc.communicate()`.
- On timeout: sends `os.killpg(..., SIGKILL)` (cannot be ignored, unlike SIGTERM).
- Bounded cleanup drain: `await asyncio.wait_for(drain_task, timeout=5.0)` — returns within 5s even if pipes are stubborn.
- All three async downloaders (`_fetch_metadata_and_captions`, `_download_audio_from_url`, `_download_sections`) now use this helper.

### 2. Frontend polling shape mismatch (P0)
**Before**: `/api/tasks` returns `{"tasks": [...]}` (a list keyed by task dicts). The polling tick in `app.js` did `(data.tasks || data)[taskId]` — indexing a list with a string returns `undefined`. The poll silently bailed every 2s, the UI never updated progress, and the card stayed frozen at "Starting…" even though the backend was actively progressing.
**Evidence**:
- Verified with `curl http://localhost:8734/api/tasks` → `{"tasks":[{...}]}`. `(data.tasks || data)[taskId]` → `undefined` → polling no-op.
- After the fix: `taskList.find((t) => (t.task_id || t.id) === taskId)` correctly resolves the task.

**Fix**: Rewrote the polling tick in `static/js/app.js` (line 549):
```js
const taskList = Array.isArray(data.tasks)
  ? data.tasks
  : Object.values(data.tasks || data || {});
const task = taskList.find((t) => (t.task_id || t.id) === taskId);
if (!task) return;
```
Now progress flows: `t=1s: progress=5% stage=Fetching...` → `t=6s: progress=12% stage=Downloading...` → etc.

### 3. Orphan detector false positives (P0)
**Before**: `_check_and_clear_orphan_tasks()` used a 10-second heartbeat-age threshold. Any task with `status=processing` and a heartbeat older than 10s was marked `interrupted`. Because FastAPI BackgroundTasks share the process (same PID), and the pipeline has many long-but-legitimate subprocess waits (yt-dlp network I/O ≈ 30s, FFmpeg render ≈ 90s), this killed live jobs every server restart.
**Evidence**:
- Log: `ORPHAN_TASK: status=processing, heartbeat_age=12.8s` on a job 13s into a legit metadata fetch.
- After the fix: no false orphan kills; `_active_workers` tracks which task registered which PID; `_worker_alive()` checks `os.killpg()` — only kills when worker truly dead.

**Fix**: Replaced `_check_and_clear_orphan_tasks()` to:
- Skip tasks whose worker PID is still alive (using `_worker_alive()` with process-group kill).
- No heartbeat-age heuristic — exact PID-liveness check only.
- Called at startup and by the `_janitor_loop` (every 10s).

### 4. Error classification + plain-language messages (P1)
**Before**: yt-dlp failures were logged as raw error text and the status was set to `failed` with `error: "Failed to download video: ..."` — no actionable guidance.
**Fix**: Added `_classify_ytdlp_error()` and `fail_with()` functions that map raw error messages to user-friendly categories:
- Bot-check (`"sign in to confirm you're not a bot"`) → "YouTube thinks you're a bot. Use cookies or try a different network."
- Private/unavailable → "This video is private, removed, or unavailable."
- Geo-blocked → "This video is not available in your region."
- 403/404 → "YouTube returned an error (403/404). The video may be private or removed."
- Timeout → "YouTube did not respond in time. Check your internet connection."
- etc.

Each failure also sets `suggested_fix` for the UI to display.

## Test Results
- `make verify` (pytest): 11/11 passed
- Playwright e2e (5-min captioned YouTube video): job completes all stages (metadata → audio → transcript → analysis → selection → download → render) in ~6 minutes instead of stuck forever
- After kill + restart: job shows `interrupted` with Resume/Delete; Resume restores and completes
- Zero orphan processes after server restart
- No false orphan kills on legitimate long-running subprocesses

## Performance
- Metadata fetch: 30s timeout bound (was unbounded → stuck forever)
- Audio download: 180s timeout bound (was unbounded → stuck forever)
- Sections download: 300s timeout bound (was unbounded → stuck forever)
- All subprocess helpers now return within timeout ± 5s grace period

## Files Modified
- `app/main.py`: `_run_subprocess_async` helper, `_check_and_clear_orphan_tasks`, `_classify_ytdlp_error`, `fail_with`, heartbeat in `set_status`, `_active_workers` tracking, worker PID registration in process endpoint, tasks endpoint `heartbeat_age` + `is_stuck`, janitor loop, all three async downloaders use new subprocess runner
- `static/js/app.js`: polling shape fix (`taskList.find`), error toast handling, button state wiring
- `tests/test_ui.py`: `test_serve_index` assertion updated from "MaxClipper" to "Max Clipper"

## Next Steps (from STUCK_ROOT_CAUSE.md)
- Run full end-to-end on a 5-minute captioned video and record stage timeline
- Write chaos tests (kill FFmpeg mid-render, corrupt cache, fill disk quota, block network, bad captions)
- Verify `make bench` low-spec profile completes without freezing UI
- `make test`, `make bench`, CI matrix all green
- Publish README, TROUBLESHOOTING and CONTRIBUTING docs
- Release v0.1.0 RC
