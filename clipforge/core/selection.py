import numpy as np
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional

from .._config import package_config as _package_config
from .signals import analyze_audio_signals
from .nlp import HookAnalyzer
from .transcript import YouTubeTranscriptProvider

class ClipSelector:
    def __init__(self, content_type: str = "podcast"):
        self.content_type = content_type
        self.transcript_provider = YouTubeTranscriptProvider()
        self.hook_analyzer = HookAnalyzer()

        # Load scoring weights from config
        self.load_scoring_weights()

    def load_scoring_weights(self):
        config_path = _package_config(f"scoring/{self.content_type}.yaml")
        if config_path.exists():
            with open(config_path, "r") as f:
                self.config = yaml.safe_load(f)
        else:
            self.config = {
                "weights": {
                    "hook_score": 0.3,
                    "energy_density": 0.2,
                    "speech_rate": 0.1,
                    "sentiment": 0.1,
                    "heatmap": 0.2
                },
                "penalties": {
                    "dead_air": -0.5,
                    "sponsor_read": -0.8,
                    "length_mismatch": -0.3
                }
            }

    def select_clips(
        self,
        source: str,
        transcript: List[Dict[str, Any]],
        audio_path: str,
        min_duration: float = 20.0,
        max_duration: float = 60.0,
        max_clips: int = 5
    ) -> List[Dict[str, Any]]:
        # 1. Get audio signals
        signals = analyze_audio_signals(audio_path)

        # 2. Split transcript into sentences
        sentences = self.hook_analyzer.get_sentence_boundaries(transcript)

        # 3. Score each candidate window
        candidates = []
        for i in range(len(sentences)):
            for j in range(i, len(sentences)):
                candidate = sentences[i:j+1]
                start = candidate[0]["start"]
                end = candidate[-1]["end"]
                duration = end - start

                if duration < min_duration:
                    continue
                if duration > max_duration:
                    break

                score = self._score_candidate(candidate, signals, start, end)
                candidates.append({
                    "start": start,
                    "end": end,
                    "score": score["score"],
                    "reasons": score["reasons"],
                    "text": " ".join([w["word"] for w in candidate]),
                    "sentence_indices": list(range(i, j+1))
                })

        # 4. Non-maximum suppression + diversity
        candidates = self._nms_diversity(candidates, max_clips)

        # 5. Generate headlines
        for cand in candidates:
            cand["headline"] = self._generate_headline(cand)

        return candidates

    def _score_candidate(
        self,
        candidate: List[Dict[str, Any]],
        signals: Dict[str, np.ndarray],
        start: float,
        end: float
    ) -> Dict[str, Any]:
        score = 0.0
        reasons = []

        # 1. Hook score (opening sentence)
        hook_score = self.hook_analyzer.score_sentence(candidate[0]["text"])
        score += hook_score["score"] * self.config["weights"]["hook_score"]
        if hook_score["reasons"]:
            reasons.append(f"Hook: {', '.join(hook_score['reasons'])}")

        # 2. Energy density
        start_idx = int(start / 0.05)  # 50ms hop
        end_idx = int(end / 0.05)
        if end_idx <= len(signals["rms"]):
            energy = np.mean(signals["rms"][start_idx:end_idx])
            score += energy * self.config["weights"]["energy_density"]
            reasons.append(f"Energy: {energy:.2f}")

        # 3. Penalties
        # Dead air penalty
        dead_air = signals["rms"][start_idx:end_idx] < 0.05
        if np.any(dead_air):
            score += np.sum(dead_air) * self.config["penalties"]["dead_air"]
            reasons.append("Dead air detected")

        return {"score": score, "reasons": reasons}

    def _nms_diversity(self, candidates: List[Dict[str, Any]], max_clips: int) -> List[Dict[str, Any]]:
        # Sort by score descending
        candidates.sort(key=lambda x: x["score"], reverse=True)

        # Non-maximum suppression
        selected = []
        for cand in candidates:
            # Check overlap with already selected
            overlap = False
            for sel in selected:
                if self._calculate_overlap(cand, sel) > 0.7:  # 70% overlap threshold
                    overlap = True
                    break

            if not overlap and len(selected) < max_clips:
                selected.append(cand)

        return selected

    def _calculate_overlap(self, cand1: Dict[str, Any], cand2: Dict[str, Any]) -> float:
        start1, end1 = cand1["start"], cand1["end"]
        start2, end2 = cand2["start"], cand2["end"]

        overlap_start = max(start1, start2)
        overlap_end = min(end1, end2)
        overlap_duration = max(0, overlap_end - overlap_start)

        duration1 = end1 - start1
        duration2 = end2 - start2

        return overlap_duration / max(duration1, duration2)

    def _generate_headline(self, candidate: Dict[str, Any]) -> str:
        # Simple headline generation from first few words
        words = candidate["text"].split()
        if len(words) > 5:
            return " ".join(words[:5]) + "..."
        return candidate["text"]
