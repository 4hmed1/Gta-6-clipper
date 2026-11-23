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
    uvicorn.run(app, host="127.0.0.1", port=port)



def run_uninstall():
    import shutil
    from pathlib import Path
    import platformdirs
    base = Path.home() / ".maxclipper"
    link = Path.home() / ".local" / "bin" / "maxclipper"
    if input("Remove Max Clipper (" + str(base) + ") and the maxclipper command? [y/N] ").strip().lower() != "y":
        print("Cancelled.")
        return
    shutil.rmtree(base, ignore_errors=True)
    try:
        link.unlink()
    except FileNotFoundError:
        pass
    data = Path(platformdirs.user_data_dir("MaxClipper"))
    if data.exists() and input("Also delete your videos and clips in " + str(data) + "? [y/N] ").strip().lower() == "y":
        shutil.rmtree(data, ignore_errors=True)
    print("Max Clipper was removed.")


def main():
    import argparse
    from importlib.metadata import version as _pkg_version, PackageNotFoundError

    argv = [a for a in sys.argv[1:] if a.strip()]
    parser = argparse.ArgumentParser(prog="maxclipper", description="Max Clipper - turn long videos into ready-to-post Shorts, locally.")
    parser.add_argument("--version", action="store_true", help="show the version and exit")
    parser.add_argument("--port", type=int, default=3000, help="port to serve on (default: 3000)")
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("server", help="start Max Clipper (same as running it with no command)")
    sub.add_parser("doctor", help="check your system and dependencies")
    sub.add_parser("update", help="update Max Clipper and yt-dlp")
    sub.add_parser("uninstall", help="remove Max Clipper")
    args = parser.parse_args(argv)

    if args.version:
        try:
            v = _pkg_version("maxclipper")
        except PackageNotFoundError:
            v = "unknown"
        print("Max Clipper " + v)
        return
    if args.command == "doctor":
        run_doctor()
    elif args.command == "update":
        run_update()
    elif args.command == "uninstall":
        run_uninstall()
    else:
        run_server(port=args.port, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()
