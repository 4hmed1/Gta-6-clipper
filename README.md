<div align="center">

# 🎬 GTA 6 Clipper
### Free, Local-First Vertical Short Maker

**Turn any YouTube video or local file into ready-to-post 1080×1920 Shorts in minutes — fully offline, no AI, no account, no watermark.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![100% Local](https://img.shields.io/badge/local--first-100%25-green.svg)](https://github.com/max/viralforge-ai)

[**Quickstart**](#-quickstart) •
[**Features**](#-features) •
[**How It Works**](#-how-it-works) •
[**Developer Setup**](#-developer-setup) •
[**Architecture**](#-architecture)

</div>

---

> ⚠️ **Disclaimer**: GTA 6 Clipper is an independent, unofficial tool. It is not affiliated with or endorsed by Rockstar Games, Take-Two Interactive, or any other company. All game names and trademarks are property of their respective owners. Users must have the rights to the videos they process and follow platform terms of service.

---

## ⚡ Highlights

- **100% free & unlimited** — no subscriptions, no usage caps, no watermarks
- **Explainable clip scoring** — every clip shows a score and the reasons (hooks, speech pacing, energy)
- **Runs on weak PCs** — designed for 4th-gen Intel i5, 8 GB RAM, no GPU
- **Self-healing pipeline** — automatically retries with fallbacks when YouTube blocks downloads
- **Deterministic** — same input always produces the same output, no random AI
- **No cloud, no upload, no telemetry** — everything runs on your machine

---

## 🎯 Features

- 📥 **Paste or Upload** — YouTube URLs or local MP4/MOV files
- 🎙️ **Word-Level Timestamps** — from YouTube captions or optional offline Whisper (faster-whisper)
- 📊 **Hook & Retention Scoring** — heuristic analysis of speech pacing, keywords, and energy
- ✨ **Kinetic Captions** — 8+ animated subtitle styles burned directly into the video
- 🎬 **Smart Re-framing** — auto face-tracking, blur-fit, or center-crop for 9:16
- 🖥️ **In-Browser Studio** — visual progress, clip cards with scores, download-all button
- 🛡️ **Player Client Fallback** — tries multiple download methods when YouTube blocks

---

## 🚀 Quickstart

### Prerequisites

Make sure **FFmpeg** is installed:

- **Ubuntu/Debian**: `sudo apt update && sudo apt install -y ffmpeg`
- **macOS**: `brew install ffmpeg`
- **Windows**: `winget install Gyan.FFmpeg`

### One-Command Install (macOS / Linux)

```bash
git clone https://github.com/max/viralforge-ai.git
cd viralforge-ai
./run.sh
```

The app opens automatically at **http://localhost:3000**.

### One-Command Install (Windows)

```powershell
git clone https://github.com/max/viralforge-ai.git
cd viralforge-ai
run.bat
```

### Manual Install

```bash
python3 -m venv venv
source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
clipforge                    # or: python -m clipforge.cli
```

### CLI Commands

```bash
clipforge              # Start the web studio (auto-opens browser)
clipforge doctor       # Check FFmpeg, yt-dlp, encoders, disk space
clipforge --port 8080  # Use a different port
clipforge --no-browser # Don't open the browser automatically
```

---

## 🧠 How It Works

```
  ┌──────────┐
  │  YouTube  │  or  Local File
  │   URL     │
  └────┬─────┘
       │
  ┌────▼────────────────┐
  │  1. Metadata Fetch   │  yt-dlp --dump-json (title, duration, caption tracks)
  └────┬────────────────┘
       │
  ┌────▼────────────────┐
  │  2. Audio Download   │  Low-bitrate WAV for analysis (~2 MB for 3-min video)
  └────┬────────────────┘
       │
  ┌────▼────────────────┐
  │  3. Transcription    │  Word-level timestamps (YouTube captions or faster-whisper)
  └────┬────────────────┘
       │
  ┌────▼────────────────┐
  │  4. Clip Selection   │  Sliding windows over sentence boundaries, scored by hooks,
  │                      │  speech density, energy. Deterministic. No AI.
  └────┬────────────────┘
       │
  ┌────▼────────────────┐
  │  5. Video Download   │  Full video at low quality (480p), player client fallback
  └────┬────────────────┘
       │
  ┌────▼────────────────┐
  │  6. Render Clips     │  FFmpeg: 1080×1920, kinetic captions, blur reframing, loudnorm
  └────┬────────────────┘
       │
  ┌────▼────────────────┐
  │  Web Studio Results  │  Ranked clip cards, preview, download-all, re-render
  └─────────────────────┘
```

---

## 💻 Developer Setup

```bash
# Clone and enter
git clone https://github.com/max/viralforge-ai.git
cd viralforge-ai

# Create venv and install
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev,stt]"

# Run
pip install -e .
clipforge --no-browser
```

### Project Structure

```
├── app/                # FastAPI backend
│   ├── main.py         # API routes + pipeline orchestrator
│   ├── downloader.py   # yt-dlp wrapper
│   ├── transcriber.py  # Caption & whisper transcription
│   ├── viral_detector.py # Heuristic clip scoring
│   ├── video_engine.py   # FFmpeg render (1080×1920)
│   └── clip_editor.py    # Re-export with adjusted settings
├── clipforge/          # CLI entry point
│   └── cli.py          # clipforge/gta6-clipper command
├── static/             # Bundled web frontend
│   ├── index.html      # Studio UI
│   ├── js/app.js       # Frontend logic
│   └── css/style.css   # Tailwind-like dark theme
├── outputs/clips/      # Generated short videos
├── downloads/          # Cached source files
└── config/             # Scoring weights (YAML)
```

### Key Files

| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI routes + full pipeline worker |
| `app/brand.py` | Single source-of-truth for app name & disclaimer |
| `app/downloader.py` | yt-dlp integration with player client ladder |
| `app/transcriber.py` | YouTube captions + faster-whisper fallback |
| `app/viral_detector.py` | Deterministic scoring: hooks, speech density, energy |
| `app/video_engine.py` | FFmpeg filter graph: captions, reframing, loudnorm |
| `clipforge/cli.py` | `clipforge` and `gta6-clipper` CLI commands |

---

## 📐 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Web Studio (React/Vanilla JS)                               │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────┐ │
│  │  Create Tab  │  │ Library Tab │  │ Settings Tab         │ │
│  │  URL / File  │  │ Video Cards │  │ Theme, output, etc.  │ │
│  │  Settings    │  │ Clip Grid   │  │                      │ │
│  └──────┬───────┘  └──────┬──────┘  └──────────────────────┘ │
│         │                 │                                   │
│         ▼                 │                                   │
│  ┌─────────────────────┐  │                                   │
│  │  FastAPI Backend     │◄┘                                   │
│  │  ┌─────────────────┐ │                                    │
│  │  │ Pipeline Worker │ │  Background task, progress via WS  │
│  │  │ Ingest → Audio  │ │                                    │
│  │  │ → Transcribe    │ │                                    │
│  │  │ → Select        │ │                                    │
│  │  │ → Download      │ │                                    │
│  │  │ → Render        │ │                                    │
│  │  └─────────────────┘ │                                    │
│  └─────────────────────┘                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔒 Privacy

- **Zero telemetry** — nothing leaves your machine except the YouTube API request for metadata
- **Zero upload** — videos are downloaded to your disk and processed locally
- **No accounts** — no sign-up, no login, no tracking
- **Optional offline STT** — faster-whisper runs entirely on your GPU/CPU

---

## 📄 License

Distributed under the **MIT License**. See `LICENSE` for details.
