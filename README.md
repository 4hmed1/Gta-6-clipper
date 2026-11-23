# Max Clipper

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![macOS/Linux](https://img.shields.io/badge/mac%20Linux-install-1f425f.svg)](https://curl.se/)

## Turn YouTube into vertical Shorts — Locally, Free, No API Keys

**Max Clipper** is a free, local-first desktop application that transforms YouTube links into ready-to-post vertical Shorts, Reels, and TikTok videos. Install with one command on Windows, macOS, or Linux, and never touch FFmpeg, Python paths, or config files.

### Why Max Clipper

| Feature | Max Clipper (Free) | Paid Tools |
|---------|-------------------|------------|
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

### 🚀 One-Command Install

```bash
curl -fsSL https://raw.githubusercontent.com/4hmed1/MaxClipper/main/installers/install.sh | bash
```

Open a new terminal and type `maxclipper`, and open the link it shows.

### 📋 Requirements

- **Python**: 3.11 or newer
- **FFmpeg**: must be on PATH (install with: `sudo apt install ffmpeg` on Ubuntu/Debian, `brew install ffmpeg` on macOS)
- **OS**: Linux, macOS (Windows via WSL)
- **Disk**: 2 GB+ free space

### 🛠 Troubleshooting

Run `maxclipper doctor` to check your system environment and fix common issues.

If you get PATH errors, add `export PATH="$HOME/.local/bin:$PATH"` to `~/.bashrc` or `~/.zshrc`.

### 🔄 Update

```bash
maxclipper update
```
or re-run the install command.

### ✂ Uninstall

```bash
maxclipper uninstall
```
This removes `~/.maxclipper` and the `maxclipper` symlink. To keep your user data (clips, library), answer `n` when prompted.

### ⚠️ Disclaimer

Max Clipper is an unofficial, independent tool. It is not affiliated with or endorsed by Rockstar Games, Take-Two Interactive, or any other company. All game names, logos, and trademarks are the property of their respective owners. Users must have the rights to the videos they process and must follow platform terms of service.

### CHANGELOG

**7.1.0** — Fixed audio download order (local first, then yt-dlp, then captions), global render lock prevents concurrent FFmpeg starvation, stall-based timeout kills FFmpeg if no progress for 180s, faster preset on weak CPUs (`-threads 0`, `-preset ultrafast` if cpu_count <= 4), render queue with FIFO UI messages, read-only error messages never show raw commands, project renamed from ClipForge to Max Clipper.

7.0.0 — Initial release