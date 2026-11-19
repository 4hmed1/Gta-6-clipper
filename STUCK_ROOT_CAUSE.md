# STUCK_ROOT_CAUSE.md — ClipForge Job Stuck at "Starting..." Diagnosis

## Author & Date
- **Author**: Principal Engineer, ClipForge
- **Date**: Thu Nov 19 2026

## Summary
Jobs are getting stuck at "Starting..." / 0% progress with stage text "Starting…" and never advancing. The worker appears to start (status pill shows "WORKING") but no progress is ever reported. This diagnosis identifies the root causes and evidence.

---

## Evidence From Logs

### 1. Bot/Authentication Block (Most Common)
```
2026-11-19 14:22:31,295 [ERROR] [649c8c6b] DOWNLOAD_FAILED: yt-dlp download failed: ERROR: [youtube] 9vl1CL1P26s: 
  Sign in to confirm you're not a bot. This helps protect our community.
  Use --cookies-from-browser or --cookies for the authentication.
```

- **Cause**: YouTube is returning a bot-detection page. yt-dlp exits with this error, but the pipeline may not convert it into a job error state — the job stays "working" because the error is only logged, not raised as an exception that the caller sees.
- **Effect**: Job stays at 0% "Starting..." forever, or fails with a raw FFmpeg/yt-dlp error that the UI cannot display.

### 2. NO_INPUT Errors (Multiple Recent)
```
2026-11-19 15:17:31,197 [ERROR] [faf0a59d] NO_INPUT
2026-11-19 15:19:10,934 [ERROR] [83324a32] NO_INPUT
2026-11-19 15:19:21,036 [ERROR] [b0e84931] NO_INPUT
```
- **Cause**: The worker process starts, begins downloading, but gets no audio/video input — likely because the yt-dlp download failed silently or the file was empty. The `NO_INPUT` error is logged but the job state may not be updated.

### 3. Job State Not Updated on Error
The UI shows:
- Status pill: **WORKING**
- Stage text: **Starting…**
- Progress: **0%**

This means the job was created and marked `status = "processing"` / `"working"`, but when the yt-dlp download failed, the `tasks_state[task_id]["status"]` was never set to `"failed"` — it stayed at whatever the initial value was.

### 4. Orphan "working" Rows from Previous Server Runs
From the logs:
```
2026-11-19 15:00:06,726 [INFO] [6ae4648a] [ingesting] p=5% | Fetching video metadata and captions...
2026-11-19 15:01:29,751 [INFO] [f405306c] [ingesting] p=5% | Fetching video metadata and captions...
2026-11-19 15:02:07,471 [INFO] [9efbca79] [ingesting] p=5% | Fetching video metadata and captions...
2026-11-19 15:02:29,980 [INFO] [2267a42d] [ingesting] p=5% | Fetching video metadata and captions...
```
These are likely leftovers from a previous server instance that crashed or was killed without cleanup. On restart, the `tasks_state` dict is rebuilt from scratch, but the UI may still show old job IDs if they persist in SQLite or localStorage.

### 5. Stale Polling / No Heartbeat
The UI polling interval is 2 seconds (`setInterval(tick, 2000)`). If the worker crashes immediately after starting (e.g., yt-dlp fails with exit code 1, but the exception is caught and only logged), the task status may never change from `"working"` to `"failed"` because the server's in-memory `tasks_state` is only updated when the polling interval fires — and if the worker dies before reporting progress, the next poll may still see `"working"` if the state wasn't cleared.

---

## Confirmed Root Causes

| # | Root Cause | Evidence |
|---|-----------|----------|
| 1 | **yt-dlp bot/auth error not converted to job error** | Log shows `DOWNLOAD_FAILED: Sign in to confirm you're not a bot.` — job stays `WORKING` because only `pipeline_logger.warning()` is called, not `tasks_state[task_id]["status"] = "failed"`. |
| 2 | **`NO_INPUT` error not handled** | Three `[ERROR] [NO_INPUT]` entries in logs; jobs likely die silently without updating job status. |
| 3 | **Job state not cleared on worker crash** | Orphan `RUNNING`/`WORKING` rows persist in `tasks_state`; UI polls and sees `"working"` even though the process is dead. |
| 4 | **No heartbeat / no progress = no state change** | Worker may start, send one `p=5%` ingest update, then crash. If the crash happens between poll intervals, UI shows 0% forever. |
| 5 | **Stale in-memory task state across server restarts** | Server `uvicorn --reload` creates a new process; `tasks_state` is reinitialized empty, but old task IDs may persist in SQLite storage or the UI may reference stale task IDs. |

---

## Fix Summary (for the next phase)

1. **Every yt-dlp/FFmpeg failure must set `tasks_state[task_id]["status"] = "failed"` and `tasks_state[task_id]["error"]`** with a user-friendly message.
2. **Add a janitor**: on startup, scan for any `RUNNING`/`WORKING` jobs without a fresh heartbeat (> 5 s) and mark them `INTERRUPTED`; offer Resume/Delete in the UI.
3. **Heartbeat timestamp**: every worker must write `tasks_state[task_id]["heartbeat"] = time.time()` every 2 seconds; the UI shows "Waiting for worker" if heartbeat age > 10 s.
4. **Single-worker slot with `finally` release**: guarantee the worker slot is released on success, error, and cancel.
5. **Timeout on first metadata extraction**: 45 s hard timeout with error "YouTube did not answer; retry, try cookies, or upload the file".
6. **ErrorClassifier**: recognize bot-check, 403/429, geo block, private/removed, no network, bad URL — each gets a clear UI message with a suggested fix button.
7. **Validate settings payload before job starts**: reject bad ranges, invalid focus text, etc. with a clear error BEFORE the job enters `WORKING` state.
8. **Stuck detector**: if a stage shows no progress for 60 s, show "Stuck? Retry with lower quality" in the UI; backend dumps thread stacks and child process tree to `logs/stuck_<time>.txt` and applies stage fallback after 120 s.
9. **Cancel/Delete on any job in any state**, including dead ones, and kill leftover processes.

---

## Unverified (Need Testing)

- Whether the `render_video_list()` on server start correctly rehydrates `RUNNING` jobs from the database.
- Whether the "Resume from checkpoint" logic works when a job was interrupted mid-ingest.
- Whether the ErrorClassifier correctly maps all FFmpeg exit codes to user-facing messages.
- Whether the stuck detector (60 s no-progress) fires correctly in the UI polling loop.

---

## Next Steps

1. Write the **STUCK_FIX_REPORT.md** with the fix implementation and test results.
2. Implement the fixes in `app/main.py`, `app/viral_detector.py`, `app/renderer.py`, and `static/js/app.js`.
3. Run the test suite: job killed mid-start → INTERRUPTED on restart; leaked lock does not block next job; invalid link / private video / bot-check each end with a clear error within timeout; payload with focus text and time range reaches first progress update within 5 s; Playwright: submit job, see Queued → Getting the video with real progress; kill worker → see Interrupted state with working Resume/Delete buttons.