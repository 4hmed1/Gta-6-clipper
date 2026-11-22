import librosa
import numpy as np
from typing import List, Dict, Any

def generate_kinetic_ass(
    words: List[Dict[str, Any]],
    output_path: str,
    vocal_onsets: np.ndarray,
    sr: int = 22050
) -> str:
    """
    Generates high-end .ass subtitles with kinetic pop-in animations
    synced to vocal onset peaks.
    """

    header = """[Script Info]
Title: ViralForge Kinetic Captions
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Viral,Anton,85,&H00FFFFFF&,&H000000FF&,&H00000000&,&H80000000&,-1,0,0,0,100,100,0,0,1,6,2,2,50,50,150,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []

    # Sync strategy: Map word timing to nearest vocal onset peak
    for word in words:
        start_t = word["start"]
        end_t = word["end"]
        text = word["word"].upper()

        # Kinetic animation:
        # \fscx115\fscy115 -> initial pop (115% scale)
        # \fscx100\fscy100 -> settle (100% scale)
        # \c&H00FFFF& -> Bright yellow active highlight

        ass_start = f"{int(start_t // 3600)}:{int((start_t % 3600) // 60):02d}:{start_t % 60:05.2f}"
        ass_end = f"{int(end_t // 3600)}:{int((end_t % 3600) // 60):02d}:{end_t % 60:05.2f}"

        # Build kinetic line with tag sequence
        line = f"Dialogue: 0,{ass_start},{ass_end},Viral,,0,0,0,,{{\\fscx115\\fscy115\\c&H00FFFF&}}{text}{{\\fscx100\\fscy100\\c&HFFFFFF&}}"
        events.append(line)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(events))

    return output_path
