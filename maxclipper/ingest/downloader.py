"""
MaxClipper YouTube Downloader Module
Handles YouTube metadata, caption track discovery, low-bitrate audio
downloads, and section-only video downloads with speed-adaptive
resolution.  Uses the yt-dlp Python API directly (no CLI shelling).

Priority order:
1. Fetch metadata + caption tracks only (tiny, <1 MB) — NEVER download
   the full video here
2. Download low-bitrate audio only for analysis (~64 kbps)
3. Download ONLY chosen sections via the download_ranges callback
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

import yt_dlp

from maxclipper.resilience import DownloadError


# Player clients to try in order when YouTube blocks / changes clients.
DEFAULT_PLAYER_CLIENTS = ["android", "web", "ios", "tv_embedded", "mweb"]


def _player_client_ladder() -> List[List[str]]:
    """Fallback ladder: try a small set of clients, widen, then widest."""
    return [
        ["android", "web"],
        ["android", "web", "ios"],
        DEFAULT_PLAYER_CLIENTS,
        DEFAULT_PLAYER_CLIENTS + ["tv", "mweb"],
    ]


class YTDLPDownloader:
    """Downloads YouTube metadata, audio and video sections with fallback ladders."""

    AUDIO_ONLY_FORMAT = "bestaudio[abr<=64]/bestaudio/worst"
    SLOW_NETWORK_MBPS = 0.5  # below this, request 480p sections

    def __init__(self, ffmpeg_path: Optional[str] = None):
        self.ffmpeg_path = ffmpeg_path

    # ── Shared option builder ─────────────────────────────────────
    def _base_opts(self, client_ladder: List[str]) -> Dict[str, Any]:
        opts: Dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "retries": 3,
            "fragment_retries": 3,
            "socket_timeout": 30,
            "extractor_args": {"youtube": {"player_client": client_ladder}},
        }
        if self.ffmpeg_path:
            opts["ffmpeg_location"] = self.ffmpeg_path
        return opts

    def _run_ydl(self, opts: Dict[str, Any], url: str):
        """Run a synchronous YoutubeDL extraction, walking the player-client
        fallback ladder.  Returns (info_dict, resolved_filename|None).
        Re-raises DownloadError if all ladders fail."""
        last_err: Optional[Exception] = None
        for clients in _player_client_ladder():
            try:
                o = dict(opts)
                o["extractor_args"] = {"youtube": {"player_client": clients}}
                with yt_dlp.YoutubeDL(o) as ydl:
                    info = ydl.extract_info(url, download=opts.get("_download", False))
                    fname = None
                    if info is not None and opts.get("_download", False):
                        try:
                            fname = ydl.prepare_filename(info)
                        except Exception:
                            fname = None
                    return info, fname
            except Exception as e:  # noqa: BLE001 - classify below
                last_err = e
                continue
        raise DownloadError(f"All yt-dlp client ladders failed: {last_err}")

    # ── Stage 1: metadata (no download) ──────────────────────────
    def get_metadata(self, url: str) -> Dict[str, Any]:
        """Fetch title, duration, thumbnail, caption track list. No media
        is downloaded.  Fast enough to show the card in ~2 s."""
        opts = self._base_opts(DEFAULT_PLAYER_CLIENTS)
        info, _ = self._run_ydl(opts, url)
        if info is None:
            raise DownloadError(f"Could not extract metadata for {url}")
        if "entries" in info:  # playlists
            raise DownloadError("Playlists are not supported — paste a single video URL.")

        caps = {**(info.get("captions") or {}), **(info.get("automatic_captions") or {})}
        return {
            "success": True,
            "video_id": info.get("id", ""),
            "title": info.get("title", "Untitled"),
            "duration": float(info.get("duration") or 0),
            "thumbnail": info.get("thumbnail", ""),
            "author": info.get("uploader", "Unknown"),
            "available_captions": sorted(caps.keys()),
            "heatmap_available": bool(info.get("view_count")),  # proxy flag
        }

    # ── Stage 2: low-bitrate audio (analysis) ────────────────────
    def download_audio(self, url: str, out_dir: Path,
                       progress_callback=None) -> Dict[str, Any]:
        """Download low-bitrate audio (~64 kbps) for DSP analysis.
        Measures and reports sustained speed via progress_callback."""
        out_dir.mkdir(parents=True, exist_ok=True)
        outtmpl = str(out_dir / "audio_%(id)s.%(ext)s")

        speed_window: List[tuple] = []  # (t, bytes) samples
        state = {"sustained_mbps": 0.0}

        def hook(d: Dict[str, Any]):
            if not progress_callback:
                return
            status = d.get("status")
            if status == "downloading":
                now = time.time()
                downloaded_window = [(t, b) for t, b in speed_window if now - t < 20]
                speed_window[:] = downloaded_window + [(now, d.get("downloaded_bytes", 0))]
                if len(speed_window) >= 2:
                    dt = speed_window[-1][0] - speed_window[0][0]
                    db = speed_window[-1][1] - speed_window[0][1]
                    if dt > 1:
                        state["sustained_mbps"] = db / dt / 1e6
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                done = d.get("downloaded_bytes", 0)
                if total:
                    pct = min(99.0, done / total * 100)
                    msg = (f"Downloading analysis audio… {pct:.0f}% "
                           f"({state['sustained_mbps']:.2f} MB/s sustained)")
                else:
                    msg = f"Downloading analysis audio… {done / 1e6:.1f} MB"
                progress_callback(msg)
            elif status == "finished":
                progress_callback("Analysis audio ready")

        opts = self._base_opts(DEFAULT_PLAYER_CLIENTS)
        opts["format"] = self.AUDIO_ONLY_FORMAT
        opts["outtmpl"] = outtmpl
        opts["progress_hooks"] = [hook]
        opts["_download"] = True

        info, final_file = self._run_ydl(opts, url)

        if final_file and Path(final_file).exists():
            return {
                "success": True,
                "filepath": final_file,
                "file_size_mb": round(Path(final_file).stat().st_size / 1e6, 2),
                "sustained_mbps": round(state["sustained_mbps"], 3),
            }
        
        # fallback finding logic moved up
        if not final_file and info:
             candidates = sorted(out_dir.glob(f"audio_{info.get('id')}*"), key=lambda p: p.stat().st_mtime, reverse=True)
             if candidates:
                 return {
                    "success": True,
                    "filepath": str(candidates[0]),
                    "file_size_mb": round(candidates[0].stat().st_size / 1e6, 2),
                    "sustained_mbps": round(state["sustained_mbps"], 3),
                }

        return {"success": False, "error": "Audio download produced no file",
                "sustained_mbps": round(state["sustained_mbps"], 3)}

    # ── Stage 3: chosen sections only ────────────────────────────
    def download_sections(self, url: str, sections: List[Dict[str, float]],
                          out_path: str, target_height: int = 720,
                          progress_callback=None) -> Dict[str, Any]:
        """Download only the requested [start, end] ranges from the video.
        This is the ONLY full-resolution download in the pipeline."""
        if not sections:
            return {"success": False, "error": "No sections requested"}

        ranges = [{"start_time": max(0.0, float(s["start"])),
                   "end_time": float(s["end"])} for s in sections if s.get("end", 0) > s.get("start", 0)]
        if not ranges:
            return {"success": False, "error": "Empty section ranges"}

        def range_cb(info, downloader):
            return ranges

        opts = self._base_opts(DEFAULT_PLAYER_CLIENTS)
        opts["format"] = f"best[height<={target_height}]+bestaudio/best[height<={target_height}]"
        opts["merge_output_format"] = "mp4"
        opts["outtmpl"] = out_path
        opts["download_ranges"] = range_cb
        opts["_download"] = True
        if progress_callback:
            opts["progress_hooks"] = [lambda d: self._section_progress(d, progress_callback)]

        try:
            _, final_file = self._run_ydl(opts, url)
        except DownloadError:
            raise
        except Exception as e:  # noqa: BLE001
            return {"success": False, "error": str(e)}

        if final_file and Path(final_file).exists():
             return {
                "success": True,
                "filepath": str(final_file),
                "file_size_mb": round(Path(final_file).stat().st_size / 1e6, 2),
                "sections": ranges,
            }
        
        # The merged file lands next to outtmpl with .mp4
        final = Path(out_path)
        if not final.exists() and final.with_suffix(".mp4").exists():
            final = final.with_suffix(".mp4")
        if final.exists():
            return {
                "success": True,
                "filepath": str(final),
                "file_size_mb": round(final.stat().st_size / 1e6, 2),
                "sections": ranges,
            }
        return {"success": False, "error": "Section download produced no file"}

    @staticmethod
    def _section_progress(d: Dict[str, Any], cb) -> None:
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes", 0)
            if total:
                cb(f"Downloading clip section… {done / total * 100:.0f}%")
            else:
                cb(f"Downloading clip section… {done / 1e6:.1f} MB")

    # Keep async wrappers for the pipeline (it runs them in a thread)
    async def get_metadata_async(self, url):
        return self.get_metadata(url)

    async def download_audio_async(self, url, out_dir, progress_callback=None):
        return self.download_audio(url, out_dir, progress_callback)

    async def download_sections_async(self, url, sections, out_path, target_height=720,
                                      progress_callback=None):
        return self.download_sections(url, sections, out_path, target_height,
                                      progress_callback)
