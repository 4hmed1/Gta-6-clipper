import re
import json
import requests
from typing import List, Dict, Any
from app.config import GEMINI_API_KEY, OLLAMA_HOST, OLLAMA_MODEL

VIRAL_HOOK_TRIGGERS = [
    r"\b(secret|mistake|never|always|why you|how to|the truth|stop doing|crazy|insane)\b",
    r"\b(nobody talks about|huge mistake|i lost|i made|guaranteed|warning|hack|trick)\b",
    r"\b(what happens if|did you know|imagine if|listen to this|number one rule)\b",
    r"\b(most people don't|don't make this|the biggest problem|transform|changed my life)\b"
]

HIGH_EMOTION_WORDS = {
    "money", "success", "rich", "millionaire", "fail", "danger", "deadly", "shocking",
    "genius", "scam", "cheat", "win", "lose", "destroyed", "exponential", "future",
    "secret", "illegal", "hidden", "powerful", "weapon", "ai", "free", "viral"
}

def analyze_viral_moments_heuristic(
    segments: List[Dict[str, Any]], 
    min_duration: float = 20.0, 
    max_duration: float = 60.0,
    max_clips: int = 5
) -> List[Dict[str, Any]]:
    """
    100% Free, Offline Smart Heuristic Engine.
    Uses NLP engagement indicators, hook sentence scoring, speech tempo and emotional density.
    """
    if not segments:
        return []

    candidates = []
    num_segs = len(segments)

    for i in range(num_segs):
        start_time = segments[i]["start"]
        accumulated_text = []
        seg_indices = []

        for j in range(i, num_segs):
            end_time = segments[j]["end"]
            duration = end_time - start_time
            accumulated_text.append(segments[j]["text"])
            seg_indices.append(j)

            if duration < min_duration:
                continue
            if duration > max_duration:
                break

            # Evaluate this window
            clip_text = " ".join(accumulated_text)
            first_sentence = segments[i]["text"]
            
            # 1. Hook Score (0-35 points)
            hook_score = 10
            for pattern in VIRAL_HOOK_TRIGGERS:
                if re.search(pattern, first_sentence, re.IGNORECASE):
                    hook_score += 12
            if "?" in first_sentence:
                hook_score += 8
            if "!" in first_sentence:
                hook_score += 5
            hook_score = min(35, hook_score)

            # 2. Emotional Keyword Density (0-30 points)
            words = re.findall(r'\b\w+\b', clip_text.lower())
            total_words = len(words)
            if total_words == 0:
                continue

            emotion_count = sum(1 for w in words if w in HIGH_EMOTION_WORDS)
            emotion_ratio = emotion_count / total_words
            emotion_score = min(30, int(emotion_ratio * 400) + (5 if emotion_count > 0 else 0))

            # 3. Speech Velocity & Flow (0-20 points)
            wpm = (total_words / duration) * 60
            velocity_score = 15
            if 130 <= wpm <= 190:  # Sweet spot for energetic speech
                velocity_score = 20
            elif wpm < 90:
                velocity_score = 5

            # 4. Length Optimization (0-15 points: 30-45s is the golden sweet spot)
            length_score = 15 if 30 <= duration <= 45 else 10

            total_score = min(99, hook_score + emotion_score + velocity_score + length_score)

            # Generate hook headline
            first_words = first_sentence.split()[:8]
            headline = " ".join(first_words)
            if not headline.endswith((".", "!", "?")):
                headline += "..."

            candidates.append({
                "start": round(start_time, 2),
                "end": round(end_time, 2),
                "duration": round(duration, 1),
                "score": int(total_score),
                "headline": headline,
                "text": clip_text,
                "reason": f"Strong hook rating ({hook_score}/35) and dynamic speech pacing ({int(wpm)} WPM).",
                "segments": [segments[idx] for idx in seg_indices]
            })

    # Sort descending by score
    candidates.sort(key=lambda x: x["score"], reverse=True)

    # Filter out overlapping clips (at least 15s separation)
    selected_clips = []
    for cand in candidates:
        overlap = False
        for sel in selected_clips:
            if not (cand["end"] < sel["start"] + 10 or cand["start"] > sel["end"] - 10):
                overlap = True
                break
        if not overlap:
            selected_clips.append(cand)
            if len(selected_clips) >= max_clips:
                break

    # CRITICAL FIX: Never return the entire video as a single clip.
    # If no valid clips found, try relaxed constraints or return empty list.
    if not selected_clips and segments:
        print(f"[ViralDetector] WARNING: No valid clips found from {len(segments)} segments. "
              f"Video duration: {segments[-1]['end'] if segments else 0:.1f}s.")

        # Fallback: try with relaxed min_duration
        if min_duration > 15:
            print(f"[ViralDetector] Retrying with min_duration=15...")
            return analyze_viral_moments_heuristic(segments, min_duration=15.0, max_duration=max_duration, max_clips=max_clips)

        # Last resort: generate clips from sentence boundaries
        if segments:
            fallback_clips = []
            total_duration = segments[-1]["end"] - segments[0]["start"]
            target_count = min(max_clips, max(1, int(total_duration / 30)))
            seg_per_clip = max(1, len(segments) // target_count)

            for i in range(0, len(segments), seg_per_clip):
                chunk = segments[i:i + seg_per_clip]
                if len(fallback_clips) >= max_clips:
                    break
                clip_start = chunk[0]["start"]
                clip_end = chunk[-1]["end"]
                clip_dur = clip_end - clip_start
                if clip_dur < 10:
                    continue
                clip_text = " ".join(s["text"] for s in chunk)
                first_sentence = chunk[0]["text"]
                headline = " ".join(first_sentence.split()[:8])
                if not headline.endswith((".", "!", "?")):
                    headline += "..."

                fallback_clips.append({
                    "start": round(clip_start, 2),
                    "end": round(clip_end, 2),
                    "duration": round(clip_dur, 1),
                    "score": 60,
                    "headline": headline,
                    "text": clip_text,
                    "reason": "Fallback clip from sentence boundaries.",
                    "segments": chunk,
                })
            if fallback_clips:
                print(f"[ViralDetector] Generated {len(fallback_clips)} fallback clips.")
                return fallback_clips

        return []

    return selected_clips

def analyze_viral_moments_gemini(transcript: str, segments: List[Dict[str, Any]], api_key: str = GEMINI_API_KEY) -> List[Dict[str, Any]]:
    """Use Google Gemini Flash (Free Tier) to discover viral hooks."""
    if not api_key:
        return analyze_viral_moments_heuristic(segments)
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    prompt = f"""
You are the world's top viral short-form video editor (expert in TikTok, YouTube Shorts, and Instagram Reels).
Analyze this video transcript with timestamps and extract the TOP 3 to 5 MOST VIRAL CLIPS.

Each clip must:
1. Have a powerful pattern interrupt / hook in the first 3 seconds.
2. Be between 25 and 60 seconds long.
3. Deliver a complete insight, story punchline, or emotional revelation.
4. Have an assigned Virality Score (0-100).

Return ONLY raw JSON with no markdown formatting or backticks:
{{
  "clips": [
    {{
      "start": 12.5,
      "end": 45.0,
      "score": 96,
      "headline": "Why 99% Of People Fail In 2026",
      "reason": "Starts with an intense curiosity gap followed by an actionable contrarian truth."
    }}
  ]
}}

Transcript:
{transcript[:8000]}
"""

    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=30)
        res_json = res.json()
        raw_text = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
        # Clean json
        raw_text = re.sub(r"^```json\s*", "", raw_text)
        raw_text = re.sub(r"^```\s*", "", raw_text)
        raw_text = re.sub(r"```$", "", raw_text)
        
        parsed = json.loads(raw_text)
        clips = parsed.get("clips", [])
        
        # Hydrate with segments
        for c in clips:
            c["duration"] = round(c["end"] - c["start"], 1)
            c["segments"] = [s for s in segments if s["end"] >= c["start"] and s["start"] <= c["end"]]
            c["text"] = " ".join([s["text"] for s in c["segments"]])
            
        return clips if clips else analyze_viral_moments_heuristic(segments)
    except Exception as e:
        print(f"[ViralDetector] Gemini API error: {e}. Falling back to heuristic.")
        return analyze_viral_moments_heuristic(segments)

def analyze_viral_moments_ollama(transcript: str, segments: List[Dict[str, Any]], host: str = OLLAMA_HOST, model: str = OLLAMA_MODEL) -> List[Dict[str, Any]]:
    """Use Local Ollama LLM for 100% private & free AI analysis."""
    endpoint = f"{host}/api/generate"
    prompt = f"""
Find the top 3 viral clips between 25 and 55 seconds from this transcript.
Output ONLY a JSON array of objects: [{{"start": float, "end": float, "score": int, "headline": str, "reason": str}}]

Transcript:
{transcript[:4000]}
"""
    try:
        res = requests.post(endpoint, json={"model": model, "prompt": prompt, "stream": False}, timeout=60)
        text = res.json().get("response", "")
        # Find json array
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            clips = json.loads(match.group(0))
            for c in clips:
                c["duration"] = round(c["end"] - c["start"], 1)
                c["segments"] = [s for s in segments if s["end"] >= c["start"] and s["start"] <= c["end"]]
                c["text"] = " ".join([s["text"] for s in c["segments"]])
            return clips
    except Exception as e:
        print(f"[ViralDetector] Ollama error: {e}")
        
    return analyze_viral_moments_heuristic(segments)

def detect_viral_clips(
    transcript_result: Dict[str, Any],
    method: str = "heuristic",
    api_key: str = "",
    progress_callback = None
) -> List[Dict[str, Any]]:
    """Unified entrypoint for viral moment detection."""
    if progress_callback:
        progress_callback("Analyzing retention curves, hooks & virality scores...", 70)

    segments = transcript_result.get("segments", [])
    full_text = transcript_result.get("text", "")

    # Fallback: build segments from words if segments list is empty
    if not segments:
        words = transcript_result.get("words", [])
        if words:
            # Group words into sentences by punctuation or pauses
            segments = []
            current_words = []
            current_start = words[0]["start"] if words else 0.0
            for w in words:
                if not current_words:
                    current_start = w["start"]
                current_words.append(w)
                # Break on sentence-ending punctuation or long pause
                if w.get("word", "").strip().endswith((".", "!", "?")) or (
                    len(current_words) > 1 and w["end"] - current_words[-2]["end"] > 1.5
                ):
                    segments.append({
                        "start": current_start,
                        "end": current_words[-1]["end"],
                        "text": " ".join(ww["word"] for ww in current_words),
                        "words": current_words,
                    })
                    current_words = []
            if current_words:
                segments.append({
                    "start": current_start,
                    "end": current_words[-1]["end"],
                    "text": " ".join(ww["word"] for ww in current_words),
                    "words": current_words,
                })
    
    if method == "gemini" or (api_key or GEMINI_API_KEY):
        return analyze_viral_moments_gemini(full_text, segments, api_key or GEMINI_API_KEY)
    elif method == "ollama":
        return analyze_viral_moments_ollama(full_text, segments)
    else:
        return analyze_viral_moments_heuristic(segments)
