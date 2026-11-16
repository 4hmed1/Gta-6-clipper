import re
import yaml
from pathlib import Path
from typing import List, Dict, Any

class HookAnalyzer:
    def __init__(self, config_path: str = "config/hooks.yaml"):
        p = Path(config_path)
        if p.exists():
            with open(p, "r") as f:
                self.config = yaml.safe_load(f)
        else:
            self.config = {
                "high_value_keywords": [],
                "hook_phrases": [],
                "negative_patterns": []
            }

    def score_sentence(self, text: str) -> Dict[str, float]:
        """Scores a sentence for viral hook potential."""
        text_lower = text.lower()
        score = 0.0
        reasons = []

        # 1. Punctuation Hook (Questions/Exclamations)
        if "?" in text:
            score += 20.0
            reasons.append("Curiosity question")
        if "!" in text:
            score += 10.0
            reasons.append("High energy statement")

        # 2. Keyphrase Matches
        for phrase in self.config.get("hook_phrases", []):
            if phrase in text_lower:
                score += 30.0
                reasons.append(f"Hook phrase: {phrase}")

        # 3. Numbers Hook (Social proof/quantification)
        if re.search(r'\d+', text):
            score += 15.0
            reasons.append("Quantified claim")

        # 4. Negative Penalty
        for pattern in self.config.get("negative_patterns", []):
            if pattern in text_lower:
                score -= 50.0
                reasons.append(f"Negative pattern: {pattern}")

        return {"score": max(0, score), "reasons": reasons}

    def get_sentence_boundaries(self, transcript: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Group words into logical sentences based on punctuation and pauses."""
        sentences = []
        current_sentence = []

        for i, word_token in enumerate(transcript):
            current_sentence.append(word_token)

            # Sentence ends on punctuation or long pause (>0.6s)
            is_terminal = word_token["word"].strip().endswith((".", "!", "?"))

            pause = 0
            if i < len(transcript) - 1:
                pause = transcript[i+1]["start"] - word_token["end"]

            if is_terminal or pause > 0.6:
                text = " ".join([w["word"] for w in current_sentence])
                sentences.append({
                    "text": text,
                    "start": current_sentence[0]["start"],
                    "end": current_sentence[-1]["end"],
                    "words": current_sentence
                })
                current_sentence = []

        # Add last sentence if any
        if current_sentence:
            text = " ".join([w["word"] for w in current_sentence])
            sentences.append({
                "text": text,
                "start": current_sentence[0]["start"],
                "end": current_sentence[-1]["end"],
                "words": current_sentence
            })

        return sentences
