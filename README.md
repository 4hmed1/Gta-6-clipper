# ClipForge

**Install-in-one-command. Turn any YouTube link into ready-to-post vertical Shorts — fully local, no account, no watermark.**

> ⚠️ **Fan-tool disclaimer**: ClipForge is an independent, unofficial tool. It is not affiliated with or endorsed by YouTube, TikTok, Instagram, or any third party. All trademarks are property of their respective owners. **You must have the rights to the videos you process** and must follow each platform's terms of service.

---

## What it does

Paste a YouTube link (or upload a local video). ClipForge finds the best moments, scores them with explainable reasons, burns kinetic captions, reframes to 9:16, and renders ready-to-post Shorts — all on your own machine. Nothing is uploaded. No AI, no cloud, no usage caps.

## One-command install

**macOS / Linux** (curl + sh):

```bash
curl -fsSL https://raw.githubusercontent.com/4hmed1/Gta-6-clipper/main/installers/install.sh | sh
```

**Windows** (PowerShell):

```powershell
irm https://raw.githubusercontent.com/4hmed1/Gta-6-clipper/main/installers/install.ps1 | iex
```

The installer creates an isolated virtual environment, installs ClipForge + dependencies, downloads a verified static FFmpeg if none is found, adds the `clipforge` command to your PATH, and runs a health check. No admin rights required.

Then run:

```bash
clipforge
```

It opens **http://localhost:3000** in your browser. From a different directory:

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

MIT. See `LICENSE`.# Gta-6-clipper
