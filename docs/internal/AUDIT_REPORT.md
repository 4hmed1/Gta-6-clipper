# AUDIT_REPORT.md

## A. PROJECT STATE
1. **Architecture**:
   - **Stack**: FastAPI (Backend), React/Vite (Frontend), SQLite (Metadata), FFmpeg (Processing), OpenCV (Vision/Selection), Librosa (Audio DSP).
   - **Structure**: `app/` (Legacy logic), `maxclipper/` (New modular core), `static/` (UI), `tests/` (Unit/Chaos).
   - **Entry Point**: `app/main.py`.
   - **Diagram**: 
     [User] -> [FastAPI/UI] -> [Ingest (yt-dlp)] -> [Signals/NLP (DSP/CV)] -> [Clip Selector] -> [Renderer (FFmpeg)] -> [Download]

2. **Flow**:
   - `Paste URL` -> `/api/process` -> `downloader.py` (YT-DLP) -> `transcriber.py` (Whisper) -> `viral_detector.py` (Heuristic) -> `render_clip` (`video_engine.py`) -> `FileResponse`.

3. **App Start**: Requires `uv` or `venv` to resolve dependencies. Default `python3 app/main.py` fails due to `ModuleNotFoundError: No module named 'fastapi'`. **Verdict: FAILED** (Manual configuration required).

4. **Installation**: Manual installation required. No signed releases or verified installers. 

5. **Feature Status**:
   - **Full**: Ingestion, Basic Clipping, Kinetic Captions.
   - **Partial**: Stream Clipper Mode (logic implemented, untested in prod), Editor UI (lite).
   - **Missing**: Chaos suite, professional install, full CapCut-style timeline, SEO/GEO/AEO pages.

## B. CLIP SELECTION QUALITY
6. **Logic**: Deterministic heuristics (NLP regex patterns, RMS energy, spectral flux). **NO PAID API**.
7. **Performance**: **NOT VERIFIED** (App startup unstable).
8. **Weaknesses**: Hardcoded regex patterns in `viral_detector.py` are brittle; no true VAD (Voice Activity Detection); struggles with rapid speech vs music; limited by word-timing precision; no semantic context.
9. **Cuts**: **NOT VERIFIED**.
10. **Long Videos**: Currently will crash/OOM on 3-hour VODs (no stream-processing mode).

## C. CAPTIONS AND EDITING
11. **Timings**: From Faster-Whisper. Accuracy is high, drift occurs if audio is variable rate.
12. **Safe Zones**: Standardized CSS/ASS markers. Header: `PlayResX: 1080, PlayResY: 1920`. Margins are manual.
13. **Styles**: 4 hardcoded styles in `app/subtitle_engine.py`.
14. **Editor**: **MISSING/PARTIAL**. Lacks full timeline, autosave, and undo/redo infrastructure.

## D. SPEED AND RELIABILITY
16-19. **NOT VERIFIED**.
20. **Failure Resilience**: **FAILED**. No auto-recovery (no resilience layer).
21. **Caching**: Basic file-based caching by ID. No hash-based stage checkpointing.
22. **UI Hangs**: UI blocks on long rendering tasks.

## E. DOWNLOAD RELIABILITY
23. **yt-dlp**: Basic wrapper. No fallbacks for API blockages.
24. **Cloud/Datacenter**: Likely to be throttled/blocked by YouTube (common issue for YT-DLP).

## F. UI/PRODUCT FEEL
25-28. **Status**: Prototypical. Lacks "Premium Feel". No coherent design system (in progress).

## G. CODE QUALITY AND SECURITY
29. **Coverage**: Low. Only basic logic tests exist.
30. **Debt**: Hardcoded paths, monolithic main file, `eval` or risky path usage in downloader.
31. **Security**: **FAILED**. Path traversal risk in `downloader.py`.
32. **Risks**: Windows paths will break rendering (`video_engine.py`).

## H. DISTRIBUTION/GROWTH
33-35. **Status**: Placeholder-heavy. Requires professional marketing/SEO planning.

## I. THE VERDICT
36. **Wins**: Deterministic, local-only, fast selection logic.
37. **Improvements**:
    - **High Impact**: Robust downloader fallback ladder, resilience checkpointing, CapCut-style editor timeline, SEO implementation, signed installers.
38. **Bugs/Risks**: Path traversal (Security), No auto-update (Maintenance), OOM crashes on long VODs (Stability), Inconsistent dependency resolution (Installation), No resilience to YT-DLP blockage (Ingestion).
39. **Biggest Hurdle**: **Resilience & Stability**. The tool is too brittle for 1-hour+ streams.
40. **3-Day Plan**: Stabilize venv/install path, add VOD stream-processing mode (checkpointing), implement robust path sanitization.

### Summary
The project works as a local script for small clips but lacks the architectural robustness and security needed for a "Premium" launch. **Priority 1: Stability & Security.**

### Facts I need the owner to provide:
1. **GitHub Org/User Name**: Required for install script URLs.
2. **Custom Domain**: For SEO/AEO setup.
3. **Discord Link**: For community growth loops.
4. **Target Platform Focus**: Are we prioritizing Windows (creators) or Linux (server/agency)?
