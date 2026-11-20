# ROADMAP — GTA 6 Clipper

Everything below is NOT in v0.1.0-beta. It is listed here so users know what is
planned and what is intentionally cut from this release.

## In v0.1.0-beta (DONE)
- ✅ Paste a YouTube link → ranked, captioned 9:16 Shorts in ~2 minutes
- ✅ YouTube captions (json3 word timing) — no Whisper needed for captioned videos
- ✅ Optional offline STT (faster-whisper) for videos without captions
- ✅ Clip selection: deterministic heuristics (hooks, speech density, energy, heatmap)
- ✅ 1080×1920 vertical output with kinetic captions inside platform safe zones
- ✅ One-command install (PowerShell / bash), `clipforge doctor`, auto FFmpeg download
- ✅ Library with progressive results, job deduplication, stuck watchdog
- ✅ Plain-language errors with fix buttons

## Known limitations of v0.1.0-beta
- **No editor**: clips are cut and rendered by the pipeline. Trimming/caption editing
  requires re-running the pipeline with new settings. (Full CapCut-style timeline
  editor is on the roadmap.)
- **No mobile companion / PWA**: the app runs on desktop only (Windows/macOS/Linux).
- **No batch queue for many videos**: one video at a time.
- **No direct publishing/scheduling**: clips are saved locally; you upload manually.
- **No multi-speaker tracking**: captions are treated as a single stream.
- **No SEO/GEO/AEO static site**: this is a GitHub repo, not a marketing site.
- **No extra caption style packs or brand kits**: the built-in styles are the only ones.

## Next 10 improvements (ranked by impact)
1. **Timeline editor** — trim, split, speed, caption drag, undo/redo, autosave, export
   that matches preview. (Release 0.2)
2. **Batch queue** — process a channel or a list of URLs, one render at a time.
3. **Mobile PWA companion** — pair your phone to the desktop app via QR code.
4. **Watch-a-channel** — auto-clip new uploads from a subscribed channel.
5. **Extra caption style packs** — user-installable ASS style bundles.
6. **Brand kits** — saved logo, fonts, colors, watermark presets.
7. **Direct publishing** — OAuth scheduling to TikTok/YouTube/Instagram (Pro).
8. **Multi-speaker tracking** — distinguish speakers in interviews/podcasts.
9. **SEO/GEO/AEO site** — standalone marketing site with schema JSON-LD.
10. **Priority support** — Pro license key with offline verification.

## Pro extension point
A `pro/` directory will hold a license-key check (offline-verifiable signed keys,
no phone-home) gating: extra caption style packs, brand kits, batch queue,
watch-a-channel, direct publishing, multi-speaker tracking, priority support.
The core stays free and honest — no nagging, no feature crippling.
