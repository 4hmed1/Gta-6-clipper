# PREMIUM LOOK MASTER PROMPT

## 0. MISSION AND RULES

Make every delivered clip look like it was cut by a professional editor: full-frame composition, crisp footage, bold clean captions with tasteful motion, balanced loud audio. The owner says current results look cheap. Fix that with measurable gates, not opinions.

Rules (always):
1. **Evidence or it did not happen.** Apply changes with the edit tool; show `git diff`, real commit hashes (`git log -1`), real command output, real file paths. Never invent hashes, test names, numbers or paths. Restart the server after backend changes. Never mark anything VERIFIED unless `scripts/check_evidence.py` passes for it.
2. No LLM/paid API in clip selection or editing decisions. Classical CV/DSP only (OpenCV Haar/YuNet-free classical detection, NumPy, FFmpeg filters). No AI upscaling.
3. Do not break what works: captions are visible and in sync, one caption group at a time, clips have sound. Every change must keep `make verify` green.
4. Target machine: 4th-gen Intel i5, 8 GB RAM, no GPU. Therefore quality TIERS (Section 4) with honest render-time budgets.
5. Use only open-license fonts and assets (SIL OFL), bundled in `assets/fonts/` with license files.
6. If you can view images, inspect contact sheets yourself and critique them against the rubric in Section 8; if you cannot, rely on the metrics and save the sheets for the owner.

## 1. MEASURED PROBLEMS IN THE CURRENT OUTPUT (from the owner's real clips and code)

- **Tiny foreground.** In the owner's clip (1080x1920) the footage is a 1080x608 strip in the middle, about one third of the frame; two thirds are blurred bands. This is the main reason it looks cheap.
- **Weak encode.** The render uses `-preset ultrafast -crf 28`; the owner's clip is about 4.5 Mbps at 29.97 fps. That causes blocking and mush, especially in motion and dark scenes.
- **Soft source.** When the connection is slow the section is downloaded at 480p and then upscaled to 1080 wide with the default scaler: soft and noisy.
- **Cheap captions.** The font fell back to DejaVu Sans (a commit switched Montserrat to DejaVu), the size is small, there were two caption elements visible at once (a small yellow word on the video and a large word in the bottom band), and highlight uses plain `\k` sweeps with scale jumps.
- **No finishing:** no color grade, no sharpening, no hook, no motion, no audio mastering, no smoothing of cuts.

## 2. LAYOUT ENGINE (replace the single "split_blur" layout)

Create `render/layouts.py` with pure functions that return a crop/scale plan (rectangles, scale factors, keyframes) which is then compiled into ONE FFmpeg filter graph. Modes and the automatic choice:

**AUTO decision (per clip, from sampled frames at 2 fps):**
1. Facecam detection: run a classical face detector on 8-12 sampled frames; a face region that stays within +/-4% of the same position in at least 70% of frames and is smaller than 35% of the frame area means FACECAM overlay. A large face that moves with the scene means TALKING HEAD. No stable face means GAMEPLAY/OTHER.
2. Choose: facecam => STREAM SPLIT; talking head => FACE-FOLLOW FILL; 16:9 gameplay/other => CINEMATIC FILL; fallback => CLASSIC (blur-fit, only if all else fails). The user can override in the wizard.

**STREAM SPLIT (1080x1920):**
- Top region 1080x1180: gameplay, scaled to cover the region with a smart horizontal crop window (center-biased, follows the action; see tracking below). Remove the facecam rectangle from the gameplay crop only if it would sit inside the window (otherwise it is cropped away naturally).
- Bottom region 1080x740: the facecam, cropped around the detected face with 30-40% padding, scaled to cover, lightly sharpened.
- Between regions: a 6 px accent line or a soft 24 px gradient shadow, rounded outer corners optional. No blurred empty bands at all.
- Captions sit at the boundary band (centered at y about 1180, within the lower part of the gameplay region), never over the face.

**FACE-FOLLOW FILL:** crop a 9:16 window (source height scaled to 1920, window 1080 wide) centered on the tracked face/upper body, filling the whole frame. Headroom rule: eyes at about 38-42% from the top. Captions in the lower third.

**CINEMATIC FILL (default for gameplay without a facecam):** the footage is scaled so it is at least 1080x1350 (4:5) crop of the source centered on the action, placed at y 285..1635, with a very soft, dark, low-contrast blurred extension above and below (blur sigma large, brightness -25%, dithered to avoid banding) and a subtle vignette. Foreground must cover at least 70% of the frame height. Add a second option "FULL BLEED" that fills 1080x1920 with a 9:16 crop when the user chooses it.

**Tracking (for all crop windows):** estimate the point of interest per 0.5 s (face position, else motion centroid from frame differences, else center). Smooth with a Kalman/EMA filter, dead zone 3% of width, maximum pan speed 180 px/s (at 1080 width), ease-in/out on pans, instant reset at scene cuts (detected via scene score). Export the path as keyframes and apply with FFmpeg expressions (`crop=w:h:x='...':y='...'` with a piecewise-linear or smoothstep expression) in the same filter graph. No per-frame Python.

**Safe areas:** keep important content and text inside x 60..1020 and y 220..1560 (Shorts/TikTok/Reels UI). Hook text may use y 180..420.

## 3. SOURCE QUALITY AND SCALING

- Format choice: with measured speed >= 0.8 MB/s prefer 1080p (or 720p60 -> 30 fps) for sections; >= 0.4 MB/s 720p; below that 480p. Show the chosen resolution in the job log and the card ("Source 720p"). Never silently pick lower than necessary.
- Scaling: `scale=...:flags=lanczos+accurate_rnd+full_chroma_int` for the foreground; the blurred extension may use bicubic at low resolution.
- Clean-up for YouTube compression artifacts (Balanced/Premium): `hqdn3d=1.2:1.2:3:3` (light), then `unsharp=5:5:0.7:5:5:0.0` (luma sharpen, tuned per tier), then `gradfun=1.2` or small temporal noise (`noise=alls=3:allf=t`) on blurred areas to kill banding.
- Color: tag and keep BT.709; subtle grade `eq=contrast=1.05:saturation=1.10:gamma=0.98` and a gentle S-curve via `curves` (lift shadows 0.02, highlights -0.02). No heavy filters that change the look of game footage. Allow "Natural / Vivid / Cinematic" looks that only change these constants.
- If the source is 480p: be honest in the UI ("Source quality is limited"), apply the milder sharpen, and recommend the Premium tier only when the source is >= 720p.

## 4. ENCODE TIERS (per clip, user selectable, default Balanced)

| Tier | x264 settings | Rate control | Target time on the i5 for a 45 s clip |
|---|---|---|---|
| Fast | `-preset veryfast` | `-crf 23 -maxrate 8M -bufsize 16M` | <= 60 s |
| Balanced (default) | `-preset faster` | `-crf 20 -maxrate 10M -bufsize 20M` | <= 150 s |
| Premium | `-preset medium` | `-crf 18 -maxrate 14M -bufsize 28M` | <= 6 min, runs in the background after Balanced is shown |

Common: `-pix_fmt yuv420p -profile:v high -level 4.2 -r 30 -g 60 -bf 2 -x264-params aq-mode=3:aq-strength=0.9:deblock=-1,-1 -colorspace bt709 -color_primaries bt709 -color_trc bt709 -movflags +faststart`. Audio AAC 192 kb/s 48 kHz stereo. Measure the real render time per tier on this machine, write it to PREMIUM_REPORT.md, and show estimates in the UI before rendering. Provide "Upgrade to Premium" on each finished clip (re-render in the background). Never freeze the UI: render at lowered priority.

## 5. CAPTION SYSTEM (rebuild the look; keep the verified timing and QA pipeline)

**Fonts:** download and bundle (SIL OFL) Montserrat ExtraBold/Black, Anton, Bebas Neue, Inter ExtraBold, Poppins ExtraBold, Archivo Black into `assets/fonts/` with licenses; always pass `fontsdir=` to libass; at startup verify every style font resolves (log `fontselect`) and FAIL the style with a clear error if it does not (no silent fallback to DejaVu).

**Typography rules (all styles):** uppercase optional per style; 2-3 words per group (max 4), max 2 lines, max about 14 characters per line; font size 88-108 px at 1080 width (measure real text width with Pillow and shrink to fit the safe width 900 px); line spacing 0.95; outline 7-9 px (rounded joins), soft shadow (blur 10, offset 4, 60% black); keep text inside the safe area; avoid single-letter widows and break at punctuation or natural pauses; numbers and strong words get the emphasis color.

**Motion:** pop-in scale 85% -> 108% -> 100% over 140 ms using `\t` with acceleration, fade-out 60 ms, caption appears 50 ms BEFORE the first word (anticipation) and stays until the next group starts (never overlaps). The active word is highlighted by color (not by scale jumping the whole line). All highlight is inside ONE Dialogue event per group (no second layer, no stacked duplicates). If the style uses a background box, draw it as an ASS drawing or `BorderStyle=3` with padding; keep corners rounded where supported.

**Six launch styles (exact colors; shipped as `styles/*.yaml`):**
1. **Clean Pop:** Montserrat ExtraBold 96, white text, active word #FFD60A, outline black 8, shadow soft.
2. **Bold Impact:** Anton 112, white, active word #FF3B30, outline black 9, uppercase, slight tracking +1.
3. **Neon Edge:** Poppins ExtraBold 92, white fill, outline #00E5FF 6 plus glow (blur 8 duplicate underneath), active word #FF2DAA.
4. **Minimal Lower Third:** Inter ExtraBold 84, white on a 55% black rounded box with 18 px padding, active word underline accent #3DDC84.
5. **Karaoke Gold:** Archivo Black 96, white to #FFC300 left-to-right sweep per word (`\kf`), outline #1A1A1A 8.
6. **Gaming Glow:** Bebas Neue 120, #F5F5F5 with outline #111 8, active word #7CFF00 with a subtle outer glow.
Plus "No captions". Each style has a live preview in the wizard rendered from a real frame of the chosen video.

**Keyword emphasis (rule-based):** numbers, "never/always/first/biggest" style superlatives, game keywords (from the YAML pack) and ALL-CAPS tokens use the emphasis color; max 1 emphasized word per group.

**Collision avoidance:** captions never overlap the facecam, the hook title, or the bottom 220 px UI zone; if the footage has a bright/busy caption zone, switch automatically to the style's boxed variant when contrast is below the gate in Section 8.

## 6. EDIT POLISH

1. **Hook title (optional, default ON for Premium/Balanced):** generated from the top keywords/hook sentence (template based, max 7 words), shown 0.0-2.4 s at y about 260, bold, animated in (slide/fade 220 ms), ends before the first caption group overlaps it, never over the facecam.
2. **Cold open:** start the clip at the strongest word/sound of the moment (cut dead air before it; keep a 0.12 s pre-roll), end on the payoff plus 0.35 s tail with a 150 ms audio fade-out.
3. **Subtle motion:** slow push-in 100% -> 105% over the clip (smoothstep), plus a quick 6% punch-in (150 ms ease-out) on emphasized words or hard cuts. Apply to the foreground via the same crop/scale expressions. Turn off automatically for clips with strong camera motion.
4. **Jump cuts / tightened pauses:** remove silences > 0.6 s and filler words using word timings; crossfade audio 20-30 ms at each cut; add a 2-frame punch-in at the cut so it feels intentional; re-time captions after cuts.
5. **Progress bar (optional):** 6 px bar at the top or bottom in the accent color, below the UI safe zone, easing.
6. **Frame-accurate start/end,** no black frames, no half-captions at cut points.

## 7. AUDIO MASTERING (per clip)

Chain: `highpass=f=80`, optional light `afftdn=nr=10:nf=-40` for noisy sources, `acompressor=threshold=-18dB:ratio=3:attack=5:release=80:makeup=2`, `loudnorm=I=-14:TP=-1.5:LRA=9` (two-pass measured when time allows, else single pass), `alimiter=limit=0.89`, 30 ms fade in and 150 ms fade out. Targets: integrated loudness -14 LUFS +/-1, true peak <= -1.0 dBTP, no clipping, A/V start offset <= 0.05 s.

## 8. VERIFICATION HARNESS: `make premium-eval` (automatic gates + owner rubric)

Run on THREE source segments each time: (a) gameplay with a facecam (like the owner's GTA 6 stream clips), (b) gameplay without a facecam, (c) a talking head. For each, render BEFORE (current code, saved as the baseline) and AFTER (all tiers). Save to /audit/premium/<segment>/: contact sheet (12 evenly spaced frames, 6x2 tile), a caption-zone strip, the .ass, ffprobe JSON, loudness report, and a side-by-side before/after frame at 5 timestamps.

**Automatic gates (all must pass for Balanced; Premium must also meet the higher bitrate):**
- Foreground coverage: footage pixels cover >= 70% of the frame area (CINEMATIC/FACE-FOLLOW) or the two regions cover >= 92% (STREAM SPLIT); no region of blurred filler taller than 14% of the frame in any mode except CLASSIC fallback (which must be flagged as a fallback).
- Video bitrate (1080x1920, 30 fps): Balanced >= 7 Mbps, Premium >= 10 Mbps; resolution exactly 1080x1920; codec h264 high profile; BT.709 tags present.
- Sharpness: mean Laplacian variance of the foreground >= 90% of the source frame scaled to the same size (no softening), without clipping halos (overshoot gate).
- Banding: in the blurred areas the number of unique luma levels per 100 px gradient >= 40 (dither working).
- Captions: font resolves to the bundled file (from libass log); font size >= 4.5% of frame height; exactly ONE group at any time; coverage >= 85% of speech time; median onset error <= 150 ms; all text inside the safe area; text-to-background contrast >= 4.5:1 sampled at 10 timestamps (use the box variant if lower); never overlapping the facecam or the hook.
- Motion smoothness: crop-path max speed <= 180 px/s and max acceleration within limits; no jitter (second derivative gate).
- Audio: -14 +/-1 LUFS, true peak <= -1.0 dBTP, volumedetect mean > -35 dB for speech clips.
- Render time within the tier budgets in Section 4 (report real numbers).

**Owner rubric (Premium Score 0-100, shown in the report and as a badge on each clip):** composition 25, caption quality 25, image quality 20, audio 15, polish (hook, motion, cuts) 15. Compute the objective parts from the gates; list the subjective parts as "owner check" lines. If you can view images, write a short critique of each contact sheet and fix the weakest area, then repeat. Loop until all automatic gates pass on all three segments.

## 9. UI

- Wizard: "Look" presets (Clean, Bold, Cinematic, Gaming, Minimal, Hype) mapped to a layout + caption style + color look; "Quality" selector (Fast / Balanced / Premium) with the real estimated render time; "Layout" override (Auto, Stream Split, Face-Follow, Cinematic, Full Bleed, Classic). A one-frame live preview of layout + captions rendered from the real video (FFmpeg single frame, under 3 s) and a before/after slider.
- Clip cards: Premium Score badge, source resolution badge, "Upgrade to Premium" and "Change look" actions (re-render without re-downloading).
- Keep honest labels; no fake claims.

## 10. DELIVERABLES AND ORDER

1. Baseline: render the three segments with the current code into /audit/premium/before/ and write the measured numbers to PREMIUM_BASELINE.md (real output only).
2. Fonts bundled and verified; caption styles rebuilt; style tests (one group, safe area, font resolution).
3. Layout engine + tracking + AUTO decision with unit tests on synthetic frames and real sources.
4. Encode tiers + scaling/cleanup/grade + audio chain; measure render times.
5. Edit polish (hook, cold open, motion, cut smoothing, progress bar).
6. `make premium-eval` + gates; iterate until all automatic gates pass on all three segments.
7. UI changes (look presets, quality tier, live preview, badges).
8. Write PREMIUM_REPORT.md: before/after contact sheets and numbers for every gate, per-tier render times, known limits (480p sources stay soft; the weak CPU makes Premium slow), and what could not be verified. Then run `make verify` and show it green.
9. Ask the owner to open the three AFTER contact sheets and one full clip and answer: "Does it look professional? What is still weak?" and loop on the answer.

Start with step 1 now. Do not stop and summarize; continue until step 8 is true, reporting real numbers after every step. complete all this tings and make sure all this tings are wrtking properly