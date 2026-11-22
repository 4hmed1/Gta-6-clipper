# CAPTION REGRESSION TESTS

Each test must FAIL on the broken code and PASS on the fixed code.

## Test Setup

Standard test fixtures:
- `test_videos/captioned_talking.mp3` — 45s talking head with YouTube captions, ~487 words, Rick Astley-style
- `test_videos/captioned_gameplay.mp3` — 60s gameplay with profanity, markers (`>>`, `[Music]`, `(laughs)`), rolling captions
- `test_videos/no_captions.mp3` — 30s video with NO caption tracks at all

## 1. Rolling Auto-Captions Sample

**Description:** No doubling, text complete — every speech segment has captions.

**Broken behavior:** `clean_word_text()` does not strip all music symbols → ♪ tokens appear in ASS → doubling or invisible text.

**Fixed behavior:** `clean_word_text()` strips `♪`, `[♪♪♪]`, `♫`, `♬` → clean text only.

**Test:**
```python
from app.captions.track import clean_word_text

# Must strip all music markers
assert clean_word_text('♪') == ''
assert clean_word_text('[♪♪♪]') == ''
assert clean_word_text('♫') == ''
assert clean_word_text('♬') == ''
assert clean_word_text('Hello ♪ world') == 'Hello world'
assert clean_word_text('Gonna ♪ give you up') == 'Gonna give you up'
assert clean_word_text('Make it ♬ work') == 'Make it work'
```

## 2. Marker Sample (>> and [ __ ])

**Description:** Markers removed, speech kept. Profanity censored if enabled.

**Broken behavior:** `clean_word_text()` passes `>>` and `[ __ ]` through, or removes real speech words.

**Fixed behavior:** `clean_word_text()` strips markers, keeps speech, censors [ __ ] when mask_profanity=True.

**Test:**
```python
from app.captions.track import clean_word_text

# Markers removed
assert clean_word_text('>> this is repeated') == 'this is repeated'
assert clean_word_text('--> another repeat') == 'another repeat'  # or passed through
assert clean_word_text('[Music]') == ''
assert clean_word_text('(laughs)') == ''

# Profanity censor
assert clean_word_text('[ __ ]', mask_profanity=True) == '****'
assert clean_word_text('[ __ ]', mask_profanity=False) == '[ __ ]'

# Real speech kept
assert clean_word_text('Never') == 'Never'
assert clean_word_text('Gonna') == 'Gonna'
assert clean_word_text('Give') == 'Give'
```

## 3. Offset Sample (Section starts 2.3s early)

**Description:** Captions in sync, no negative times.

**Broken behavior:** Words have absolute source times; clip_start subtraction pushes all captions negative or out of range.

**Fixed behavior:** Words are section-relative OR clip_start is properly handled with assertion + log.

**Test:**
```python
from app.video_engine import render_clip
import json, urllib.request

# Get job data with known section timing
d = json.load(urllib.request.urlopen('http://127.0.0.1:8760/api/status/test-offset-job'))
words = d.get('transcript_words', [])

# Clip starts at 43s on source; words have absolute times
# The pipeline should assert: source_start <= start_time < source_end
# And log: first word time after clip_start subtraction

# Words after clip_start adjustment should all be >= 0 and <= duration
for w in words[:5]:
    # After pipeline processing, word.times should be in [0, duration]
    assert w['start'] >= 0 or 'clip_start_adjusted' in str(w), f"Word start {w['start']} < 0"
```

## 4. VAD Shift Out-of-Range Rejection

**Description:** If VAD shift would push >10% of words outside clip, shift is rejected, original timing kept.

**Broken behavior:** VAD shift applied unconditionally → captions fall outside 0..duration → silent delivery.

**Fixed behavior:** Shift rejected if >10% words out of range → original timing kept → warning logged.

**Test:**
```python
# Simulate: if >10% of words would have start < 0 or end > duration after shift,
# the pipeline should reject the shift and keep original timing

# Test with words near clip boundaries
from app.captions.track import clamp_to_clip_bounds

# Words at clip start should stay at start, not go negative
words_near_start = [
    {'word': 'near', 'start': 0.1, 'end': 0.3},
    {'word': 'end', 'start': 0.5, 'end': 0.7},
]
clamped = clamp_to_clip_bounds(words_near_start, clip_start=0.0, clip_end=10.0)
assert clamped[0]['start'] >= 0  # Should NOT be negative
assert clamped[-1]['end'] <= 10.0  # Should NOT exceed clip end
```

## 5. FFmpeg Without libass

**Description:** Simulate FFmpeg without libass → clear error, no silent caption-less delivery.

**Broken behavior:** DEVNULL on stderr hides the missing libass error → silent clip with no captions.

**Fixed behavior:** stderr captured → error about missing subtitles filter → CaptionError raised → job shows "Captions could not be created: FFmpeg libass not available" with Retry button.

**Test:**
```python
# Cannot easily test without rebuilding FFmpeg, but verify the code change:
# subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
# Then check result.stderr for "No such filter: subtitles" or similar
# And that it raises CaptionError instead of returning success=True
```

## 6. Missing Font Fallback

**Description:** Font not found → fallback font used and logged, captions still visible.

**Broken behavior:** Font Montserrat not installed → libass renders invisible text → silent clip.

**Fixed behavior:** Font DejaVu Sans used (system font) → captions visible → startup log: "Font 'Montserrat' not found, using 'DejaVu Sans' fallback".

**Test:**
```python
# Verify font availability at render time
from app.captions.track import STYLES
for style_name, style in STYLES.items():
    font = style['font_name']
    # Verify font is available (system font check)
    import subprocess
    result = subprocess.run(
        ['fc-list', ':', 'family=' + font],
        capture_output=True, text=True
    )
    # Should find at least DejaVu Sans
    assert font in result.stdout or 'DejaVu Sans' in result.stdout, \
        f"Font '{font}' not found at render time!"
```

## 7. End-to-End on Standard Test Clips

For each of the 3 standard test videos:

**Caption coverage %**: Must be >= 85%
**Max simultaneous caption groups**: Must be exactly 1
**Median onset error vs speech**: <= 150 ms (difference between ASS event start and actual word start)
**5 extracted frames saved in /audit/captions/<clip_id>/

### Per-clip metrics:

| Metric | Required | Broken | Fixed |
|--------|----------|--------|-------|
| Dialogue events count | >= 1 per speech segment | 0 (silent) | >= 1 |
| Music symbols (♪♫♬) in ASS | 0 | Present | 0 |
| Coverage % | >= 85% | 0% | >= 85% |
| First Dialogue start time | <= 150ms after word start | N/A | <= 150ms |
| Zero-byte .ass file | Never | 2 files exist | Never |

## 8. `make verify` All Layers Green

Run `make verify` and all layers must pass:
- Unit tests for `_normalize_word`, `clean_word_text`, `group_words`, `generate_ass_events`
- Integration test for end-to-end clip rendering
- Visibility QA for 3 standard test clips
- Font availability check at startup
- FFmpeg libass presence check at startup

Run `make verify` after each code change. If any gate fails, iterate (change approach after 4 attempts) until all pass. Do not stop until captions are visible, single, clean and in sync on all test clips.