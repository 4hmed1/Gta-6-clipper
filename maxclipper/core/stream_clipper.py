import json
import os
import numpy as np
from pathlib import Path

from .._config import package_config as _package_config
from typing import List, Dict, Any, Optional

class StreamClipperEngine:
    def __init__(self, config_path: str = ""):
        self.config_path = config_path or _package_config("stream_clipping.yaml")
        self.load_config()

    def load_config(self):
        p = Path(self.config_path)
        if p.exists():
            import yaml
            with open(p, "r") as f:
                self.config = yaml.safe_load(f)
        else:
            self.config = {
                "chat_spike_weight": 0.35,
                "heatmap_weight": 0.25,
                "audio_burst_weight": 0.25,
                "motion_weight": 0.15
            }

    def parse_live_chat(self, chat_json_path: str) -> np.ndarray:
        """
        Parse YouTube/Twitch live chat JSON logs and build message rate density timeline.
        Returns a time-binned numpy array of chat spike intensity (z-score normalized).
        """
        if not os.path.exists(chat_json_path):
            return np.array([])

        try:
            with open(chat_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            timestamps = []
            for msg in data.get("messages", []):
                t = msg.get("offset_seconds", msg.get("timestamp", 0))
                timestamps.append(float(t))

            if not timestamps:
                return np.array([])

            max_t = int(max(timestamps))
            binned = np.zeros(max_t + 1)
            for t in timestamps:
                if int(t) <= max_t:
                    binned[int(t)] += 1

            # Rolling window average & z-score
            window = 10
            kernel = np.ones(window) / window
            smoothed = np.convolve(binned, kernel, mode="same")

            mean = np.mean(smoothed)
            std = np.std(smoothed) + 1e-6
            z_scores = (smoothed - mean) / std
            return np.maximum(0, z_scores)
        except Exception as e:
            print(f"[StreamClipper] Chat parsing error: {e}")
            return np.array([])

    def fuse_signals(
        self,
        duration: float,
        chat_timeline: np.ndarray,
        heatmap_timeline: np.ndarray,
        audio_signals: Dict[str, np.ndarray]
    ) -> np.ndarray:
        """
        Fuse chat z-scores, YouTube heatmap, audio RMS, and spectral flux into a single
        moment-intensity timeline.
        """
        # Resample all to 1-second bins up to duration
        num_bins = int(duration)
        timeline = np.zeros(num_bins)

        # 1. Chat spikes
        if len(chat_timeline) > 0:
            chat_resampled = np.interp(
                np.linspace(0, len(chat_timeline)-1, num_bins),
                np.arange(len(chat_timeline)),
                chat_timeline
            )
            timeline += chat_resampled * self.config["chat_spike_weight"]

        # 2. Heatmap
        if len(heatmap_timeline) > 0:
            heat_resampled = np.interp(
                np.linspace(0, len(heatmap_timeline)-1, num_bins),
                np.arange(len(heatmap_timeline)),
                heatmap_timeline
            )
            timeline += heat_resampled * self.config["heatmap_weight"]

        # 3. Audio RMS/Flux
        if "rms" in audio_signals and len(audio_signals["rms"]) > 0:
            rms_arr = audio_signals["rms"]
            rms_resampled = np.interp(
                np.linspace(0, len(rms_arr)-1, num_bins),
                np.arange(len(rms_arr)),
                rms_arr
            )
            timeline += rms_resampled * self.config["audio_burst_weight"]

        return timeline

    def detect_stream_moments(
        self,
        timeline: np.ndarray,
        min_duration: float = 20.0,
        max_duration: float = 60.0,
        max_clips: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Detect peaks in the fused moment-intensity timeline and expand into clip windows.
        """
        if len(timeline) == 0:
            return []

        # Find local peaks above threshold
        threshold = np.mean(timeline) + 1.2 * np.std(timeline)
        moments = []

        for i in range(5, len(timeline) - 5):
            if timeline[i] > threshold and timeline[i] == np.max(timeline[i-5:i+6]):
                # Peak found at second i
                start = max(0, i - int(min_duration / 2))
                end = min(len(timeline), start + int(max_duration))

                moments.append({
                    "start": float(start),
                    "end": float(end),
                    "score": float(timeline[i] * 20),
                    "reason": f"Stream peak intensity (Score: {timeline[i]:.2f}σ)"
                })

        # Sort by score, remove duplicates/overlaps
        moments.sort(key=lambda x: x["score"], reverse=True)
        selected = []
        for m in moments:
            overlap = False
            for s in selected:
                if abs(m["start"] - s["start"]) < 30:  # 30s separation
                    overlap = True
                    break
            if not overlap and len(selected) < max_clips:
                selected.append(m)

        return selected
