# ClipForge TODO List (TODO.md)

## Phase 1: Foundation (Completed)
- [x] Initialize `clipforge/` package structure.
- [x] `clipforge doctor` command and health check infrastructure.
- [x] CI/CD matrix setup (Windows, macOS, Ubuntu).
- [x] Move existing `app/` functionality into `clipforge/` structure, retaining core logic.

## Phase 2: Distribution (Completed)
- [x] `install.ps1` (PowerShell) and `install.sh` (Bash) installers.
- [x] Automated FFmpeg binary download & checksum verification.
- [x] `clipforge` CLI command entrypoint setup.
- [x] First-run self-test.

## Phase 3: Ingest & Resilience (Resilience Module)
- [ ] Pipeline checkpointing & idempotent state machine.
- [ ] Download fallback ladder (multiple yt-dlp clients, retries, local fallback).

## Phase 4: Algorithms (DSP, NLP, Select)
- [ ] DSP signal extraction (RMS/energy, spectral flux, pitch, VAD, scene cut detection).
- [ ] NLP Text heuristic/hook score pipeline (YAML rules).
- [ ] Clip Selection logic (NMS + diversity pass).
- [ ] `clipforge calibrate` CLI tool.

## Phase 5: Captions (ASS generation)
- [ ] Kinetic ASS generation pipeline (word timing, per-word highlight, pop animations).
- [ ] Style library and safe-zone presets.

## Phase 6: Visuals (Reframing)
- [ ] OpenCV Face/Motion tracking module (EMA/Kalman smoothing).
- [ ] Reframing fallback ladder.

## Phase 7: Rendering Engine
- [ ] FFmpeg single-filtergraph pipeline.
- [ ] Hardware encoder auto-detection (NVENC, QSV, etc.) with x264 fallback.
- [ ] SSE Progress streaming.

## Phase 8: Resilience Hardening
- [ ] Error classification system.
- [ ] Resource governance.
- [ ] Chaos testing suite.

## Phase 9: Wizard & API
- [x] Design system tokens (docs/DESIGN_SYSTEM.md) — colors, type, spacing, radius, shadows, motion
- [x] Create screen static layout (static/index.html) — app bar, tabs, headline, source input, all settings
- [x] App interaction logic (static/js/app.js) — paste detection, drag-drop, segmented controls, caption gallery, toggles, focus/time range, presets, video list with stepper + clip grid + overflow menu, toasts, confirm dialogs, polling, persistence
- [x] Backend wiring — ProcessRequest gains clip_count/length_min/length_max/aspect/caption_style/framing/hook_text/tighten_pauses/focus_text/range_start/range_end; detect_viral_clips accepts min/max/max_clips; new endpoints /api/validate, /api/tasks, /api/tasks/cancel, /api/videos/folder
- [x] UI verification — Playwright screenshots at 360/768/1440px dark+light (audit/screenshots/), UI_REPORT.md
- [ ] Processing status screen (stepper + clip grid + progress SSE)
- [ ] Results page (clip cards with scores, reasons, edit/download)
- [ ] Playwright e2e tests: link validation, settings payload, stepper state, clip grid, delete/cancel, keyboard nav
- [ ] Lighthouse accessibility ≥ 95, axe zero critical issues

## Phase 10: CapCut-like Editor
- [ ] Project JSON model.
- [ ] React-based timeline editor.
- [ ] FFmpeg export compiler.

## Phase 11: Release Candidate
- [ ] Accessibility audit.
- [ ] Docs (README, TROUBLESHOOTING, CONTRIBUTING).
- [ ] Final CI/CD pipeline verification.

## Phase 12: Pro Extension
- [ ] Offline-verifiable license key system.
