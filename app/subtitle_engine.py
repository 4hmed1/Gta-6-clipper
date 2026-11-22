import os
from typing import List, Dict, Any
from pathlib import Path

# Professional Subtitle Style Presets (ASS uses BGR hex format: &H00BBGGRR&)
STYLES = {
    "vibrant_gold": {
        "font_name": "Montserrat ExtraBold",
        "font_size": 28,
        "primary_color": "&H00FFFFFF&",    # Crisp White inactive
        "highlight_color": "&H0022E6FF&",  # Electric Vibrant Gold/Yellow
        "outline_color": "&H00000000&",    # Deep Pure Black Outline
        "back_color": "&H80000000&",       # Soft Shadow
        "bold": -1,
        "outline": 5,
        "shadow": 2,
        "uppercase": True
    },
    "neon_green": {
        "font_name": "Poppins ExtraBold",
        "font_size": 30,
        "primary_color": "&H00FFFFFF&",
        "highlight_color": "&H0033FF55&",  # Intense Neon Cyber Green
        "outline_color": "&H00000000&",
        "back_color": "&H90000000&",
        "bold": -1,
        "outline": 6,
        "shadow": 3,
        "uppercase": True
    },
    "cyber_cyan": {
        "font_name": "Inter",
        "font_size": 28,
        "primary_color": "&H00F0F0F0&",
        "highlight_color": "&H00FFF000&",  # Electric Neon Cyan
        "outline_color": "&H00000000&",
        "back_color": "&H70000000&",
        "bold": -1,
        "outline": 5,
        "shadow": 2,
        "uppercase": True
    },
    "minimal": {
        "font_name": "Inter",
        "font_size": 22,
        "primary_color": "&H00FFFFFF&",
        "highlight_color": "&H00A0A0FF&",
        "outline_color": "&H00202020&",
        "back_color": "&H60000000&",
        "bold": 0,
        "outline": 3,
        "shadow": 1,
        "uppercase": False
    }
}
STYLES["hormozi"] = STYLES["vibrant_gold"]
STYLES["mrbeast"] = STYLES["neon_green"]
STYLES["cyber"] = STYLES["cyber_cyan"]

def format_ass_time(seconds: float) -> str:
    """Format seconds into ASS timestamp H:MM:SS.cs"""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int(round((seconds - int(seconds)) * 100))
    if centis >= 100:
        centis = 99
    return f"{hrs}:{mins:02d}:{secs:02d}.{centis:02d}"

def generate_ass_subtitles(
    words: List[Dict[str, Any]],
    clip_start: float,
    clip_end: float,
    output_ass_path: str,
    style_name: str = "vibrant_gold",
    words_per_batch: int = 3
) -> str:
    """
    Generates high-retention ASS subtitles with TikTok/Reels kinetic word-pop scale animations.
    Uses \\fscx118\\fscy118 pop-in animation with instant color transitions.
    """
    style = STYLES.get(style_name, STYLES["vibrant_gold"])

    # Filter words strictly inside clip window
    clip_words = [
        w for w in words
        if w["end"] > clip_start and w["start"] < clip_end
    ]

    if not clip_words:
        # Emergency dummy subtitle if no timestamps
        clip_words = [{
            "word": "VIRAL SHORT",
            "start": clip_start,
            "end": clip_end
        }]

    # Batch words in 2-3 word chunks for ultra-fast retention reading
    batches = []
    current_batch = []
    for w in clip_words:
        current_batch.append(w)
        if len(current_batch) >= words_per_batch:
            batches.append(current_batch)
            current_batch = []
    if current_batch:
        batches.append(current_batch)

    ass_header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: KineticViral,{style['font_name']},{style['font_size'] * 2.3},{style['primary_color']},&H000000FF&,{style['outline_color']},{style['back_color']},{style['bold']},0,0,0,100,100,1,0,1,{style['outline'] * 2},{style['shadow'] * 2},2,50,50,120,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    dialogue_lines = []

    for batch in batches:
        # ONE dialogue line per batch — not one per word. The old code
        # created a line for every word in the batch, each showing the
        # full batch text, so a 3-word batch rendered 3 overlapping
        # copies of the same caption (the "doubling" bug).
        batch_start = max(0.0, batch[0]["start"] - clip_start)
        batch_end = max(0.0, batch[-1]["end"] - clip_start)
        if batch_end <= batch_start:
            batch_end = batch_start + 0.22

        # Karaoke-style word sweep inside a single line:
        #   \k{centis}  = highlight grows across this word
        #   \fscx118    = pop-in scale on the active word
        #   \fscx100    = back to normal after the word
        # The highlight moves word-by-word without duplicating text.
        phrase_parts = []
        for w in batch:
            word_text = w["word"].upper() if style["uppercase"] else w["word"]
            w_dur = max(0.05, w["end"] - w["start"])
            centis = int(w_dur * 100)
            phrase_parts.append(
                f"{{\\k{centis}\\fscx118\\fscy118\\c{style['highlight_color']}}}"
                f"{word_text}"
                f"{{\\fscx100\\fscy100\\c{style['primary_color']}}}"
            )

        text_line = " ".join(phrase_parts)
        dialogue_lines.append(
            f"Dialogue: 0,{format_ass_time(batch_start)},{format_ass_time(batch_end)},KineticViral,,0,0,0,,{text_line}"
        )

    full_ass_content = ass_header + "\n".join(dialogue_lines) + "\n"

    Path(output_ass_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_ass_path, "w", encoding="utf-8") as f:
        f.write(full_ass_content)

    return output_ass_path
