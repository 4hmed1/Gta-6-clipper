# CAPTION VISIBILITY QA

Per-clip mandatory QA checkpoint that runs BEFORE delivery. Extends QAAgent.

## 1. Visibility Check

For each rendered clip, sample the ASS subtitles and the delivered MP4 at multiple timestamps:

### ASS-Only Rendering (black frame + ASS)
Render the ASS file alone on a black 1080x1920 canvas at 10 evenly-spaced timestamps INSIDE speech word segments, plus 3 timestamps in silence intervals.

**Procedure:**
1. From the word list, identify all speech segments (union of word intervals where `word` is not a marker/silence token)
2. Select 10 timestamps that fall inside speech segments (evenly distributed across total speech duration)
3. Select 3 timestamps that fall inside silence intervals (gaps between speech segments where no word starts for >1.0s)
4. For each timestamp, run: `ffmpeg -f lavfi -i color=black:s=1080x1920:r=1:d=<clip_duration> -vf "ass=<sub_path>" -frames:v 1 -f null -`
5. After each frame, extract the YMAX metadata (or pixel min/max in the caption region 100px from top, full width)
6. **PASS** if: Speech timestamps show text (YMAX > black level threshold, e.g., 20 out of 255), and exactly one caption group is visible
7. **FAIL** if: Silence timestamps show text when they shouldn't, or speech timestamps show zero text

### B. Final MP4 Comparison
Compare 5 sampled frames from the delivered MP4 against the same timestamps in a no-caption "twin" render.

**Procedure:**
1. Render a no-caption version of the same clip (user chose "No captions", or render with `--no-captions` flag)
2. Sample 5 timestamps from the delivered MP4
3. For each frame, extract the caption region pixels (top 100px to 400px, full width 1080)
4. Compare pixel values against the no-caption twin render
5. **PASS** if: Caption-visible time / speech time >= 85%
6. **FAIL** if: Coverage < 85%, OR more than one caption group visible simultaneously

## 2. Coverage Metric

```
caption_visible_time / speech_time >= 85%
```

Where:
- `speech_time` = total duration of union of word intervals (excluding markers and silence gaps)
- `caption_visible_time` = total duration where at least one ASS dialogue event is active

**If coverage < 85%:** Re-render with next fallback:
1. No VAD shift (original timing without VAD shift)
2. Accurate mode with faster-whisper on clip's audio
3. Plain style (minimal formatting)
4. If ALL fail: Deliver clip WITHOUT captions + explicit warning badge + "Retry captions" button

## 3. Single Caption Group Enforcement

At any given timestamp, there must be EXACTLY ONE active caption group visible.

**Check:** Sample 20 timestamps across the clip duration. Count how many ASS dialogue events have `start <= timestamp <= end` at each sample point.

**If >1 group visible simultaneously:** Re-render with tighter pause_threshold and max_words_per_group settings, or increase group separation. Never deliver with overlapping captions.

## 4. End-to-End Pixel Verification

After rendering and QA pass:

1. Save 5 frames from the delivered MP4 at timestamps: 10%, 25%, 50%, 75%, 90% of clip duration
2. Also render the same 5 timestamps from the ASS-only render
3. Save all frames to: `/audit/captions/<clip_id>/`
   - `/audit/captions/<clip_id>/frames_mp4/frame_X.png`
   - `/audit/captions/<clip_id>/frames_ass/frame_X.png`
4. In the UI, show the audit data for each clip

## 5. `clipforge captions-debug <clip_id>` Command

New CLI command that prints complete pipeline diagnostics:

```
Usage: clipforge captions-debug <clip_id>
```

Output sections:
1. **Stage counts**: raw words from json3 → cleaned words → after de-roll/dedupe → after timing repair → after offset/VAD shift → caption groups
2. **ASS head**: first 20 lines of generated .ass file (header + first Dialogue events)
3. **FFmpeg command**: exact command line used for subtitle rendering
4. **libass status**: `ffmpeg -hide_banner -filters | grep -E " ass | subtitles "` 
5. **Visibility numbers**: coverage %, speech time, caption-visible time, max simultaneous groups
6. **Font resolution**: which font is being used and whether it resolves at runtime

## 6. Failure Handling

If QA fails at any step:
- Log the failure with stage name and reason
- Show user: "Captions could not be created properly: <reason>. Click Retry to regenerate."
- Provide "Retry captions" button in the job card
- If all 3 fallbacks fail: deliver without captions, but show warning badge and Retry button
- NEVER silently deliver a clip with zero visible captions when the user expected them