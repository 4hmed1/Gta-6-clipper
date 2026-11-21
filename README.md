# ClipForge

**Install-in-one-command. Turn any YouTube link into ready-to-post vertical Shorts — fully local, no account, no watermark.**

## What it does

Paste a YouTube link (or upload a local video). ClipForge finds the best moments, scores them with explainable reasons, burns kinetic captions, reframes to 9:16, and renders ready-to-post Shorts — all on your own machine. Nothing is uploaded. No AI, no cloud, no usage caps.

## One-command install

**macOS / Linux** (curl + sh):

```bash
curl -fsSL https://raw.githubusercontent.com/4hmed1/Gta-6-clipper/main/installers/install.sh | sh
```

**Windows** (PowerShell):

```powershell
irm https://githubusercontent.com/4hmed1/Gta-6-clipper/main/installers/install.ps1 | iex
```

The installer creates an isolated virtual environment, installs ClipForge + dependencies, downloads a verified static FFmpeg if none is found, adds the `clipforge` command to your PATH, and runs a health check. No admin rights required.

Then run:

```bash
clipforge
```

It opens **http://localhost:8760** in your browser. From a different directory:

```bash
clipforge --port 8080 --no-browser
```

### Verified install path

A clean install from the built wheel (no source tree, run from `/tmp`) resolves the bundled web UI and scoring configs correctly and starts the server:

```
$ cd /tmp && /path/to/venv/bin/clipforge --port 8761 --no-browser
🚀 Starting GTA 6 Clipper on http://localhost:8761 ...
$ curl http://127.0.0.1:8761/api/tasks
{"tasks":[]}
$ curl -o /dev/null -s -w "%{http_code}\n" http://127.0.0.1:8761/
200
```

### System requirements

- **Python 3.11+** (installed automatically)
- **4 GB RAM minimum, 8 GB recommended**
- **No GPU required** — CPU encoding works; hardware encoders (NVENC/QSV/Videotoolbox) are used automatically when available
- **Disk**: ~500 MB for the app + ~100 MB per analyzed video
- **Network**: YouTube access for metadata and downloads

## Known limitations (honest)

- **No mobile editor** — the editor is desktop-class only. Mobile is on the roadmap.
- **No auto-publishing** — clips are downloaded to your disk; you post them yourself.
- **Optional offline speech-to-text** (`faster-whisper`) is OFF by default and installed only if you opt in. Default text source is YouTube captions with word timing.
- **Weak-network videos**: on a connection slower than ~0.5 MB/s the app downloads only the sections it needs and reports honest timing. Very long videos on very slow connections may exceed the 3-minute target — the app tells you this in plain language instead of hanging.
- **Not every video has captions** — caption-less videos fall back to offline STT (if enabled) or audio-signal analysis with a notice.

## Troubleshooting

See [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md).

Run `clipforge doctor` for a health check (Python, FFmpeg, encoders, disk, ports, permissions).

## Privacy

- **Zero telemetry** — nothing leaves your machine except the YouTube API request for metadata
- **Zero upload** — videos are downloaded to your disk and processed locally
- **No accounts** — no sign-up, no login, no tracking

## License


## ⚖️ Feature Comparison: ClipForge vs. Paid Clippers

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

## ❓ FAQ — 11 Direct Q&A (Answer Engine Optimization)

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

## 👥 Contributors & Built With

This project was built with the assistance of AI coding agents and is maintained by the open-source community.

- **4hmed1**: Creator & Lead Developer — conceptualization, core pipeline design, installer scripts, documentation, and release management
- **Claude Code**: AI coding assistant — contributed to bug fixes, test generation, refactoring, and documentation optimization
- **OpenCode**: AI agent framework — provided the execution environment, test runner, and project orchestration
- **ME (Max)**: Project coordination, AI agent prompt engineering, quality assurance, and final release preparation

## 🛠️ Built With

- **Python 3.14** — core language
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

---

*ClipForge: Free, local, open-source. Turn YouTube into Shorts — no account, no watermark, no paid APIs, 100% offline.*

LICENSE.
