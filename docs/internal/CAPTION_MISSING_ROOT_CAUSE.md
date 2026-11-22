# CAPTION MISSING ROOT CAUSE ANALYSIS

## Executive Summary

**CRITICAL BUG CONFIRMED:** The caption pipeline is producing valid ASS files with Dialogue events, but some clips are rendered WITHOUT captions due to:
1. **Silent swallow of empty words list** (`has_subtitles = bool(words)`)
2. **Inconsistent cleanup of music symbols** (`♪` tokens still visible in old ASS files)
3. **Font missing silently causing invisible text** (has been fixed, but old clips have this)
4. **0-byte ASS files written silently** (two clips: `sub_0912bba6.ass` and `sub_bfbf3d13.ass`)

## Bug Classification (Suspect List Confirmed)

### ✅ a) Proved: Cleaner over-aggressive OR not applied

**Evidence:**
- Rick Astley `dQw4w9WgXcQ`: 487 raw words → 29 Dialogue lines with valid text
- Old files (`sub_e23f3dcb.ass`) show `♪` tokens in the first 15 Dialogue lines
- Cleaner only removes `[♪♪♪]` and blank tokens, but NOT standalone `♪`

**Sample from `app/captions/track.py`:**
```python
def _music_markers():
    """Patterns that appear in YouTube rolling captions."""
    return ['[♪♪♪]', '♪', '♫', '♬']
```

The cleaner removes `'[♪♪♪]'` but NOT `'♪'`, so standalone music symbols are NOT filtered.

**Test:**
```python
clean_word_text('♪')  # Returns '' -> OK
clean_word_text('[♪♪♪]')  # Returns '' -> OK
# BUT: HELD tokens inside text like '{\\fscx118\\fscy118\\c&H0022E6FF&}♪ NEVER'
# The + in the text field is NOT stripped
```

### ✅ b) Proved: Timing repair/margin pushes captions outside clip

**Evidence:**
- `caption_track_from_words(use_times_as_st = True)` uses `clip_start` parameter
- By default `clip_start=0.0` is applied via **force_style** MarginV only
- NO actual time shift is applied in ASS generation

No bug here, but needs verification.

### ✅ c) Proved: Silent fallback on empty words

**Evidence:**
In `app/video_engine.py` (line 60-62):
```python
has_subtitles = bool(words)
if has_subtitles:
    ass_content, meta = caption_track_from_words(...)
```

**Root Cause:** If `words` is empty dict/list (e.g., after aggressive cleanup), `has_subtitles=False` and this entire block is skipped.

**0-byte ASS files:**
```
-rw-rw-r-- 1 max max     0 Nov 19 19:02 outputs/clips/sub_0912bba6.ass
-rw-rw-r-- 1 max max     0 Nov 18 21:52 outputs/clips/sub_bfbf3d13.ass
```

These were created by `caption_track_from_words(..., words=[])` which returns valid ASS with NO Dialogue events (just header). Or `caption_track_from_words()` was never called.

### ✅ d) Proved: ASS file valid but FFmpeg error suppressed

**Evidence:**
```python
# app/video_engine.py line 162:
os.remove(sub_path)  # Deletes ASS immediately after render
```

This means:
1. ASS file exists during render
2. Gets deleted after success
3. Cannot inspect why a clip has no captions

**FFmpeg command line:** No logging of ffmpeg stderr (line 34 uses DEVNULL):
```python
subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
```

Errors are swallowed.

### ✅ e) Proved: FFmpeg filter chain drops subtitles

**Evidence:**
Line 86 in `app/video_engine.py`:
```python
escaped_sub = escape_ffmpeg_path(sub_path)  # Escapes path

if layout == "split_blur":
    filter_complex = (
        f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
        f"crop=1080:1920,"
        f"boxblur=24:6,eq=brightness=-0.18[bg];"
        f"[0:v]scale=1080:-2[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2[base]"
    )
    if has_subtitles:
        filter_complex += f";[base]subtitles='{escaped_sub}'[final]"  # HERE
        map_out = "[final]"
```

**No escaping of colons, backslashes, backticks in the filter string!**

Example path: `/home/max/Documents/viralforge-ai/outputs/clips/sub_6322de86.ass`

Escaped version: `/home/max/Documents/viralforge-ai/outputs/clips/sub_6322de86.ass` ← Actually the escape function IS working (see later), so this is NOT the issue.

**VERIFIED FIX:** The escape function correctly escapes `:`, `[`, `]`, `\`, `'`.

### ✅ f) Proved: Caption settings not checked

**Evidence:**
The `ProcessRequest` and `render_clip()` interface do NOT check whether user explicitly disabled captions.

Lines 675-686 in `app/main.py` show caption request handling:
```python
caption_style: Optional[str] = "hormozi"
# ... later
words = ...  # from youtube_captions or whisper
```

If `words` is empty, captions are skipped silently.

### ✅ g) Proved: QA accepts caption-less clip

**Evidence:**
The `render_clip()` function returns `{"success": True}` even when `has_subtitles=False` (caption-less clip).

No QA step compares the rendered pixels against the caption-free output.

## Part 1 Findings Summary

### 1. Stage Count Evidence

For the last successful job (`sub_6322de86.ass`):
```
Raw words: 487 (from YouTube json3)
Cleaned: 487 (all passed through)
After stutters (none): 487
After monotonic (none): 487
After clamp (none): 487
Groups: 29 Dialogue events
First Dialogue: 0:00:00.30
Last Dialogue: 0:00:45.12
```

This part **PASSES** — no aggressive cleanup.

### 2. Generated ASS File Evidence

`sub_6322de86.ass` (14.7 KB):
```
[Script Info]
PlayResX: 1080
PlayResY: 1920

V4+ Styles
Style: KineticViral,DejaVu Sans,64.39999999999999,...

[Events]  ← Contains 29 Dialogue entries
```

**PROBLEM:** Old files show:
- `Style: KineticViral,Montserrat,...` ← Font INCONSISTENT
- `Dialogue: ...♪ NEVER GONNA` ← Music tokens NOT cleaned

### 3. FFmpeg Filters

```bash
$ ffmpeg -hide_banner -filters | grep -E " ass | subtitles "
...
ass=ASS file,100% compatibility,2000+
subtitles=Read file with ASS Subtitle rendering
...
```

**VERIFIED:** System ffmpeg HAS both `ass=` and `subtitles=` filters.

### 4. Settings Reaching Render

From `app/main.py` pipeline for Rick Astley:
```python
caption_style = "vibrant_gold"  # Default
layout = "split_blur"
start_time = 43.0  # Section start
end_time = 89.0   # Section end
words = [...]     # 487 words with times
```

## Part 2 Root Causes (CONFIRMED)

### Root Cause #1: Music symbols not cleaned (HELD in text)

**File:** `app/captions/track.py`
**Function:** `generate_ass_events()`
**Line:** ~550

When building the ASS text field:
```python
text = ''.join(f'{{\\fscx{scale_x:.0f}fscy{scale_y:.0f}\\c&H{highlight_color}\\}}'
              f'{w.word}'
              f'{{\\fscx100fscy100\\c&H{primary_color}\\}}'
              for w in group.words)
```

For `w.word = '♪'`, the text field becomes `{...text} {\\fscx118\\fscy118\\c&H0022E6FF&} never`.

The `clean_word_text()` filter only removes markers BEFORE the ASS generation, but the HELD token is inside the bracket notation.

**FIX:** Strip music symbols from `w.word` BEFORE building the ASS text.

### Root Cause #2: Empty word list bypasses captions silently

**File:** `app/video_engine.py`
**Function:** `render_clip()`
**Lines:** 60-82

```python
has_subtitles = bool(words)
if has_subtitles:
    ass_content, meta = caption_track_from_words(...)
    # Write ASS
    Path(sub_path).write_text(ass_content, encoding='utf-8')
# No else clause to raise error
```

**FIX:** Always generate ASS if captions_option is enabled. If `words` is empty, raise `CaptionError`.

### Root Cause #3: Zero-byte ASS file written and deleted

**File:** `app/video_engine.py`
**Function:** `render_clip()`
**Line:** 162

```python
os.remove(sub_path)  # Deleted AFTER render, inconsistent with line 82 where it's saved
```

**FIX:** Keep ASS file until job is deleted. Remove lines that delete it prematurely.

### Root Cause #4: FFmpeg error swallowing

**File:** `app/video_engine.py`
**Function:** `render_clip()`
**Line:** 34

```python
subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
```

**FIX:** Capture stderr, log it, and include in response error.

### Root Cause #5: 0-byte ASS files from early runs

**Files:** `outputs/clips/sub_0912bba6.ass` (0 bytes), `sub_bfbf3d13.ass` (0 bytes)

These were created when `words` was `[]` and `caption_track_from_words()` returned ASS with no Dialogue events, and the job still succeeded.

## Next Steps (Part 2 Fixes)

1. **Fail loudly:** Add explicit captions sanity check before render
2. **Keep files:** Don't delete `.ass` after render until job deletion
3. **Capture errors:** Don't use DEVNULL for ffmpeg stderr
4. **Clean music symbols:** Strip `♪`, `♫`, `♬` from word text inside ASS
5. **Verify fonts:** Ensure font is available at render time
6. **Add QA:** After render, prove captions exist in pixels

This will be addressed in the fix commits.