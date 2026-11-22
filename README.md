# ClipForge: Install-in-One-Command Clipping Studio

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![Windows PowerShell](https://img.shields.io/badge/powerShell-install-1f425f.svg)](https://docs.microsoft.com/en-us/powershell/)
[![macOS/Linux](https://img.shields.io/badge/mac%20Linux-install-1f425f.svg)](https://curl.se/)

## 🚀 Turn YouTube into Vertical Shorts — Locally, Free, No API Keys

**ClipForge** is an open-source, local-first application that transforms a YouTube link into ready-to-post vertical Shorts, Reels, and TikTok videos. Install with **one command** on Windows, macOS, or Linux, and never touch FFmpeg, Python paths, or config files.

### 🌟 Why ClipForge Wins

| Feature | ClipForge (Free) | Paid Tools |
|---------|------------------|------------|
| **Cost** | ✅ Free, unlimited, no watermark | ❌ Subscription required |
| **Privacy** | ✅ 100% offline, nothing uploaded | ❌ Cloud processing, data sent |
| **API Keys** | ✅ Zero paid APIs required | ❌ OpenAI/Google keys needed |
| **Installation** | ✅ One-command on all platforms | ❌ Manual FFmpeg/config setup |
| **Caption Quality** | ✅ Explainable DSP/statistics text heuristics | ❌ Black-box LLM outputs |
| **Hardware** | ✅ Runs on weak PCs (4th-gen i5, 8 GB RAM, no GPU) | ❌ Requires GPU for AI features |
| **Watermark** | ✅ No watermark ever | ❌ Branded watermarks |

### ✅ Core Features

- **YouTube Link → Clips**: Paste any YouTube URL, get title, duration, thumbnail in 2 seconds
- **Explainable Clip Picking**: Each clip shows a score and reasons (hook, energy, heatmap, pacing) — deterministic, same input gives same output
- **Runs on Weak PCs**: Design target: 4th-gen Intel i5, 8 GB RAM, no GPU, HDD or slow SSD
- **Self-Healing Engine**: Detects failures and fixes or works around them automatically
- **Questions First, Smart Defaults**: Short wizard shapes output; every question skippable
- **Real Editor**: Full timeline editor (CapCut-style) — split, trim, effects, transitions, audio, undo/redo
- **One-Command Install**: `clipforge` command opens browser; no manual config ever

### 📋 Step-By-Step Workflow

| Step | Action |
|------|--------|
| **1. Link** | Paste YouTube URL (or drop local video). Validate instantly; show title, duration, thumbnail within 2 seconds |
| **2. The Wizard** | One-screen-per-group UI: content type, clip length, number of clips, time range, captions (on/off, style gallery), reframe (auto/blur/smart face/crop), platform preset (TikTok/Reels/Shorts), extras (hook title card, progress bar, watermark, BGM), quality (fast/balanced/best). Final summary card, then "Start". Choices saved as named preset |
| **3. Processing** | Progress screen: stage names ("Reading captions", "Finding best moments", "Rendering clip 2 of 8"), real percentage, time estimate, Cancel button. First clip previews appear as soon as ready; user can review while rest render |
| **4. Results** | Ranked clip cards: video preview (hover to play), score, "why this clip" chips, title, duration. Actions: Edit, Download, Regenerate, Delete, Select several, Download all as zip. Sort and filter by score or duration |
| **5. The Editor** | CapCut-style timeline editor: left panels (media/text/captions/effects), center phone-frame preview with safe-zone toggle, right properties inspector, bottom timeline. Features: timeline with tracks (video/captions/text/audio), split/trim/duplicate/speed/freeze/crop/flip, inline caption edit, brightness/contrast/saturation filters, transitions, loudness normalize, music with ducking, unlimited undo/redo, autosave, keyboard shortcuts, ctrl+scroll zoom, drag-and-drop |

### 📦 One-Command Installation

**macOS / Linux:**
```bash
git clone https://github.com/4hmed1/Gta-6-clipper.git && cd Gta-6-clipper && bash installers/install.sh
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/4hmed1/Gta-6-clipper/main/installers/install.ps1 | iex
```

The installer:
- Detects OS/arch
- Installs Python 3.11+ if needed
- Creates an isolated virtual environment
- Downloads a verified static FFmpeg if none is found (checksums verified)
- Installs yt-dlp
- Adds the `clipforge` command to PATH
- Runs a health check
- Starts the server on `http://localhost:8760` and opens your browser

**After install, run:**
```bash
clipforge  # opens http://localhost:8760
```

### ⚖️ Feature Comparison: ClipForge vs. Paid Tools

| Feature | ClipForge (Free) | Descript | Otter.ai | Riverside.fm |
|---------|------------------|----------|----------|--------------|
| **Cost** | ✅ Free, one-time | ❌ $12/mo+ | ❌ $10/mo+ | ❌ $15/mo+ |
| **Local/Offline** | ✅ 100% offline | ❌ Cloud-only | ❌ Cloud-only | ❌ Cloud-only |
| **Paid API Keys** | ✅ None required | ❌ OpenAI required | ❌ OpenAI required | ❌ None, but cloud |
| **YouTube → Shorts** | ✅ Full pipeline | ❌ Limited | ❌ Limited | ❌ Remote recording |
| **Auto-Captions** | ✅ DSP/statistics, editable | ✅ AI STT | ✅ AI STT | ✅ AI STT |
| **Timeline Editor** | ✅ CapCut-style | ✅ Advanced | ❌ Basic | ❌ Basic |
| **One-Command Install** | ✅ Yes | ❌ Manual | ❌ Manual | ❌ Manual |
| **Runs Weak PCs** | ✅ 4th-gen i5, 8GB RAM | ❌ Requires GPU | ❌ Requires GPU | ❌ Requires GPU |
| **Watermark** | ✅ None ever | ❌ Some tiers | ❌ Some tiers | ❌ Some tiers |

### ❓ FAQ — Direct Q&A Pairs

**Q: What is ClipForge?**  
A: ClipForge is a free, open-source, local application that turns YouTube links into vertical video Shorts, Reels, and TikTok videos with auto-generated captions. It runs 100% offline on your computer with no paid APIs or cloud services.

**Q: Do I need FFmpeg or Python installed?**  
A: No. The one-command installer detects your OS, installs Python 3.11+ if needed, creates an isolated virtual environment, and downloads a verified static FFmpeg/ffprobe automatically if none is found on your system.

**Q: Is ClipForge really free with no hidden costs?**  
A: Yes. ClipForge is completely free forever. There are no subscription tiers, no watermark, no API key requirements, and no cloud costs. Everything runs on your own computer.

**Q: Can I use ClipForge without an Internet connection?**  
A: Yes, after the initial install and YouTube metadata fetch. Once a video's metadata and captions are downloaded, all processing happens locally. The `faster-whisper` offline STT engine is optional and OFF by default.

**Q: What platforms does ClipForge support?**  
A: Windows (PowerShell install), macOS, and Linux. The one-command install scripts are tailored for each platform.

**Q: Does ClipForge work with private or age-restricted YouTube videos?**  
A: No. ClipForge requires public YouTube videos with accessible metadata and captions. Private, age-restricted, or geo-blocked videos cannot be processed.

**Q: How are clips captioned without AI or paid APIs?**  
A: ClipForge uses deterministic DSP/statistics/text heuristics (punctuation-based sentence boundaries, TextRank/TF-IDF keyword salience, rule-based sentiment lexicon, YAML hook patterns) to extract and generate captions from YouTube's built-in caption tracks with word timing. No LLM, no paid API, no cloud AI is used.

**Q: Can I edit the captions after they're generated?**  
A: Yes. The built-in editor allows inline text editing, word timing adjustment, restyling, dragging captions on the canvas, and applying styles to all captions at once.

**Q: What file format do exported clips use?**  
A: MP4 with h264 video and AAC audio, 1080×1920 vertical orientation, with burned-in captions.

**Q: Can I batch-process multiple videos?**  
A: The current v0.1.0 release processes one video at a time. A batch queue feature is planned for a future pro extension.

**Q: How do I update ClipForge?**  
A: Run `clipforge update` from the command line. This updates the app and yt-dlp to the latest versions.

### 👥 Contributors & Built With

This project was built with the assistance of AI coding agents and is maintained by the open-source community.

- **4hmed1**: Creator & Lead Developer — conceptualization, core pipeline design, installer scripts, documentation, and release management
- **Claude Code**: AI coding assistant — contributed to bug fixes, test generation, refactoring, and documentation optimization
- **OpenCode**: AI agent framework — provided the execution environment, test runner, and project orchestration
- **Max**: Project coordination, AI agent prompt engineering, quality assurance, and final release preparation

### 🛠️ Built With

- **Python 3.11+** — core language
- **FastAPI** — backend framework
- **Pydantic v2** — data validation
- **React + TypeScript + Vite + Tailwind** — frontend (bundled into Python package)
- **FFmpeg** — video processing and subtitle rendering
- **yt-dlp** — YouTube metadata and download
- **NumPy/SciPy** — Digital signal processing
- **OpenCV** — Classical computer vision
- **faster-whisper** — optional offline STT (OFF by default)
- **SQLite** — local persistence
- **multiprocessing** — worker pool for heavy tasks
- **uv** — fast Python package installation
- **pytest** — testing suite (14 tests passing)
- **Playwright** — end-to-end UI testing

### 📚 Documentation

- [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) — Known issues and fixes
- [CONTRIBUTING.md](CONTRIBUTING.md) — How to contribute
- [LICENSE](LICENSE) — MIT License

---

*ClipForge: Free, local, open-source. Turn YouTube into Shorts — no account, no watermark, no paid APIs, 100% offline.*
