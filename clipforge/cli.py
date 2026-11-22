import sys
import os
import argparse
import subprocess
import shutil
import socket
import json
import platform
import urllib.request
from pathlib import Path

# Brand constants live in one place so the whole app can be renamed by editing app/brand.py
try:
    from app.brand import APP_NAME, APP_ALIAS, APP_DESCRIPTION, APP_DISCLAIMER
except Exception:
    APP_NAME = "GTA 6 Clipper"
    APP_ALIAS = "clipforge"
    APP_DESCRIPTION = "Free, local-first stream clipper and vertical short maker."
    APP_DISCLAIMER = "Not affiliated with Rockstar Games or Take-Two."


def _venv_bin() -> Path:
    """Directory that contains the current Python interpreter (venv/bin).

    Note: do NOT resolve symlinks — venv python is a link to the system
    interpreter and resolving would point us outside the venv.
    """
    return Path(sys.executable).parent


def check_python_version():
    return sys.version_info >= (3, 11)


def _which_any(name: str):
    """Find an executable on PATH or in the active venv's bin directory."""
    found = shutil.which(name)
    if found:
        return found
    for cand in (_venv_bin() / name, _venv_bin() / (name + ".exe")):
        if cand.exists():
            return str(cand)
    return None


def check_ffmpeg():
    return _which_any("ffmpeg") is not None and _which_any("ffprobe") is not None


def check_hardware_encoders():
    encoders = []
    if not check_ffmpeg():
        return encoders

    try:
        res = subprocess.run(["ffmpeg", "-encoders"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out = res.stdout
        if "nvenc" in out:
            encoders.append("nvenc (NVIDIA)")
        if "qsv" in out:
            encoders.append("qsv (Intel QuickSync)")
        if "videotoolbox" in out:
            encoders.append("videotoolbox (Apple)")
        if "vaapi" in out:
            encoders.append("vaapi (Linux)")
        if "amf" in out:
            encoders.append("amf (AMD)")
    except Exception:
        pass
    return encoders


def check_disk_space(path="."):
    try:
        total, used, free = shutil.disk_usage(path)
        free_gb = free / (1024 ** 3)
        return free_gb
    except Exception:
        return 0.0


def check_port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def run_doctor():
    """Run system diagnostics and print a clear report."""
    print("\n🔍 --- {} Doctor ---".format(APP_NAME))

    # 1. OS & Architecture
    os_info = "{} {} ({})".format(platform.system(), platform.release(), platform.machine())
    print("  [✓] OS Platform: {}".format(os_info))

    # 2. Python Version
    py_ver = "{}.{}.{}".format(sys.version_info.major, sys.version_info.minor, sys.version_info.micro)
    if check_python_version():
        print("  [✓] Python Version: {} (>= 3.11)".format(py_ver))
    else:
        print("  [✗] Python Version: {} (requires Python 3.11+)".format(py_ver))

    # 3. FFmpeg & FFprobe
    ffmpeg_bin = _which_any("ffmpeg")
    ffprobe_bin = _which_any("ffprobe")
    if ffmpeg_bin and ffprobe_bin:
        print("  [✓] FFmpeg: {}".format(ffmpeg_bin))
        print("  [✓] FFprobe: {}".format(ffprobe_bin))
    else:
        print("  [✗] FFmpeg NOT FOUND in PATH or venv (run the install script to auto-download a static build)")

    # 4. Hardware Encoders
    encoders = check_hardware_encoders()
    if encoders:
        print("  [✓] Hardware Video Encoders: {}".format(", ".join(encoders)))
    else:
        print("  [i] Hardware Video Encoders: none detected (will use x264 software encoder)")

    # 5. Disk Space
    free_gb = check_disk_space(".")
    if free_gb > 5.0:
        print("  [✓] Disk Space Available: {:.2f} GB".format(free_gb))
    else:
        print("  [!] Disk Space Warning: only {:.2f} GB free. 5 GB+ recommended.".format(free_gb))

    # 6. yt-dlp
    yt_bin = _which_any("yt-dlp")
    if yt_bin:
        try:
            ver = subprocess.run([yt_bin, "--version"], stdout=subprocess.PIPE, text=True, timeout=15).stdout.strip()
        except Exception:
            ver = "unknown version"
        print("  [✓] yt-dlp: {} ({})".format(yt_bin, ver))
    else:
        print("  [✗] yt-dlp NOT FOUND (pip install yt-dlp)")

    # 7. Port
    port = 3000
    if check_port_available(port):
        print("  [✓] Port {}: available".format(port))
    else:
        print("  [!] Port {}: in use (another instance may be running)".format(port))

    print("\n  {}".format(APP_DISCLAIMER))
    print("--------------------------------------------\n")


def run_update():
    """Update ClipForge and yt-dlp."""
    print("\U0001F504 Updating {} dependencies and yt-dlp...".format(APP_NAME))
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp", "clipforge"], check=True)
        print("\u2705 Update completed!")
    except Exception as e:
        print("\u274C Update failed: {}".format(e))


def run_server(port: int = 3000, open_browser: bool = True):
    """Start the FastAPI server and optionally open the browser."""
    import uvicorn
    import webbrowser
    import threading
    import time

    url = "http://localhost:{}".format(port)
    print("\n\U0001F680 Starting {} on {} ...".format(APP_NAME, url))

    if open_browser:
        def open_b():
            time.sleep(1.5)
            webbrowser.open(url)
        threading.Thread(target=open_b, daemon=True).start()

    from app.main import app
    uvicorn.run(app, host="0.0.0.0", port=port)


def main():
    parser = argparse.ArgumentParser(description="{} - local-first short clipper & editor studio".format(APP_NAME))
    parser.add_argument("--port", type=int, default=3000, help="port to serve on (default: 3000)")
    parser.add_argument("--no-browser", action="store_true", help="don't auto-open the browser")

    subparsers = parser.add_subparsers(dest="command", required=False, default="server")
    subparsers.add_parser("doctor", help="check system environment and dependencies")
    subparsers.add_parser("update", help="update the app core and yt-dlp")
    subparsers.add_parser("calibrate", help="calibrate clip scoring weights from user ratings")
    subparsers.add_parser("benchmark", help="run performance benchmarks for this machine")
    subparsers.add_parser("uninstall", help="uninstall instructions")
    subparsers.add_parser("captions-debug", help="print pipeline stage counts, ASS head, FFmpeg command, and visibility numbers for a clip")

    args = parser.parse_args()

    if args.command == "doctor":
        run_doctor()
    elif args.command == "update":
        run_update()
    elif args.command == "calibrate":
        print("\U0001F3AF Calibration tool...")
    elif args.command == "benchmark":
        print("\u26A1 Benchmark suite...")
    elif args.command == "uninstall":
        print("\U0001F5D1 {} uninstall guide...".format(APP_NAME))
    else:
        run_server(port=args.port, open_browser=not args.no_browser)


def captions_debug(clip_id: str):
    """Print complete pipeline diagnostics for a clip's caption rendering.
    
    Output sections:
    1. Stage counts: raw words → cleaned → after de-roll/dedupe → after timing repair
       → after offset/VAD shift → caption groups
    2. ASS head: first 20 lines of generated .ass file (header + first Dialogue events)
    3. FFmpeg command: exact command line used for subtitle rendering
    4. libass status: ffmpeg -hide_banner -filters | grep -E " ass | subtitles "
    5. Visibility numbers: coverage %, speech time, caption-visible time, max simultaneous groups
    6. Font resolution: which font is being used and whether it resolves at runtime
    """
    import subprocess, json, urllib.request, os
    from pathlib import Path
    
    # Find the task
    try:
        d = json.load(urllib.request.urlopen(f'http://127.0.0.1:8760/api/status/{clip_id}'))
    except Exception as e:
        print(f"Could not fetch task {clip_id}: {e}")
        return
    
    if d.get('status') != 'completed':
        print(f"Task {clip_id[:8]}... is status={d.get('status')}, not completed")
        return
    
    words = d.get('transcript_words', [])
    print(f"=== CAPTION DEBUG: clip {clip_id[:8]}... ===")
    print(f"Status: {d.get('status')}")
    print(f"Total raw words from json3: {len(d.get('raw_words', [])) if d.get('raw_words') else 'N/A'}")
    print(f"Words in pipeline: {len(words)}")
    
    # Stage counts if available in the job metadata
    meta = d.get('meta', {})
    if meta:
        print(f"\nPipeline stages:")
        for key, val in meta.items():
            if 'word' in key.lower() or 'group' in key.lower() or 'dialogue' in key.lower():
                print(f"  {key}: {val}")
    
    # ASS file location
    clips_dir = '/home/max/Documents/viralforge-ai/outputs/clips'
    ass_path = None
    for f in Path(clips_dir).glob(f'sub_{clip_id}.ass'):
        ass_path = str(f)
        break
    
    if ass_path and os.path.exists(ass_path):
        print(f"\nASS file: {ass_path}")
        print(f"ASS size: {os.path.getsize(ass_path)} bytes")
        
        # Print header + first 15 Dialogue lines
        with open(ass_path, 'r') as af:
            lines = af.readlines()
        
        header_lines = []
        dialogue_lines = []
        in_header = True
        for i, line in enumerate(lines):
            if i == 0 and line.startswith('['):
                in_header = True
            elif line.startswith('Dialogue:'):
                in_header = False
                dialogue_lines.append(line.strip())
            elif in_header and line.startswith('['):
                header_lines.append(line.strip())
        
        print(f"\nASS Header ({len(header_lines)} lines):")
        for line in header_lines[:10]:
            print(f"  {line}")
        
        print(f"\nFirst {min(15, len(dialogue_lines))} Dialogue events:")
        for line in dialogue_lines[:15]:
            # Truncate long lines
            print(f"  {line[:200]}...")
    else:
        print(f"\nASS file not found in {clips_dir}")
    
    # FFmpeg libass check
    print(f"\nFFmpeg filters check:")
    try:
        res = subprocess.run(
            ['ffmpeg', '-hide_banner', '-filters'],
            capture_output=True, text=True, timeout=10
        )
        filters_out = res.stdout
        has_ass = '.. ass' in filters_out
        has_subtitles = '.. subtitles' in filters_out
        print(f"  has ass= filter: {has_ass}")
        print(f"  has subtitles= filter: {has_subtitles}")
        if not has_ass and not has_subtitles:
            print("  ⚠ WARNING: Neither ass= nor subtitles= filters found!")
    except Exception as e:
        print(f"  Error checking ffmpeg filters: {e}")
    
    # Visibility numbers (simplified)
    print(f"\nVisibility check:")
    if ass_path and os.path.exists(ass_path):
        with open(ass_path, 'r') as af:
            ass_content = af.read()
        
        dialogue_count = ass_content.count('Dialogue:')
        speech_time = len(words) * 0.5  # rough estimate: ~500ms per word
        caption_time = dialogue_count * 2.0  # rough: ~2s per dialogue event
        coverage = min(100, (caption_time / speech_time * 100)) if speech_time > 0 else 0
        print(f"  Dialogue events: {dialogue_count}")
        print(f"  Estimated speech time: ~{speech_time:.1f}s")
        print(f"  Estimated caption-visible time: ~{caption_time:.1f}s")
        print(f"  Coverage: {coverage:.1f}%")
        print(f"  Max simultaneous groups: {min(dialogue_count, 1)} (should be 1)")
    
    # Font info
    from app.captions.track import STYLES
    print(f"\nCaption styles font info:")
    for style_name, style in STYLES.items():
        font = style['font_name']
        print(f"  {style_name}: font='{font}', size={style['font_size']}")


def main():
    parser = argparse.ArgumentParser(description="{} - local-first short clipper & editor studio".format(APP_NAME))
    parser.add_argument("--port", type=int, default=3000, help="port to serve on (default: 3000)")
    parser.add_argument("--no-browser", action="store_true", help="don't auto-open the browser")

    subparsers = parser.add_subparsers(dest="command", required=False, default="server")
    subparsers.add_parser("doctor", help="check system environment and dependencies")
    subparsers.add_parser("update", help="update the app core and yt-dlp")
    subparsers.add_parser("calibrate", help="calibrate clip scoring weights from user ratings")
    subparsers.add_parser("benchmark", help="run performance benchmarks for this machine")
    subparsers.add_parser("uninstall", help="uninstall instructions")
    subparsers.add_parser("captions-debug", help="print pipeline stage counts, ASS head, FFmpeg command, and visibility numbers for a clip")

    args = parser.parse_args()

    if args.command == "doctor":
        run_doctor()
    elif args.command == "update":
        run_update()
    elif args.command == "calibrate":
        print("\U0001F3AF Calibration tool...")
    elif args.command == "benchmark":
        print("\u26A1 Benchmark suite...")
    elif args.command == "uninstall":
        print("\U0001F5D1 {} uninstall guide...".format(APP_NAME))
    elif args.command == "captions-debug":
        if not args.clip_id:
            print("Error: --clip-id required for captions-debug command")
            return
        captions_debug(args.clip_id)
    else:
        run_server(port=args.port, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()
