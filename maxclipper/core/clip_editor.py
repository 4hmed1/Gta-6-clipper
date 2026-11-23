from typing import Dict, Any, List
from app.video_engine import render_clip

def adjust_and_reexport_clip(
    source_video: str,
    start_time: float,
    end_time: float,
    words: List[Dict[str, Any]],
    headline: str,
    layout: str = "split_blur",
    subtitle_style: str = "hormozi",
    custom_text: str = ""
) -> Dict[str, Any]:
    """
    Re-render clip with adjusted start/end boundaries, new layout, or revised captions.
    """
    # If user manually edited caption text, update the words accordingly
    if custom_text and words:
        edited_tokens = custom_text.split()
        if len(edited_tokens) == len(words):
            for i, tok in enumerate(edited_tokens):
                words[i]["word"] = tok

    return render_clip(
        source_video=source_video,
        start_time=start_time,
        end_time=end_time,
        words=words,
        headline=headline,
        layout=layout,
        subtitle_style=subtitle_style
    )
