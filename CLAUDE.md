# MASTER PROMPT v2 — MaxClipper: Install-in-One-Command Clipping Studio

---

## 0. ROLE AND MISSION

You are a principal engineer (video processing, algorithms, cross-platform desktop tooling, product design). Build **MaxClipper**: an open-source, local-first app that turns a YouTube link into ready-to-post vertical Shorts, then lets the user polish each clip in a CapCut-style editor. It installs with **one command** on Windows, macOS and Linux, runs fully on the user's own computer, and never makes them touch FFmpeg, Python paths, or config files.

Work autonomously, phase by phase. Run everything you build. Test it, fix it, then move on. Ask me questions only if you are completely blocked; otherwise decide, record it in `DECISIONS.md`, and continue. **Never claim something works unless you ran it and saw it work.** If you cannot test something (for example macOS from a Linux box), say so and cover it with CI (Section 11).

## 1. WHY THIS TOOL WINS (build around these, they are the product)

1. **Free, unlimited, no watermark, no account, private**: everything runs locally. Nothing is uploaded.
2. **Explainable clip picking**: each clip shows a score and the reasons (hook, energy, heatmap, pacing…). Users trust it and can tune it.
3. **Runs well on weak PCs** (design target: 4th-gen Intel i5, 8 GB RAM, no GPU, HDD or slow SSD). Speed on cheap hardware is a headline feature.
4. **Self-healing**: it detects failures and fixes or works around them automatically (Section 7).
5. **Questions first, smart defaults always**: a short wizard shapes the output; every question can be skipped.
6. **A real editor**: not just a downloader. Every clip opens in a timeline editor.
7. **One-command install and one-command update.**

## 2. HARD CONSTRAINTS

1. **No LLM, no paid API, no cloud AI** in clip selection. Selection is deterministic, explainable algorithms (DSP, statistics, text heuristics, classical computer vision). Same input gives same output.
2. Everything free and local. Allowed: Python 3.11+, FastAPI, FFmpeg, yt-dlp, NumPy/SciPy, librosa (DSP only), OpenCV (classical only), SQLite, React.
3. Speech-to-text is the **only** place a model may exist, as an optional offline engine (`faster-whisper`), OFF by default and installed only if the user opts in. Default text source is YouTube captions with word timing. Design the scoring and caption modules behind a `TranscriptProvider` interface so more providers can be added later (including optional user-supplied keys for people who want them, never required and never default).
4. Never crash on bad input. Every error gets a plain-language message and a fix.
5. No telemetry. Optional, local-only crash reports the user can choose to share.

## 3. PRODUCT FLOW

### 3.1 Step 1: Link
User pastes a YouTube URL (or drops a local video file). Validate instantly; show title, duration, thumbnail within 2 seconds.

### 3.2 Step 2: The Wizard (every question skippable, "Use smart defaults" button always visible, choices saved as presets)
Ask, in a clean one-screen-per-group UI with live phone preview where possible:
- **Content type**: podcast / interview, educational, gaming, vlog, motivation/speech, comedy, news, music/other. This selects a scoring preset (for example podcasts weigh hooks and speech density; gaming weighs audio bursts and motion).
- **Clip length**: range slider (15–90 s) plus quick buttons (≈20, ≈30, ≈45, ≈60). **Number of clips**: auto, or 3 / 5 / 10 / 15.
- **Which part of the video**: whole video, or a time range.
- **Captions**: on/off; style gallery (8+ styles, live preview); font; size; text color, highlight color, outline/shadow; position (top / middle / bottom / custom); words per line (1–4); animation (pop, karaoke highlight, typewriter, none); uppercase on/off; keyword emphasis on/off; profanity masking on/off.
- **Caption language**: from available caption tracks.
- **Reframe**: auto (recommended) / blur background / smart face-follow crop / center crop / keep original with blur.
- **Platform preset**: TikTok / Reels / YouTube Shorts (sets safe zones, max length, loudness).
- **Extras**: hook title card at the start (on/off, style), progress bar, watermark (user's own logo/text, optional), background music from a user-chosen file with auto-ducking, auto-normalize loudness, remove long silences.
- **Quality**: Fast preview / Balanced / Best.
Show a final summary card, then "Start". Save the choices as a named preset for next time.

### 3.3 Step 3: Processing view
One clear progress screen: stage names ("Reading captions", "Finding the best moments", "Rendering clip 2 of 8"), a real percentage, a time estimate, a Cancel button, and live errors that explain what the engine is doing to fix them. First clip previews appear as soon as they are ready; the user can start reviewing while the rest render.

### 3.4 Step 4: Results
Ranked clip cards: video preview (hover to play), score, "why this clip" chips, title, duration. Actions: **Edit**, Download, Regenerate with different length/style, Delete, Select several, **Download all as zip**. Sort and filter by score or duration.

### 3.5 Step 5: The Editor (opens on its own page/route per clip, CapCut-like)
Layout: left = media / text / captions / effects panels; center = phone-frame preview with safe-zone toggle; right = properties inspector; bottom = timeline. Required features:
- **Timeline** with tracks: video, captions, text overlays, stickers/images, audio (original + music). Zoom, snap, ripple, drag to move, handles to trim, waveform, thumbnail strip.
- **Edit tools**: split (S), delete, trim, duplicate, speed (0.25–4×), reverse optional, volume, fade in/out, freeze frame, crop/zoom/position of the video, flip/rotate.
- **Captions**: edit text inline, edit word timing, restyle all or one, drag directly on the preview canvas to reposition, resize, rotate; per-word highlight; apply a style to all.
- **Text and images**: add text with fonts/colors/shadow/animation, add logo or sticker, set start/end on the timeline.
- **Visual**: brightness/contrast/saturation/temperature, simple filters (LUT presets), vignette, blur background strength, transitions (fade, slide, zoom) between segments.
- **Audio**: loudness normalize, music track with ducking, mute, noise reduction (FFmpeg `afftdn`).
- **Undo/redo** (unlimited within session), **autosave** every few seconds, crash-safe project recovery, keyboard shortcuts with a cheat sheet, ctrl+scroll zoom, drag-and-drop files.
- **Export**: preview-quality (fast) and final (1080×1920), MP4; progress with cancel; GIF/thumbnail export optional.
- **Architecture rule**: the editor edits a single **Project JSON** (tracks, clips, effects, caption words, styles). The preview renders that JSON in the browser (HTML5 video + canvas/DOM overlays on a 540p proxy for smooth scrubbing on weak PCs). The exporter **compiles the same JSON to one FFmpeg filter graph**. A golden-test suite must prove that preview and export match (positions, timing, styles) within tolerance.

## 4. PIPELINE (isolated, testable modules)

### A. Ingest
yt-dlp metadata, the "most replayed" **heatmap** when available, captions in `json3` with word-level offsets (manual first, then auto). Download audio low-res first for analysis; download only chosen sections later (`--download-sections`) at up to 1080p; cache by video ID + params. Download layer: multiple player clients, retries with backoff, optional browser cookies, clear message when YouTube blocks, local upload fallback.

### B. Signals (hop 50 ms, robust-normalized per video)
RMS/loudness, energy variance and slope, spectral flux and flatness (laughter/applause/crowd bursts), pitch contour/variance (emotion proxy), dead-air map (silencedetect plus hysteresis VAD), speech rate and pause lengths from word timings, scene-cut density and motion intensity.

### C. Text (classic NLP only)
Sentence boundaries from punctuation plus pauses; **hook score** for the first 3 s (questions, numbers, contrast words, bold claims, curiosity gaps), patterns in YAML; TextRank/TF-IDF keyword salience; rule-based sentiment/intensity lexicon; negative patterns (intros, outros, sponsor reads, "subscribe", repeated sentences, filler); completeness (starts at a thought start, ends at a thought end).

### D. Select
Candidates from sliding windows over sentence boundaries, snapped to words (pre-roll 0.15 s, short tail, never inside a word). Score = weighted sum of normalized features minus penalties, with weights in `config/scoring/*.yaml` per content type. Non-maximum suppression plus diversity pass. Output: start, end, 0–100 score, feature breakdown, template-generated title, transcript text. `make calibrate` fits weights from clips the user labels good/bad (logistic regression/grid search, offline).

### E. Reframe
Blur-fit (blur a 270×480 downscale then upscale), smart crop (OpenCV cascade face detection at 3–5 fps, Kalman/EMA smoothing with dead-zone, reset at scene cuts, fallback to motion-saliency centroid then center), crop path exported as keyframes and applied by an FFmpeg expression. Split-screen for two stable face clusters.

### F. Captions
ASS generated from word timings at `PlayResX=1080`, `PlayResY=1920`, `ScaledBorderAndShadow=yes`. Chunk by pause and length; active-word highlight and pop animation via `\t`, `\fscx/\fscy`, `\k/\kf`. Platform safe-zone presets (about y 250–1500, x 90–950, bottom margin ≈420 px, right margin ≈130 px). Timing repair: min word 80 ms, no overlaps, merge punctuation tokens, clamp to clip start. Bundle only open-license fonts.

### G. Render
One FFmpeg call per clip: seek before input, scale, blur, overlay, crop path, subtitles, loudnorm (≈ −14 LUFS), single filter graph. Defaults `libx264 -preset veryfast -crf 23 -r 30 -pix_fmt yuv420p -movflags +faststart`, AAC 128k. Auto-detect hardware encoders (nvenc, qsv, videotoolbox, vaapi, amf) with verified fallback to x264. Fast preview first, final on demand. Progress from `-progress pipe:1` through SSE (no polling). Target: 45 s clip renders in under 30 s on a 4-core CPU; on the weak-PC target, report honest numbers and tune presets automatically.

## 5. TECH STACK AND LAYOUT

Backend: FastAPI, Pydantic v2, SQLite, `multiprocessing` worker pool for heavy work (never block the event loop). Frontend: React + TypeScript + Vite + Tailwind, built and **bundled into the Python package** so users do not need Node. Editor timeline built with canvas/virtualized DOM for 60 fps. Tests: pytest, Playwright, ruff, mypy. Repo: monorepo with `maxclipper/` (backend), `web/` (frontend), `installers/`, `config/`, `tests/`, `docs/`.

## 6. INSTALL AND DISTRIBUTION (must be flawless)

Goal: a non-technical user copies one command, pastes it, and the app opens in their browser.

- **Windows (PowerShell)**: `irm https://raw.githubusercontent.com/<user>/maxclipper/main/install.ps1 | iex`
- **macOS / Linux**: `curl -fsSL https://raw.githubusercontent.com/<user>/maxclipper/main/install.sh | sh`
- The installer: detects OS/arch, installs `uv` (or uses the system Python 3.11+), creates an isolated environment (no global pollution), installs MaxClipper, **downloads a verified static FFmpeg/ffprobe automatically** if none is found (checksums verified), installs yt-dlp, adds the `maxclipper` command to PATH, creates a desktop/start-menu shortcut, runs `maxclipper doctor`, then prints "Run: maxclipper". No admin rights required.
- **Commands**: `maxclipper` (start server and open browser on localhost), `maxclipper update` (app + yt-dlp), `maxclipper doctor` (checks Python, FFmpeg, encoders, disk, ports, permissions, with auto-fix suggestions), `maxclipper uninstall`, `maxclipper --port`, `maxclipper --no-browser`.
- Scripts must be short, readable, idempotent, safe to re-run, with clear error messages. Publish SHA-256 checksums with each release and document the manual alternative (`pipx install maxclipper`).
- **GitHub Actions** release workflow builds on `windows-latest`, `macos-latest` (Intel and Apple Silicon) and `ubuntu-latest`: runs tests, builds the wheel, and also produces standalone bundles (PyInstaller or similar) attached to GitHub Releases. Phase 2: winget and Homebrew manifests.
- First-run experience: zero config, opens the browser, shows a 3-step welcome, runs a self-test on a bundled tiny sample clip so the user knows everything works.
- Docs: `README.md` (install in 3 lines, GIF demo, FAQ), `docs/TROUBLESHOOTING.md`, `CONTRIBUTING.md`, issue templates (bug template asks for `maxclipper doctor` output), MIT or Apache-2.0 license (decide, record in `DECISIONS.md`).
- Legal: README and first-run screen state clearly that users must have the rights to videos they process and follow YouTube's terms.

## 7. THE SELF-HEALING ENGINE (core differentiator, build it as its own module `maxclipper/resilience/`)

1. **Pipeline as a checkpointed state machine**: every stage writes its result to disk with a content hash; every stage is idempotent; after a crash or restart the job resumes from the last good stage.
2. **Fallback ladders** (try in order, log each attempt, show the user a friendly note):
   - Download: player client A → B → C → cookies → lower resolution → ask for local upload; auto-update yt-dlp on known failure signatures, then retry.
   - Captions: manual → auto → (if enabled) offline STT → audio-only mode (clip by audio/heatmap signals, captions off with notice).
   - Encoder: hardware → x264 veryfast → x264 ultrafast at lower resolution.
   - Reframe: smart crop → blur-fit → center crop.
   - Caption burn failure: re-render without custom font → without animation → export without captions plus separate `.srt`.
3. **Error classifier**: maps raw FFmpeg/yt-dlp/OS errors (disk full, permission, codec missing, network, rate limit, corrupted file, out of memory) to a cause, an automatic fix attempt, and a human message.
4. **Resource governor**: samples CPU, RAM and disk; picks worker count and encoder preset adaptively; pauses new jobs under memory pressure; lowers preview quality on weak machines; keeps the UI responsive (target: UI interactions under 100 ms during rendering, by lowering worker priority/nice level).
5. **Watchdogs**: timeouts per stage based on duration; kill and retry hung processes; orphan-process cleanup on exit; temp-file janitor.
6. **Input repair**: probe every file with ffprobe; remux/transcode odd inputs (variable frame rate, strange audio layouts, rotated phones) to a normalized intermediate before processing.
7. **Atomic writes** for projects and outputs; project recovery after power loss.
8. **Chaos tests**: automated tests that inject failures (kill FFmpeg mid-render, corrupt cache, fill the disk quota, block network, bad captions) and assert the app recovers or fails with a helpful message. These must pass in CI.

## 8. PERFORMANCE RULES

Cache everything expensive by content hash. Download only what is needed. Analyze audio once at 16 kHz mono. Downscaled proxies for analysis and editor preview. Stream results to the UI as they arrive. Lazy-load editor panels. Virtualize long lists. Bound memory (stream frames, never hold full videos). `make bench` prints stage timings and fails the build on >20% regression. Include a **low-spec benchmark profile** (limit to 2 cores and 4 GB RAM in a container) and keep it passing.

## 9. MONETIZATION HOOKS (build the free core fully; make these cleanly separable, off by default for the open-source build)

Open-core design: everything above is free forever. Add a `pro/` extension point with a **license-key check** (offline-verifiable signed keys, no phone-home required) for optional paid extras I can sell: extra caption style packs and templates, brand kits (saved logo/fonts/colors), batch queue for many videos, watch-a-channel auto-clipping, direct publishing/scheduling (TikTok/YouTube/Instagram OAuth), multi-speaker tracking, and priority support. Also a "Done-for-you" landing page template and a sponsor/donate link in the app. Keep the core honest: no nagging, no feature crippling.

## 10. QUALITY BAR

Type hints, small functions, docstrings explaining each algorithm and its formula. Unit tests with synthetic fixtures (generated audio, fake word lists, tiny FFmpeg-made videos). Golden-file tests for ASS and for FFmpeg command generation. Property tests for caption timing. Editor tests (Playwright): load clip, split, trim, move caption, undo/redo, export, and verify the output duration and that captions are visible. Accessibility: keyboard navigation, contrast, reduced motion. Structured logs with a one-click "copy diagnostics" button.

## 11. CROSS-PLATFORM PROOF

You may only have one OS locally. Therefore: a CI matrix on Windows, macOS and Ubuntu that (1) runs unit and e2e tests, (2) executes the real install scripts in clean runners, (3) renders a sample clip end-to-end and checks the output with ffprobe (resolution 1080×1920, duration within ±0.5 s, audio present, loudness in range), and (4) runs `maxclipper doctor`. Handle Windows specifics explicitly: paths with spaces and non-ASCII characters, ASS font path escaping in FFmpeg filters, long paths, antivirus-locked files, PowerShell execution policy. Handle macOS specifics: Apple Silicon, Gatekeeper messages. Handle Linux specifics: missing codecs, headless servers.

## 12. DELIVERY PLAN (do in order; after each phase run tests, show me results, commit)

1. Scaffold, config, CI matrix, `maxclipper doctor`, health check.
2. Install scripts, automatic FFmpeg download, `maxclipper` command, first-run self-test.
3. Ingest, caching, download fallback ladder.
4. Signal, text and selection modules with tests, plus calibration tool.
5. Captions (ASS), safe zones, style library.
6. Reframing.
7. Render engine, hardware detection, SSE progress, benchmarks.
8. Resilience engine (Section 7) with chaos tests, wired through all stages.
9. API, wizard, processing view, results page.
10. Editor: Project JSON, timeline, tools, preview, export compiler, preview/export match tests.
11. Hardening, accessibility, docs, release workflow, v0.1.0 release candidate.
12. Pro extension point (license keys) and docs for selling.

## 13. DEFINITION OF DONE

- On a clean Windows, macOS and Linux runner, one pasted command installs MaxClipper and `maxclipper` opens the app with no manual steps (proven by CI logs).
- Paste a YouTube link, answer or skip the wizard, and get 5–10 ranked 9:16 clips with word-accurate captions inside platform safe zones, each with visible reasons for its score.
- Every clip opens in the editor and all features in 3.5 work; export matches the preview.
- A 45 s clip renders in under 30 s on a 4-core CPU; the low-spec profile still completes without freezing the UI (report real numbers in `BENCHMARKS.md`).
- All chaos tests pass; no unhandled exception reaches the user.
- `make test`, `make bench`, CI matrix all green. README, TROUBLESHOOTING and CONTRIBUTING exist and are accurate, including honest known limits.

## 14. HOW TO WORK

Start with Phase 1 now. Before each phase write a short plan; after it run tests, show results, commit. Keep `DECISIONS.md` and `TODO.md` current. If requirements conflict, follow Hard Constraints first, then the Definition of Done. Prefer boring, proven solutions over clever ones. Never fake results. If something cannot be made to work, say so plainly, explain why, and propose the best alternative.
