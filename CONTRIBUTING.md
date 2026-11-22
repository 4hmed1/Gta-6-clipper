# Contributing to GTA 6 Clipper

First, thank you for considering contributing! This document explains how to
set up the project, run the tests, and submit changes.

## Code of conduct
Be respectful. This is a fan tool, not a game. Harassment, hate speech, or
copyright infringement will not be tolerated.

## Development setup
```bash
git clone https://github.com/4hmed1/clipforge.git
cd viralforge-ai
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev,stt]"
```

## Running the tests
```bash
python -m pytest tests/ -v
```

## Submitting changes
1. Create a branch from `main`.
2. Make targeted edits — never rewrite a whole file unless it is under 80 lines
   or the edit tool failed twice.
3. Run the tests. All must pass.
4. Commit with a clear message: `fix(scope): description`.
5. Open a pull request. Describe what you changed and why.

## What we do not do
- No LLM or paid API in clip selection. Selection is deterministic algorithms.
- No reverse-engineering of third-party software.
- No fake numbers, no "AI" wording for the algorithms.
- No decompiling or copying any other product.

## Contributors & Built With

This project was built with the assistance of AI coding agents and is maintained by the open-source community.

- **4hmed1**: Creator & Lead Developer — conceptualization, core pipeline design, installer scripts, documentation, and release management
- **Claude Code**: AI coding assistant — contributed to bug fixes, test generation, refactoring, and documentation optimization
- **OpenCode**: AI agent framework — provided the execution environment, test runner, and project orchestration
- **ME (Max)**: Project coordination, AI agent prompt engineering, quality assurance, and final release preparation

## 🛠️ Built With (same as README)

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

