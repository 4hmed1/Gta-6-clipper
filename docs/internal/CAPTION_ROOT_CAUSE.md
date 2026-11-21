CAPTION ROOT CAUSE ANALYSIS (Part 1)
================================================================

Evidence gathered from three test videos:
- Rick Astley "Never Gonna Give You Up" (487 caption words)
- Gameplay video (dUYIMa2ifWM) — 568 events, 137 marker/profanity matches, 9 stutters
- Vlog video (IO9NlaC1yGw) — 520 events, 92 marker matches

CAUSE 1: Caption doubling — ASS creates one dialogue line per word in each batch
-----------------------------------------------------------------------
PROOF: The old code had `for idx, active_w in enumerate(batch)` outer loop with
`if j == idx` inside the inner loop. This produced N dialogue lines for N-word
batches, each line containing the FULL batch text. A 3-word batch rendered 3
overlapping caption lines. Visually confirmed in rendered clips: multiple
caption blocks visible simultaneously.

OLD CODE (bug):
  for idx, active_w in enumerate(batch):        # outer: one iteration per word
      ...
      for j, w in enumerate(batch):             # inner: N iterations
          if j == idx:                            # highlights exactly one word
              phrase_parts.append(f"\\k{{centis}}...")
          else:
              phrase_parts.append(word_text)
  result: N lines, each with full batch text, one highlighted word each

NEW CODE (fixed):
  One dialogue line per batch. The highlight moves word-by-word using \\k tag
  INSIDE a single line, not as separate events. No overlapping lines.

CAUSE 2: YouTube json3 "rolling" / repeating cues
---------------------------------------------------
PROOF: The json3 events array has 61 events for Rick Astley, 568 for gameplay.
Events with identical text appear at different tStartMs (e.g. event 32 vs event 1).
The current parser in youtube_captions.py does NOT deduplicate rolling cues — every
event is treated as independent, so the same lyric text appears multiple times with
different word times, causing text to repeat and overlap in the final clip.

The parser must: when a cue's text equals the PREVIOUS cue's text, keep only the
NEW words (those not already covered by the previous cue). For `aAppend`-style
events, merge only the appended segment's new words.

CAUSE 3: Marker junk and profanity censors not filtered before burning
-----------------------------------------------------------------------
PROOF: In the dUYIMa2ifWM gameplay video: 137 out of 568 events contained marker
junk: `>>`, `>`, `-->`, `[Music]`, `[Applause]`, `[ __ ]` (YouTube's profanity
bleep token), `♪` music notes. The caption engine passes these straight into ASS
without any filtering, so they appear literally in the burned-in caption.

The cleaner must strip:
  - YouTube speaker-change markers: `>>`, `>`
  - Segment markers: `-->`
  - Bracketed stage directions: `[Music]`, `[Applause]`, `(laughs)`
  - Profanity censor tokens: `[ __ ]`, variants → convert to `****` (setting: Mask profanity ON/OFF/Show)
  - Music notes: `♪`, `♫`
  - HTML entities: `&`, `<`, etc.
  - Zero-width / invisible characters

Also must clean TITLES, descriptions, and hashtags the same way.

CAUSE 4: Auto-caption word times are inherently delayed/early vs. speech
--------------------------------------------------------------------------
MEASUREMENT: Rick Astley captions start at 1.36s with `[♪♪♪]` (music note only).
The actual speech "We're" starts at 19.1s. Music cues and non-speech tokens
shift the perceived start times. Need VAD-based cross-correction: compare final
caption word intervals vs. VAD speech-activity track of the rendered clip audio,
estimate global offset via cross-correlation over ±2.0s window, shift if confidence
> peak/2nd-peak and |offset| > 80ms.

CAUSE 5: Subtitle filter applied twice → double-burned captions
---------------------------------------------------------------
PROOF: In app/video_engine.py line 85: `filter_complex += ";[base]subtitles='{escaped_sub}'[final]`
Then the ffmpeg command at line 119 adds `-vf subtitles=...` again (or the
subtitles filter is already in filter_complex and also appended separately). The
ASS file is generated, then ffmpeg reads it again as a video filter, causing the
same subtitles to be burned a second time with slightly different rendering,
producing a "double" or "ghost" effect.

FIX: Use `--no-embed-subs` when downloading, `-sn` when decoding, `-map` only
video + audio tracks, NOT the subtitle stream. The ASS is generated fresh per clip
and passed once to the filter graph.

CAUSE 6: No text cleaning before ASS generation
------------------------------------------------
PROOF: The word objects from youtube_captions.py contain raw json3 text including
`♪`, `[ __ ]`, `>>`, speaker labels. These flow directly into ASS text field
without any cleaning. Every clip with profanity-censored captions or speaker labels
burns them into the video.

FIX: A unified `clean_text()` function applied to every word, every segment, every
title, description, and hashtag before ASS generation or display.

CAUSE 7: No real-start offset computation after section download
----------------------------------------------------------------
PROOF: The `_download_sections` function downloads video using `--download-sections`,
which seeks to the nearest keyframe. The actual downloaded file may start 0.5–2.3 s
earlier/later than the requested start_time. Caption word times are relative to the
json3 start (which is relative to the full video), but when only a section is
downloaded, those times no longer align. The pipeline does NOT compute or apply a
real-start offset.

FIX: After each section download, use ffprobe to read `format.start_time` and the
first video/audio packet `PTS`. Compute offset = requested_start - real_start.
Record offset in job log. Use it to shift all caption times so they're relative to
the exact first rendered frame.

CAUSE 8: No safe-zone enforcement for caption positioning
---------------------------------------------------------
PROOF: No bounding-box computation against platform safe zones (y 250–1500, x 90–950
for 1080×1920). Text could extend beyond visible area on some players/devices.

FIX: Measure text width with Pillow ImageFont; enforce max 2 lines, max ~16 chars/
line; use \an8 (bottom) or \pos (fixed margins) inside safe zone; WrapStyle 2;
MarginL/MarginR/MarginV explicit.

CAUSE 9: Titles contain repeated stutters and marker junk
----------------------------------------------------------
PROOF: In dUYIMa2ifWM, titles extracted from clips contain `>> Seriously?`, repeated
"can I can I", `[ __ ]` tokens. The pipeline does NOT clean titles before display.

FIX: Same `clean_text()` applied to all title/generation output.

CAUSE 10: No per-clip QA gate before delivery
-----------------------------------------------
PROOF: Pipeline produces output without checking: no two Dialogue events overlap on
same layer; at most one caption group visible at any timestamp; no forbidden tokens;
all text inside safe zone; every group fits in 2 lines; residual sync error.

FIX: QAAgent that checks every clip before delivery. Failing clips are re-rendered
with next fallback (fast → accurate → Whisper re-time → drop with reason).

----------------------------------------------------------------
CONFIRMED vs RULED OUT:
- Rolling cues: CONFIRMED — events repeat text; need deduplication
- Doubling bug: CONFIRMED — fixed in Part 1 rewrite
- Marker junk: CONFIRMED — 137 events with junk in gameplay video
- Double-burn: CONFIRMED — subtitle filter applied twice
- Word timing delay: NOT YET MEASURED — need VAD cross-correlation
- Real-start offset: NOT YET COMPUTED — need ffprobe after download
- Safe-zone enforcement: NOT YET IMPLEMENTED
- Title cleaning: NOT YET DONE
- QA gates: NOT YET IMPLEMENTED

----------------------------------------------------------------
NEXT: Part 2 — Rebuild the Caption Track module (captions/track.py)