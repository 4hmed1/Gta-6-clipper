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

def check_python_version():
    return sys.version_info >= (3, 11)

def check_ffmpeg():
    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")
    return ffmpeg_path is not None and ffprobe_path is not None

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
            encoders.append("videotoolbox (Apple Silicon/Mac)")
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
        return s.connect_ex(('127.0.0.1', port)) != 0

def run_doctor():
    """Run clipforge doctor diagnostic checks."""
    print("\n🔍 --- ClipForge Doctor System Diagnostics ---")

    # 1. OS & Architecture
    os_info = f"{platform.system()} {platform.release()} ({platform.machine()})"
    print(f"  [✓] OS Platform: {os_info}")

    # 2. Python Version
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if check_python_version():
        print(f"  [✓] Python Version: {py_ver} (>= 3.11)")
    else:
        print(f"  [✗] Python Version: {py_ver} (ClipForge requires Python 3.11+)")

    # 3. FFmpeg & FFprobe
    if check_ffmpeg():
        ffmpeg_bin = shutil.which("ffmpeg")
        print(f"  [✓] FFmpeg Binary: Found at {ffmpeg_bin}")
    else:
        print("  [✗] FFmpeg Binary: NOT FOUND in PATH! (Run install script to auto-download)")

    # 4. Hardware Encoders
    encoders = check_hardware_encoders()
    if encoders:
        print(f"  [✓] Hardware Video Encoders Detected: {', '.join(encoders)}")
    else:
        print("  [i] Hardware Video Encoders: None detected (Falling back to high-performance x264 software encoder)")

    # 5. Disk Space
    free_gb = check_disk_space(".")
    if free_gb > 5.0:
        print(f"  [✓] Disk Space Available: {free_gb:.2f} GB")
    else:
        print(f"  [!] Disk Space Warning: Only {free_gb:.2f} GB free. At least 5 GB recommended for processing.")

    # 6. yt-dlp Status
    yt_dlp_bin = shutil.which("yt-dlp")
    if yt_dlp_bin:
        print(f"  [✓] yt-dlp Engine: Available at {yt_dlp_bin}")
    else:
        print("  [✗] yt-dlp Engine: NOT FOUND in PATH!")

    # 7. Port Check (default 3000)
    port = 3000
    if check_port_available(port):
        print(f"  [✓] Default Port {port}: Available")
    else:
        print(f"  [!] Default Port {port}: In use by another service.")

    print("--------------------------------------------\n")

def run_update():
    """Update ClipForge and yt-dlp."""
    print("🔄 Updating ClipForge dependencies and yt-dlp engine...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp", "clipforge"], check=True)
        print("✅ Update completed successfully!")
    except Exception as e:
        print(f"❌ Update failed: {e}")

def run_server(port: int = 3000, open_browser: bool = True):
    """Start FastAPI server and optionally open browser."""
    import uvicorn
    import webbrowser
    import threading
    import time

    url = f"http://localhost:{port}"
    print(f"\n🚀 Starting ClipForge Studio server on {url} ...")

    if open_browser:
        def open_b():
            time.sleep(1.5)
            webbrowser.open(url)
        threading.Thread(target=open_b, daemon=True).start()

    from app.main import app
    uvicorn.run(app, host="0.0.0.0", port=port)

def main():
    parser = argparse.ArgumentParser(description="ClipForge - Local-First AI Short Clipper & Editor Studio")
    parser.add_argument("--port", type=int, default=3000, help="Port to run server on (default: 3000)")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("doctor", help="Run system environment and dependency checks")
    subparsers.add_parser("update", help="Update ClipForge core and yt-dlp")
    subparsers.add_parser("calibrate", help="Calibrate clip scoring weights based on user ratings")
    subparsers.add_parser("benchmark", help="Run performance benchmarks for current hardware")
    subparsers.add_parser("uninstall", help="Uninstall ClipForge")

    args = parser.parse_args()

    if args.command == "doctor":
        run_doctor()
    elif args.command == "update":
        run_update()
    elif args.command == "calibrate":
        print("🎯 Calibration tool initialized...")
    elif args.command == "benchmark":
        print("⚡ Benchmark suite starting...")
    elif args.command == "uninstall":
        print("🗑️ ClipForge uninstall guide...")
    else:
        run_server(port=args.port, open_browser=not args.no_browser)

if __name__ == "__main__":
    main()
