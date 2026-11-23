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
    APP_NAME = "Max Clipper"
    APP_ALIAS = "maxclipper"
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
    """Update MaxClipper and yt-dlp."""
    print("\U0001F504 Updating {} dependencies and yt-dlp...".format(APP_NAME))
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp", "maxclipper"], check=True)
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
    parser = argparse.ArgumentParser(description=f"{APP_NAME} - local-first stream clipper & editor studio")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} 7.1.0")
    subparsers = parser.add_subparsers(dest="command", required=False)
    
    parser.set_defaults(command="server")
    subparsers.add_parser("doctor", help="check system environment and dependencies")
    subparsers.add_parser("update", help="update the app core and yt-dlp")
    subparsers.add_parser("server", help="start the web interface")
    
    args = parser.parse_args()
    
    if args.command == "doctor":
        run_doctor()
    elif args.command == "update":
        run_update()
    elif args.command == "server":
        port = 3000
        open_browser = True
        # TODO: allow --port and --no-browser flags
        run_server(port, open_browser)
    else:
        # Default to server
        run_server()

if __name__ == "__main__":
    main()

def main():
    parser = argparse.ArgumentParser(description=f"{APP_NAME} - local-first stream clipper & editor studio")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} 7.1.0")
    subparsers = parser.add_subparsers(dest="command", required=False)
    
    parser.set_defaults(command="server")
    subparsers.add_parser("doctor", help="check system environment and dependencies")
    subparsers.add_parser("update", help="update the app core and yt-dlp")
    subparsers.add_parser("server", help="start the web interface")
    
    args = parser.parse_args()
    
    if args.command == "doctor":
        run_doctor()
    elif args.command == "update":
        run_update()
    elif args.command == "server":
        port = 3000
        open_browser = True
        # TODO: allow --port and --no-browser flags
        run_server(port, open_browser)
    else:
        # Default to server
        run_server()

if __name__ == "__main__":
    main()
