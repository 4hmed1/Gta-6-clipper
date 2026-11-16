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

    # If empty (video very short), take whole video as 1 clip
    if not selected_clips and segments:
        duration = segments[-1]["end"] - segments[0]["start"]
        selected_clips.append({
            "start": round(segments[0]["start"], 2),
            "end": round(segments[-1]["end"], 2),
            "duration": round(duration, 1),
            "score": 88,
            "headline": segments[0]["text"][:40] + "...",
            "text": " ".join([s["text"] for s in segments]),
            "reason": "Complete context with high retention opener.",
            "segments": segments
        })

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
    
    if method == "gemini" or (api_key or GEMINI_API_KEY):
        return analyze_viral_moments_gemini(full_text, segments, api_key or GEMINI_API_KEY)
    elif method == "ollama":
        return analyze_viral_moments_ollama(full_text, segments)
    else:
        return analyze_viral_moments_heuristic(segments)
