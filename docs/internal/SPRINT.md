# SPRINT — 3-Hour Launch Sprint

Hard clock: start time written to `.loop/SPRINT_CLOCK`. Check `date` at the start of every
block; report elapsed time at each block end. Work on branch `launch-sprint`, commit after
every fix, targeted edits only (never rewrite a whole file). No questions to the owner.
Evidence or it did not happen. No fake numbers, no "AI" wording for the algorithms.

## Mission
In 3 hours, a user pastes a YouTube link and reliably gets ranked, captioned 9:16 clips,
with no job ever stuck. Everything else goes to ROADMAP.md.

## Known facts (from owner's real screenshot)
- Same link submitted twice; BOTH jobs sit at "Downloading low-bitrate audio for analysis... 12%"
  with a "Stuck? Retry lower quality" button that does nothing automatically.
- Earlier jobs: "Interrupted" with wrong state; "Video" titles stuck at "Starting... 0%".
- Machine: 4th-gen i5, 8 GB RAM, slow network (0.2-1 MB/s).

## Verified on this machine (do not re-test)
1. Network + YouTube work. Outside the app: `yt-dlp -f worstaudio -N 4 --force-ipv4`
   downloaded 9.16 MiB audio (format 233, HLS, 26-min video) in 19-27 s (~345 KiB/s).
   The 12% stall is a BUG IN OUR APP.
2. yt-dlp needs a JS runtime (node, installed) AND the EJS challenge solver
   (yt-dlp-ejs, installed via `pip install -U "yt-dlp[default]"`; yt-dlp 2026.10.26, ejs 0.8.0).
   Pass `--js-runtimes node` in EVERY yt-dlp call. "n challenge" warnings are non-fatal.
3. Real sizes for the stuck 26-min video: audio-only ~9 MB; 480p video-only ~109 MB;
   720p 192-413 MB; 1080p 440-730 MB. NEVER download full video.
   Use `--download-sections` (Python API: `download_ranges`) for chosen clips only:
   480p when measured speed < 0.5 MB/s, else 720p.
4. Python 3.14.4 in `myenv`; numpy, scipy, cv2, librosa, faster_whisper all import fine.
   Use myenv only; run the app with `myenv/bin/python`.
5. Deduplicate jobs by video ID + settings. Every job gets its own unique work directory.

## Suspects for the 12% stall (from owner)
(a) two same-link jobs sharing one temp path (.part collision / file lock);
(b) progress hook can't handle fragment/HLS downloads (no total_bytes);
(c) download run through Python API in a thread or asyncio.run() that can deadlock;
(d) undrained pipe.

## BLOCK A (0:00-0:25) — DONE (find why download stalls)
- Timed yt-dlp audio download outside the app; best combo recorded.
- Suspects (a)-(d) identified; fix lands in Blocks B/C.

## BLOCK B (0:25-1:15) — CAPTIONS-FIRST FAST PATH (the core fix)
1. Within 10 s fetch: title, thumbnail, duration, heatmap, captions
   (json3 with word timing, manual first, then auto). Show title + thumbnail in the card immediately.
2. If captions exist: choose moments with NO audio or video download — using captions
   (sentence boundaries, hook score in first 3 s, keyword + focus-text TF-IDF/BM25 boost,
   negative patterns), the heatmap, and the user's time range. Produce candidates + score breakdown.
3. Download ONLY the chosen sections (`--download-sections`, video+audio together,
   480p if measured speed < 0.5 MB/s else 720p, with 2 s margins), reusing ONE extracted
   info dict. Compute audio features (silence, energy) on each downloaded section only,
   to refine start/end points and trim dead air.
4. If NO captions: prefer heatmap peaks. Download low-bitrate audio only in 5-minute chunks
   around the hottest heatmap regions first (or the user's range), analyze each chunk as it
   arrives, emit candidates progressively, and use optional faster-whisper (tiny, int8,
   beam 1, vad_filter) only on the best windows. Hard cap: if measured speed would make the
   audio download exceed 6 minutes, analyze what has arrived, tell the user in plain words.
5. Render each chosen clip in ONE FFmpeg pass
   (`-nostdin -hide_banner -loglevel error -progress pipe:1`, seek before input,
   tiny-copy blur, `-preset veryfast -crf 23`, ASS captions at 1080x1920 with safe zones,
   loudnorm). One render at a time. Show each clip in the Library the moment it finishes.
6. Always return at least 3 clips (target = user's count) or a clear, specific error.
- For videos where audio is small (~9 MB): download audio in the background WHILE
  caption-based candidates are already shown (acceptable per owner).

## BLOCK C (1:15-1:55) — JOBS THAT CAN NEVER BE STUCK
- Deduplicate: same video ID + same settings while queued/running returns the existing job
  and shows "Already processing this video". Normalize youtu.be, youtube.com/watch,
  shorts and ?si= links to the video ID.
- Real lifecycle: QUEUED (with position) -> RUNNING (heartbeat every 2 s) ->
  DONE / FAILED / CANCELLED / INTERRUPTED. A job with no heartbeat for 10 s is never shown
  as working. On every server start: recover or mark INTERRUPTED, kill orphan processes.
  INTERRUPTED cards show Resume and Delete (no spinner, no percent).
- AUTOMATIC stuck watchdog: no progress for 45 s in any stage kills the process group and
  applies the next fallback by itself (other player client -> lower quality -> smaller chunk
  -> captions-only mode -> clear error), logging each attempt. "Retry lower quality" button
  must work too. Every subprocess has a timeout; slots released in `finally`.
- Plain-language errors with fix buttons for: bot-check/sign-in, 403/429, geo-block,
  private/removed, no network, disk full, bad URL.
- UI fixes: brand name + status chips must not wrap in the header at 1440, 1024 and 768 px
  (one clean row); cards show the real stage text, percent, speed and ETA;
  Cancel and Delete work in every state.

## BLOCK D (1:55-2:35) — PROOF ON REAL VIDEOS
Run through the real UI/API (not mocks):
(1) captioned talking video 5-10 min, (2) captioned gameplay/stream video,
(3) a video WITHOUT captions.
For each record: time to first clip, time to all clips, MB downloaded vs full size,
number of clips, score reasons, ffprobe QA (1080x1920, duration, audio present),
3 caption-vs-transcript checks, screenshot of finished card + clip grid.
Break-it tests: kill worker mid-download, same link twice, invalid URL, private video,
cancel mid-render. Each must end in a clean state with a clear message.
Fix every failure, re-run. Loop inside this block until all three videos pass.
Write SPRINT_RESULTS.md with the numbers.

## BLOCK E (2:35-3:00) — MINIMUM LAUNCH
- Honest README (answer-first, what it does, one-command install Windows/macOS-Linux,
  system requirements, mobile/editor limits as roadmap, troubleshooting,
  unofficial-fan-tool + trademark disclaimer, "users must have rights to the videos").
- Test the install script on a fresh clone in a temp folder with a fresh venv; fix breaks;
  app must open from a different working directory.
- LICENSE, .gitignore (no outputs/cache/venv committed), remove .bak/.orig files,
  tag v0.1.0-beta, RELEASE_NOTES.md with honest known limitations.
- ROADMAP.md: editor, Library polish, mobile companion, installers (.exe),
  SEO/GEO/AEO site, extra caption styles.

## Clock rules
If a block runs over by 20%, cut scope inside it (never skip testing) and move the rest to
ROADMAP.md. Never start a later block before the current block's tests pass, except launch
docs may be prepared while a long render runs in the background (never wait idle on a long
process; poll its log).

## FINAL OUTPUT
Print LAUNCH_CHECKLIST with PASS/FAIL + evidence for:
A) captioned video yields clips within 3 minutes of pasting the link
B) video without captions yields clips
C) same link twice creates one job
D) no job is WORKING without a live heartbeat
E) killing the worker leaves a clean Interrupted card with Resume/Delete
F) clean-clone install works
G) header and cards look right at 360/768/1440 px
H) README and disclaimer present
Then ask the owner: "Paste your own link, press Find my clips, and tell me YES or what is wrong."
