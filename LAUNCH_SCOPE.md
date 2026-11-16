# ClipForge Launch Scope & Release 0.1 Plan (LAUNCH_SCOPE.md)

## Release 0.1 "Launch Edition" Scope
- **One-Command Installers**: `install.sh` and `install.ps1` with automated FFmpeg verification.
- **CLI Commands**: `clipforge`, `clipforge doctor`, `clipforge update`, `clipforge calibrate`.
- **Ingest & Caching**: YouTube URL & local file support, yt-dlp wrapper with fallback ladders.
- **Stream Clipper Mode**: Chat replay parsing, heatmap metadata integration, audio signal detection (loudness/silence), game moment detector framework, and facecam region handling.
- **Selection & Scoring**: Deterministic moment scoring using RMS, spectral flux, pitch, and NLP hook scoring.
- **Captions & Reframing**: Kinetic ASS subtitles with word timings, platform safe zones, and smart face tracking.
- **Rendering & Resilience**: FFmpeg filtergraph pipeline, SSE progress streaming, and fault recovery.
- **UI & Frontend**: Modern dark-first React/Tailwind interface, step-by-step wizard, progressive results view, and lite editor.
- **SEO/GEO/AEO**: Static landing page in `/site`, `llms.txt`, and automated validation checks.

## Release 0.2 (Post-Launch)
- Full CapCut-style timeline editor.
- Advanced chaos test suite.
- Pro extension point (offline-verifiable signed licenses, preset packs).
