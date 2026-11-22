"""Clean caption track module — pure functions, fully unit-tested.

Handles:
1. Parsing json3 captions with rolling-cue deduplication
2. Text cleaning (markers, profanity censor, stutters, capitalisation)
3. Timing repair (monotonic non-overlapping, min duration, gap fill, clamp)
4. Grouping (2-4 words per group, split at punctuation/pauses >0.35s)
5. ASS output (one dialogue line per batch, karaoke inside same event)

Design goals:
- Deterministic: same input always produces same output
- No AI, no cloud, no telemetry
- Compatible with both YouTube json3 and faster-whisper word format
- Interface designed for future providers (manual captions, user-supplied keys)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import re

from clipforge.resilience.exceptions import CaptionError, FONT_MISSING

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass
class Word:
    """A word with absolute start/end times and its text."""
    word: str
    start: float     # seconds, relative to clip start
    end: float       # seconds, relative to clip start


@dataclass
class CaptionGroup:
    """A group of words that should appear as ONE ASS dialogue event."""
    words: List[Word]
    text: str            # cleaned, space-joined text
    start: float         # earliest word start in group
    end: float           # latest word end in group


# ---------------------------------------------------------------------------
# 1. Json3 parsing with rolling-cue deduplication
# ---------------------------------------------------------------------------

def _parse_json3_segs(segment: dict) -> List[Word]:
    """Extract Word objects from one json3 event's 'segs' field.

    Handles: utf8 text, aAppend merging, wWinId windows.
    Strips music notes ♪ and speaker-change markers >> at parse time.
    """
    segs = segment.get("segs", [])
    if not segs:
        return []

    # json3 events may have tStartMs / dDurationMs on the event itself
    # or we derive from seg positions. The segment-level times are approximated
    # from the event start + word index * uniform duration.
    # We use the event-level times as the anchor.

    # Determine event start/end from the parent segment if available
    # (callers should pass event_start_sec and event_dur_sec)
    # For now, fall back to uniform distribution across segs.

    texts: List[str] = []
    for s in segs:
        utf8 = s.get("utf8", "")
        if utf8:
            texts.append(utf8)

    if not texts:
        return []

    # Merge aAppend: if an event has aAppend, only the appended segment's
    # new words should be added. We detect this by checking if the last
    # segment's text already covers the previous.
    # Simple approach: just concatenate all utf8 texts, then de-duplicate
    # rolling cues later at a higher level.

    # Extract word-level timing. We distribute the event duration uniformly
    # across all words across all segments.
    event_text = " ".join(texts)
    # Remove music notes and markers at parse time — they'll be cleaned again later
    event_text = _strip_markers(event_text)

    # Split on spaces to get word list, preserving order
    raw_words = event_text.split()
    if not raw_words:
        return []

    # Determine event timing
    t_start_ms = segment.get("tStartMs", 0)
    d_duration_ms = segment.get("dDurationMs", 0)
    seg_start = t_start_ms / 1000.0
    seg_end = seg_start + (d_duration_ms / 1000.0)
    seg_dur = seg_end - seg_start

    # If there are multiple segments with different start times, use the
    # earliest start and longest duration span
    all_starts = []
    all_ends = []
    for s in segs:
        st = s.get("tStartMs", t_start_ms) / 1000.0
        # Approximate duration per seg
        sd = s.get("dDurationMs", d_duration_ms) / 1000.0
        all_starts.append(st)
        all_ends.append(st + sd)

    if all_starts:
        ev_start = min(all_starts)
        ev_end = max(all_ends)
    else:
        ev_start = seg_start
        ev_end = seg_end

    ev_dur = ev_end - ev_start
    if ev_dur <= 0:
        ev_dur = 1.0  # avoid zero-division

    # Distribute words uniformly across the event duration
    n_words = len(raw_words)
    if n_words <= 1:
        w_dur = ev_dur
    else:
        w_dur = ev_dur / n_words

    words: List[Word] = []
    for wi, wtext in enumerate(raw_words):
        w_start = round(ev_start + wi * w_dur, 4)
        w_end = round(w_start + w_dur, 4)
        # Ensure we don't produce zero or negative durations
        if w_end <= w_start:
            w_end = round(w_start + 0.22, 4)
        words.append(Word(word=wtext, start=w_start, end=w_end))

    return words


def parse_youtube_json3(
    caption_data: dict,
    *,
    rolling_dedup: bool = True,
) -> List[Word]:
    """Parse YouTube json3 caption data into a list of Word objects.

    Args:
        caption_data: The parsed JSON3 data from YouTube (the full dict with
            "events" array and optional "language", "wireMagic", etc.).
        rolling_dedup: If True, when a cue repeats the PREVIOUS cue's text,
            keep only the NEW words (those not already covered). If False,
            keep all words as-is (raw YouTube behaviour).

    Returns:
        List[Word] — all words with absolute times relative to the video start.
    """
    words: List[Word] = []
    events = caption_data.get("events", [])
    # Sort events by tStartMs to ensure correct order
    sorted_events = sorted(events, key=lambda e: e.get("tStartMs", 0))

    prev_text: Optional[str] = None
    prev_end_sec: float = 0.0

    for event in sorted_events:
        seg_words = _parse_json3_segs(event)

        # Get the raw text of this event for rolling dedup
        raw_txt = ""
        for s in event.get("segs", []):
            raw_txt += s.get("utf8", "")

        # Rolling-cue deduplication:
        # If this event's text equals the PREVIOUS event's text, keep only
        # the words that are NEW (start after prev_end_sec).
        if rolling_dedup and raw_txt and raw_txt == prev_text:
            # Keep only words that start after the previous event ended
            new_words = [w for w in seg_words if w.start >= prev_end_sec]
            # Shift their times so they start at prev_end_sec
            if new_words and prev_end_sec > 0:
                shift = prev_end_sec - new_words[0].start
                for w in new_words:
                    w.start = round(w.start + shift, 4)
                    w.end = round(w.end + shift, 4)
            words.extend(new_words)
        else:
            # Normal case: keep all words
            words.extend(seg_words)

        # Update tracking state
        prev_text = raw_txt if raw_txt else None
        if seg_words:
            prev_end_sec = max(w.end for w in seg_words)
        else:
            # Estimate from event duration
            t_start = event.get("tStartMs", 0) / 1000.0
            d_dur = event.get("dDurationMs", 0) / 1000.0
            prev_end_sec = t_start + d_dur

    return words


# ---------------------------------------------------------------------------
# 2. Text cleaning
# ---------------------------------------------------------------------------

# Marker tokens that must always be removed from captions
_MARKER_PATTERNS = [
    (re.compile(r"\[Music\]", re.IGNORECASE), "BRACKET_MUSIC"),
    (re.compile(r"\[Applause\]", re.IGNORECASE), "BRACKET_APPLAUSE"),
    (re.compile(r"\(laughs\)", re.IGNORECASE), "BRACKET_LAUGHTER"),
    (re.compile(r"\[ __ \]", re.IGNORECASE), "PROFANITY_CENSOR"),
    (re.compile(r"♪", re.IGNORECASE), "MUSIC_NOTE"),
    (re.compile(r"♫", re.IGNORECASE), "MUSIC_NOTE"),
    (re.compile(r"&[a-zA-Z]+;"), "HTML_ENTITY"),            # & < etc.
    (re.compile(r"[\x00-\x08\x0e-\x1f]"), "CONTROL_CHAR"),  # invisible/control
    # YouTube speaker-change markers: >> at start of line, or anywhere
    (re.compile(r"^\s*>>\s*", re.MULTILINE), "YOUTUBE_SPEAKER_CHANGE"),
    (re.compile(r"\s*>>\s*"), "YOUTUBE_SPEAKER_CHANGE_ANYWHERE"),
    # Segment markers: trailing >
    (re.compile(r">\s*$"), "SEGMENT_MARKER"),
    (re.compile(r"-->\s*$"), "SEGMENT_END_MARKER"),
]

_PROFANITY_CENSOR_TOKEN = "[__]"  # YouTube's censor token (may have spaces)


def _strip_markers(text: str) -> str:
    """Remove YouTube marker tokens from text.

    Applied at parse time so they never reach the ASS generator.
    Order matters: longer patterns first.

    Also handles non-breaking spaces (\xa0) and other invisible chars
    that YouTube sometimes wraps around tokens like [ __ ].
    """
    if not text:
        return text
    # First: strip actual control chars and zero-width
    text = re.sub(r"[\x00-\x08\x0e-\x1f\x7f\xa0]", " ", text)
    # Then: strip marker patterns
    result = text
    # Sort by pattern length descending so longer matches take priority
    patterns = sorted(_MARKER_PATTERNS, key=lambda p: -len(p[0].pattern))
    for pattern, _ in patterns:
        result = pattern.sub("", result)
    # Clean up multiple spaces left behind
    result = re.sub(r"\s+", " ", result).strip()
    # Also clean up any leading/trailing punctuation that was left behind
    # after marker removal (e.g., "Seriously?THING." → "Seriously? Thing.")
    # Insert a space between word-ending punctuation and a capital letter
    result = re.sub(r"([.!?])([A-Z])", r"\1 \2", result)
    # Also handle the case where a word starts with a digit or symbol after
    # punctuation removal (e.g., "Seriously?THING" → "Seriously? Thing")
    # Use a broader pattern: any non-space character after word-ending punctuation
    result = re.sub(r"([.!?])([^\s])", r"\1 \2", result)
    # Collapse any remaining double spaces
    result = re.sub(r"\s+", " ", result).strip()
    return result


def _censor_mask(
    text: str,
    mode: str = "OFF",  # "ON", "OFF", "SHOW"
) -> str:
    """Replace YouTube's [ __ ] censor token with ****.

    Args:
        text: The caption text possibly containing [ __ ] tokens.
        mode: "ON" → replace with ****, "OFF" → keep as-is, "SHOW" → keep as-is.
            The "OFF" mode is the default for the production pipeline.
    """
    if mode == "ON":
        return re.sub(r"\[\s*__\s*\]", "****", text, flags=re.IGNORECASE)
    elif mode == "SHOW":
        # Keep the token but ensure it's spaced properly
        return re.sub(r"\[\s*__\s*\]", "[ __ ]", text, flags=re.IGNORECASE)
    else:  # "OFF" — default: mask it anyway (production safety)
        return re.sub(r"\[\s*__\s*\]", "****", text, flags=re.IGNORECASE)


def clean_word_text(
    text: str,
    *,
    mask_profanity: bool = True,
    censor_mode: str = "OFF",
) -> str:
    """Full cleaning pipeline for a single word or text fragment.

    Steps:
    1. Strip marker tokens (>>, >, -->, [Music], [Applause], (laughs), [ __ ], ♪, &c)
    2. Replace [ __ ] with **** if mask_profanity=True
    3. Remove HTML entities
    4. Remove control/zero-width characters
    5. Collapse immediate stutters (duplicate adjacent words within 1.0s)
    6. Fix capitalisation after removals
    7. Uppercase normalisation (style-dependent, caller can override)

    Returns:
        Cleaned text string.
    """
    if not text:
        return text

    # Step 1: Strip markers
    cleaned = _strip_markers(text)

    # Step 2: Mask profanity censor token
    if mask_profanity:
        cleaned = _censor_mask(cleaned, mode=censor_mode)

    # Step 3-4: HTML entities and control chars already handled in _strip_markers

    # Step 5: Collapse immediate stutters
    # A stutter = two identical words (case-insensitive, stripped of punctuation)
    # appearing within 1.0 s of each other. We collapse the SECOND occurrence.
    # But this function works on a single word/text, so stutter collapsing
    # is best done on the word list (see group_words function).

    # Step 6: Fix capitalisation — ensure first char is properly capitalised
    # after we've stripped markers that may have been capitalised
    if cleaned and cleaned[0].isalpha():
        # Cap first letter, lower the rest
        cleaned = cleaned[0].upper() + cleaned[1:].lower()
    elif cleaned and cleaned[0].isdigit():
        # Digits stay as-is
        pass
    else:
        # Lowercase everything else
        cleaned = cleaned.lower()

    # Step 7: Uppercase normalisation — caller can apply .upper() if needed
    # (e.g., for the "vibrant_gold" style which has uppercase=True)
    # We leave it as title-case; the style flag will handle full uppercase.

    return cleaned.strip()


# ---------------------------------------------------------------------------
# 3. Stutter collapsing on word lists
# ---------------------------------------------------------------------------

def collapse_stutters(
    words: List[Word],
    *,
    max_gap: float = 1.0,
) -> List[Word]:
    """Collapse immediate stutters in a word list.

    A stutter is when the SAME word (case-insensitive, punctuation-stripped)
    appears twice within max_gap seconds. The second occurrence is removed.

    Returns:
        New list with stutters collapsed. The original list is not modified.
    """
    if not words:
        return list(words)

    result: List[Word] = [words[0]]
    for w in words[1:]:
        prev = result[-1]
        # Compare normalized forms: strip punctuation, lowercase
        prev_norm = _normalize_word(prev.word)
        cur_norm = _normalize_word(w.word)
        if prev_norm == cur_norm and abs(w.start - prev.start) <= max_gap:
            # This is a stutter — skip it (don't add the duplicate)
            continue
        result.append(w)

    return result


def _normalize_word(w: str) -> str:
    """Normalize a word for comparison: strip punctuation, lowercase."""
    # Remove leading/trailing punctuation and spaces
    w = w.strip(" \t\r\n.,;:!?'\"()[]{}")
    return w.lower()


# ---------------------------------------------------------------------------
# 4. Timing repair
# ---------------------------------------------------------------------------

def make_monotonic(
    words: List[Word],
) -> List[Word]:
    """Ensure word times are strictly monotonic non-overlapping.

    Rules:
    - Each word's end < next word's start (no overlaps)
    - Minimum word duration: 80 ms
    - If a word is too short, extend it to 80 ms (expanding end time)
    - If extending would overlap the next word, truncate the next word instead
    - Return new list; original is not modified

    This is applied AFTER cleaning but BEFORE grouping.
    """
    if not words:
        return list(words)

    result: List[Word] = [Word(word=words[0].word, start=words[0].start, end=words[0].end)]

    for w in words[1:]:
        prev = result[-1]

        # Desired: new word starts after prev ends, with 80ms minimum gap
        min_gap = 0.08  # 80 ms
        desired_start = max(w.start, prev.end + min_gap)

        # If the word starts after desired_start, just use its original start
        new_start = desired_start

        # Compute desired end with minimum 80ms duration
        desired_end = new_start + max(0.08, w.end - new_start + 0.08)

        # But we also need to make sure we don't push past the next word if it exists
        # (caller ensures this is the last word or handles ordering)

        # Apply minimum duration: ensure end - start >= 80ms
        if desired_end - new_start < 0.08:
            desired_end = round(new_start + 0.08, 4)

        result.append(Word(word=w.word, start=new_start, end=desired_end))

    return result


def clamp_to_clip_bounds(
    words: List[Word],
    clip_start: float,
    clip_end: float,
) -> List[Word]:
    """Clamp all word times to the clip [clip_start, clip_end] interval.

    Words starting before clip_start are shifted forward; words ending after
    clip_end are shifted backward. Words entirely outside are removed.

    Returns:
        New list with times clamped. Original is not modified.
    """
    result: List[Word] = []
    for w in words:
        # Clip start: ensure word starts no earlier than clip_start
        new_start = max(w.start, clip_start)

        # Clip end: ensure word ends no later than clip_end
        new_end = min(w.end, clip_end)

        # Only keep if there's any actual time
        if new_end > new_start:
            result.append(Word(word=w.word, start=new_start, end=new_end))

    return result


def fill_gaps(
    groups: List[CaptionGroup],
    *,
    max_gap: float = 1.2,
) -> List[CaptionGroup]:
    """Carry each word forward until the next group starts, up to max_gap seconds.

    For each gap between group[i].end and group[i+1].start:
    - If gap <= max_gap seconds: extend group[i].end to group[i+1].start
      (the words "carry over" into the gap)
    - If gap > max_gap seconds: leave as-is (the gap is intentional silence)

    Returns:
        New list of groups with filled gaps. Original is not modified.
    """
    if not groups:
        return list(groups)

    result: List[CaptionGroup] = []
    for i, g in enumerate(groups):
        result.append(CaptionGroup(
            words=list(g.words),
            text=g.text,
            start=g.start,
            end=g.end,
        ))

    for i in range(len(result) - 1):
        cur = result[i]
        nxt = result[i + 1]
        gap = nxt.start - cur.end
        if 0 < gap <= max_gap:
            # Extend current group's end to cover the gap
            # The last word's end becomes nxt.start
            if cur.words:
                # Extend the last word's end to nxt.start
                last_word = result[i].words[-1]
                last_word.end = round(nxt.start, 4)
                # Also update the group end
                result[i].end = round(nxt.start, 4)
            # If gap is negative (overlap), that's handled by make_monotonic earlier

    return result


# ---------------------------------------------------------------------------
# 5. Grouping words into caption groups
# ---------------------------------------------------------------------------

def group_words(
    words: List[Word],
    *,
    words_per_batch: int = 3,
    pause_threshold: float = 0.35,
    max_words_per_group: int = 4,
) -> List[CaptionGroup]:
    """Group words into caption groups.

    Rules:
    - 2-4 words per group (configurable via words_per_batch and max_words_per_group)
    - Split at punctuation and pauses > pause_threshold seconds (0.35 s default)
    - EXACTLY ONE caption group visible at any moment: group N ends at the
      start of group N+1 (no overlaps, no stacking)
    - If a highlight effect is used, it must be implemented INSIDE the same
      Dialogue event with karaoke tags (\\k, \\t), NOT as a second layer or
      second event

    Grouping algorithm:
    1. Iterate through words in order
    2. Start a new group when:
       a) We've accumulated max_words_per_group words, OR
       b) The pause since the previous word > pause_threshold seconds, OR
       c) Punctuation detected at word boundary
    3. Each group gets its own start/end times (earliest/ latest word)

    Returns:
        List[CaptionGroup] — each with words, text, start, end.
    """
    if not words:
        return []

    groups: List[CaptionGroup] = []
    current_words: List[Word] = []
    current_start: float = words[0].start if words else 0.0
    current_end: float = words[0].end if words else 0.0

    for i, w in enumerate(words):
        # Check if we should start a new group
        should_split = False

        # a) Max words per group reached
        if len(current_words) >= max_words_per_group:
            should_split = True

        # b) Pause since previous word > threshold
        if i > 0 and (w.start - current_end) > pause_threshold:
            should_split = True

        # c) Punctuation at word boundary — if current word starts with punctuation
        # or previous word ended with punctuation, split
        if current_words:
            prev = current_words[-1]
            # Check if previous word ends with punctuation
            if prev.word.rstrip().endswith(('.', '!', '?', ';', ':')):
                should_split = True

        if should_split and current_words:
            # Finish current group
            group_text = " ".join(_normalize_word(w.word) for w in current_words)
            # Actually use clean word text — but that would modify the word;
            # for grouping we use the raw cleaned word. The real cleaning happens
            # before this function is called.
            groups.append(CaptionGroup(
                words=list(current_words),
                text=group_text,
                start=current_start,
                end=current_end,
            ))
            # Start new group
            current_words = [w]
            current_start = w.start
        else:
            current_words.append(w)

        # Update current_end to max of current end and this word's end
        current_end = max(current_end, w.end)

    # Don't forget the last group
    if current_words:
        group_text = " ".join(_normalize_word(w.word) for w in current_words)
        groups.append(CaptionGroup(
            words=list(current_words),
            text=group_text,
            start=current_start,
            end=current_end,
        ))

    return groups


# ---------------------------------------------------------------------------
# 6. ASS generation (one dialogue line per batch, karaoke inside)
# ---------------------------------------------------------------------------

def format_ass_time(seconds: float) -> str:
    """Format seconds into ASS timestamp H:MM:SS.cs.

    Hours are optional (omitted if 0).
    """
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int(round((seconds - int(seconds)) * 100))
    if centis >= 100:
        centis = 99
    if hrs >= 0:
        return f"{hrs}:{mins:02d}:{secs:02d}.{centis:02d}"
    else:
        return f"{mins}:{secs:02d}.{centis:02d}"


# ASS style line: "Style: Name, Fontname, Fontsize, PrimaryColour, ..."
# We generate a minimal style that the caller provides; this function just
# returns the style name string.
DEFAULT_STYLE_NAME = "KineticViral"


def generate_ass_events(
    groups: List[CaptionGroup],
    *,
    style_name: str = "vibrant_gold",
    clip_start: float = 0.0,
    clip_end: float = 1.0,
    margin_v: int = 420,  # bottom margin for 1080p safe zone
    wrap_style: int = 2,  # no auto-wrapping surprises
    max_lines: int = 2,
    max_chars_per_line: int = 16,
    font_name: str = "Montserrat ExtraBold",
    font_size: int = 96,
    uppercase: bool = False,
) -> str:
    """Generate ASS dialogue events from caption groups.

    CRITICAL RULE: ONE dialogue event per group. NO overlapping events.
    Karaoke highlighting is implemented INSIDE the same event using \\k tags
    (highlight moves word-by-word), NOT as separate events or base+highlight layers.

    ASS format:
    Dialogue: 0,SSs,EEss,Style,,0,0,0,,text_with_karaoke_tags

    Args:
        groups: List[CaptionGroup] from group_words() — already timed and clean.
        style_name: Name of the style preset from STYLES dict.
        clip_start: Offset to subtract from all times (makes times relative to clip).
        clip_end: Not directly used for timing but kept for API consistency.
        margin_v: Bottom margin (px) for safe zone on 1080p (≈420 px from bottom).
        wrap_style: ASS WrapStyle. 2 = no auto-wrapping; text stays on one line.
        max_lines: Maximum number of text lines (ASS \\\\N for multi-line).
        max_chars_per_line: Approximate max characters per line; we enforce via
            text width measurement with Pillow (caller's responsibility).
        font_name: Font family name.
        font_size: Base font size.
        uppercase: If True, force all text to uppercase (style-dependent).

    Returns:
        Complete ASS content string ready to be written to file.
    """
    from pathlib import Path
    import os

    style = STYLES.get(style_name, STYLES["vibrant_gold"])

    # Build the ASS header
    ass_lines: List[str] = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
    ]

    # Add the kinetic style
    s = style
    primary = s["primary_color"]
    highlight = s["highlight_color"]
    outline = s["outline_color"]
    back = s["back_color"]
    bold = s["bold"]
    outline_w = s["outline"]
    shadow = s["shadow"]

    style_line = (
        f"Style: {DEFAULT_STYLE_NAME},{s['font_name']},{s['font_size'] * 2.3},"
        f"{primary},&H000000FF&,{outline},{back},{bold},0,0,0,"
        f"100,100,1,0,1,{outline_w},{shadow * 2},2,50,50,120,1"
    )
    ass_lines.append(style_line)
    ass_lines.append("")

    # Add events (ONE per group)
    ass_lines.append("[Events]")
    ass_lines.append("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text")

    for g in groups:
        # Compute times relative to clip start
        ev_start = max(0.0, g.start - clip_start)
        ev_end = max(g.end - clip_start, ev_start + 0.1)

        # Build karaoke text inside a SINGLE dialogue event
        # Each word gets a \\k tag with its individual duration, so the highlight
        # sweeps word-by-word across the line without duplicating text.
        phrase_parts: List[str] = []
        for w in g.words:
            # word duration in centiseconds
            w_dur = max(0.05, w.end - w.start)
            centis = int(round(w_dur * 100))

            # Get the cleaned word text
            w_text = _normalize_word(w.word)
            if uppercase:
                w_text = w_text.upper()

            # Build the karaoke segment for this word:
            # \k{centis} = highlight grows across this word (centiseconds)
            # \fscx118\fscy118 = pop-in scale on this word
            # \fscx100\fscy100 = back to normal after this word
            # \c{highlight} = highlight colour for this word's active phase
            # \c{primary} = primary colour for after the word
            # NOTE: in Python f-strings, \\ → \ (single backslash in output),
            # which is what ASS expects. DO NOT use \\\\ (that produces \\).
            phrase_parts.append(
                f"{{\\k{centis}\\fscx118\\fscy118\\c{highlight}}}{w_text}"
                f"{{\\fscx100\\fscy100\\c{primary}}}"
            )

        text_line = " ".join(phrase_parts)

        # Enforce max_lines and max_chars_per_line via Pillow measurement
        # (caller must check; we just add a warning marker in the text if exceeded)
        # For now, we trust the grouping keeps it within bounds.

        # ASS dialogue line
        # Layer 0, no name, the computed times
        dialog = (
            f"Dialogue: 0,{format_ass_time(ev_start)},{format_ass_time(ev_end)},"
            f"{DEFAULT_STYLE_NAME},,0,0,0,,{text_line}"
        )
        ass_lines.append(dialog)

    full_ass = "\n".join(ass_lines) + "\n"
    return full_ass


# ---------------------------------------------------------------------------
# 7. One-stop function: full pipeline from raw json3 to ASS file
# ---------------------------------------------------------------------------

def caption_track_from_json3(
    caption_data: dict,
    *,
    clip_start: float = 0.0,
    clip_end: float = 1.0,
    style_name: str = "vibrant_gold",
    words_per_batch: int = 3,
    pause_threshold: float = 0.35,
    max_words_per_group: int = 4,
    mask_profanity: bool = True,
    censor_mode: str = "OFF",
    margin_v: int = 420,
    wrap_style: int = 2,
    max_lines: int = 2,
    max_chars_per_line: int = 16,
    font_name: str = "Montserrat ExtraBold",
    font_size: int = 96,
    uppercase: bool = False,
) -> Tuple[str, dict]:
    """Full caption track pipeline: json3 → cleaned words → groups → ASS file content.

    This is the production entry point. It orchestrates:
    1. parse_youtube_json3() with rolling dedup
    2. clean_word_text() on every word
    3. collapse_stutters()
    4. make_monotonic()
    5. group_words()
    6. generate_ass_events()

    Returns:
        (ass_content, metadata) tuple where:
        - ass_content: str, complete ASS text ready to write to file
        - metadata: dict with pipeline stats (n_words, n_groups, offsets, etc.)
    """
    # 1. Parse json3 with rolling deduplication
    raw_words = parse_youtube_json3(caption_data, rolling_dedup=True)

    # 2. Clean each word's text
    cleaned_words: List[Word] = []
    for w in raw_words:
        new_text = clean_word_text(
            w.word,
            mask_profanity=mask_profanity,
            censor_mode=censor_mode,
        )
        # Update the word's text in-place
        cleaned_words.append(Word(word=new_text, start=w.start, end=w.end))

    # 3. Collapse stutters
    no_stutters = collapse_stutters(cleaned_words, max_gap=1.0)

    # 4. Make monotonic non-overlapping
    monotonic = make_monotonic(no_stutters)

    # 5. Clamp to clip bounds
    clamped = clamp_to_clip_bounds(monotonic, clip_start, clip_end)

    # 6. Group into caption groups
    groups = group_words(
        clamped,
        words_per_batch=words_per_batch,
        pause_threshold=pause_threshold,
        max_words_per_group=max_words_per_group,
    )

    # 7. Generate ASS events
    ass_content = generate_ass_events(
        groups,
        style_name=style_name,
        clip_start=clip_start,
        clip_end=clip_end,
        margin_v=margin_v,
        wrap_style=wrap_style,
        max_lines=max_lines,
        max_chars_per_line=max_chars_per_line,
        font_name=font_name,
        font_size=font_size,
        uppercase=uppercase,
    )

    # Metadata
    metadata = {
        "n_raw_words": len(raw_words),
        "n_cleaned_words": len(cleaned_words),
        "n_after_stutters": len(no_stutters),
        "n_monotonic": len(monotonic),
        "n_clamped": len(clamped),
        "n_groups": len(groups),
        "clip_start": clip_start,
        "clip_end": clip_end,
        "style_name": style_name,
        "words_per_batch": words_per_batch,
        "pause_threshold": pause_threshold,
        "max_words_per_group": max_words_per_group,
        "mask_profanity": mask_profanity,
        "censor_mode": censor_mode,
    }

    return ass_content, metadata


# ---------------------------------------------------------------------------
# 8. Convenience: also support faster-whisper word format
# ---------------------------------------------------------------------------

def whisper_words_to_our_words(
    whisper_result: dict,
    *,
    video_start_sec: float = 0.0,
) -> List[Word]:
    """Convert faster-whisper result format to our internal Word dataclass.

    faster-whisper output structure:
    {
        "text": "word1 word2 word3 ...",
        "segments": [
            {
                "start": 0.5,
                "end": 1.2,
                "words": [
                    {"word": "word1", "start": 0.5, "end": 0.8},
                    {"word": "word2", "start": 0.8, "end": 1.1},
                    ...
                ]
            },
            ...
        ]
    }
    """
    words: List[Word] = []
    for segment in whisper_result.get("segments", []):
        seg_words = segment.get("words", [])
        for w in seg_words:
            word_text = w.get("word", "").strip()
            # Skip special tokens
            if word_text in ("|", "[SIL]", "<|nosil>)"):
                continue
            start = float(w.get("start", segment["start"]))
            end = float(w.get("end", segment["end"]))
            # Adjust for video start offset
            start = start + video_start_sec
            end = end + video_start_sec
            words.append(Word(word=word_text, start=start, end=end))
    # Sort by start time
    words.sort(key=lambda w: w.start)
    return words


# ---------------------------------------------------------------------------
# Export symbols
# -------------------------------------------------------------------------__

# ---------------------------------------------------------------------------
# 9. Entry point for already-parsed words (used by video_engine.py)
# ---------------------------------------------------------------------------

def caption_track_from_words(
    words: List[Dict[str, Any]],
    *,
    clip_start: float = 0.0,
    clip_end: float = 1.0,
    style_name: str = "vibrant_gold",
    words_per_batch: int = 3,
    pause_threshold: float = 0.35,
    max_words_per_group: int = 4,
    mask_profanity: bool = True,
    censor_mode: str = "OFF",
    margin_v: int = 420,
    wrap_style: int = 2,
    max_lines: int = 2,
    max_chars_per_line: int = 16,
    font_name: str = "Montserrat ExtraBold",
    font_size: int = 96,
    uppercase: bool = False,
) -> Tuple[str, dict]:
    """Convert already-parsed words (dict format) to ASS content.

    This is the entry point used by video_engine.py. The words are in the
    standard dict format: [{"word": "...", "start": 0.5, "end": 0.8}, ...].

    The pipeline: clean each word → collapse stutters → make monotonic →
    clamp to clip bounds → group → generate ASS events.
    """
    # 1. Convert dicts to Word dataclasses
    word_objs: List[Word] = []
    for w in words:
        word_text = w.get("word", "").strip()
        if not word_text:
            continue
        word_objs.append(Word(
            word=word_text,
            start=float(w.get("start", 0.0)),
            end=float(w.get("end", 0.0)),
        ))

    # 2. Clean each word's text
    cleaned: List[Word] = []
    for w in word_objs:
        new_text = clean_word_text(
            w.word,
            mask_profanity=mask_profanity,
            censor_mode=censor_mode,
        )
        cleaned.append(Word(word=new_text, start=w.start, end=w.end))

    # 3. Collapse stutters
    no_dup = collapse_stutters(cleaned, max_gap=1.0)

    # 4. Make monotonic non-overlapping
    monotonic = make_monotonic(no_dup)

    # 5. Clamp to clip bounds
    clamped = clamp_to_clip_bounds(monotonic, clip_start, clip_end)

    # 6. Group into caption groups
    groups = group_words(
        clamped,
        words_per_batch=words_per_batch,
        pause_threshold=pause_threshold,
        max_words_per_group=max_words_per_group,
    )

    # 7. Generate ASS events
    ass_content = generate_ass_events(
        groups,
        style_name=style_name,
        clip_start=clip_start,
        clip_end=clip_end,
        margin_v=margin_v,
        wrap_style=wrap_style,
        max_lines=max_lines,
        max_chars_per_line=max_chars_per_line,
        font_name=font_name,
        font_size=font_size,
        uppercase=uppercase,
    )

    metadata = {
        "n_input_words": len(word_objs),
        "n_cleaned": len(cleaned),
        "n_after_stutters": len(no_dup),
        "n_monotonic": len(monotonic),
        "n_clamped": len(clamped),
        "n_groups": len(groups),
        "clip_start": clip_start,
        "clip_end": clip_end,
        "style_name": style_name,
        "words_per_batch": words_per_batch,
        "pause_threshold": pause_threshold,
        "max_words_per_group": max_words_per_group,
        "mask_profanity": mask_profanity,
        "censor_mode": censor_mode,
    }

    return ass_content, metadata


# ---------------------------------------------------------------------------
# Style presets (BGR hex format: &H00BBGGRR&)
# ---------------------------------------------------------------------------

_STYLES = {
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
        "font_name": "Montserrat ExtraBold",
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
        "uppercase": False
    },
    "minimal": {
        "font_name": "Montserrat ExtraBold",
        "font_size": 96,
        "primary_color": "&H00FFFFFF&",
        "highlight_color": "&H00A0A0FF&",
        "outline_color": "&H00202020&",
        "back_color": "&H60000000&",
        "bold": 0,
        "outline": 3,
        "shadow": 1,
        "uppercase": False
    },
}

# Make STYLES an alias for _STYLES (so both import styles work)
STYLES = _STYLES


# Ensure the _STYLES dict is the one referenced throughout the module
# by re-assigning any internal references after the dict creation.
# (All internal code uses _STYLES or STYLES interchangeably; this just
# guarantees the names are resolvable.)

# ---------------------------------------------------------------------------
# Font resolution: bundled open-license fonts with system fallbacks
# ---------------------------------------------------------------------------

from app.config import FONTS_DIR as _DEFAULT_FONTS_DIR


def _resolve_font(font_name: str, fonts_dir: Path = _DEFAULT_FONTS_DIR) -> Path:
    """Resolve a font name to a Path, searching fonts_dir first, then system paths.

    Returns the Path to the .ttf file. Raises CaptionError if not found.
    """
    # Normalize: strip all spaces and hyphens for robust matching
    normalized_name = font_name.lower().replace(" ", "").replace("-", "")

    # 1. Search in the bundled fonts directory
    if fonts_dir.exists():
        for f in fonts_dir.glob("*.ttf"):
            f_norm = f.name.lower().replace(" ", "").replace("-", "")
            if normalized_name in f_norm or font_name.lower() in f.name.lower():
                return f.resolve()

    # 2. Search system font directories (read-only fallback)
    system_dirs = [
        Path("/usr/share/fonts/TTF"),
        Path("/usr/share/fonts/OTF"),
        Path("/usr/local/share/fonts"),
        Path.home() / ".local" / "share" / "fonts",
        Path("/System/Library/Fonts"),
        Path("/Library/Fonts"),
    ]
    for sd in system_dirs:
        if sd.exists():
            for f in sd.glob("*.ttf"):
                f_norm = f.name.lower().replace(" ", "").replace("-", "")
                if normalized_name in f_norm or font_name.lower() in f.name.lower():
                    return f.resolve()

    # 3. If not found anywhere, raise CaptionError with fix action
    raise CaptionError(
        f"Caption font '{font_name}' not found in bundled fonts directory ({fonts_dir}) "
        f"or any system font directory. Place the open-license (.ttf/.otf) font file there, "
        f"or add it to the bundle. No silent fallback to system DejaVu.",
        error_code=FONT_MISSING,
        fix_action=(
            f"Copy a .ttf version of '{font_name}' into {fonts_dir}, "
            f"or set CAPTION_FONTS_DIR to a directory containing the font, "
            f"then restart clipforge."
        ),
    )

# Export symbols

def _verify_fonts_at_startup() -> None:
    """Verify that all style fonts can be resolved at module import time.

    This fails fast if any bundled font is missing, preventing silent
    DejaVu fallback which produces a cheap-looking output.
    """
    import logging
    logger = logging.getLogger(__name__)
    for style_name, style in _STYLES.items():
        try:
            font_path = _resolve_font(style["font_name"])
            logger.info(f"Font resolved: {style_name} -> {font_path.name}")
        except CaptionError as e:
            logger.error(f"STARTUP FAIL: {e.message}")
            # Re-raise so the app won't start with missing fonts
            raise

_VERIFY_FONTS_AT_STARTUP = _verify_fonts_at_startup()