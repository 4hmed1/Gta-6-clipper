# Troubleshooting

Run `maxclipper doctor` first — it checks Python, FFmpeg, encoders, disk, ports and permissions and prints a clear PASS/FAIL per item with a suggested fix.

## "YouTube thinks you're a bot" / sign-in required

yt-dlp occasionally hits a bot-check. The app tries multiple player clients automatically (android → web → ios → tv_embedded). If all fail:

1. Export cookies from Chrome: `chrome://settings/cookies` → site → export, or use the extension "EditThisCookie".
2. Place them at `~/cookies.txt` and tell the app to use them (Settings → Cookies).
3. Upload the video file locally instead.

## "YouTube did not respond in time"

The metadata fetch has a 60 s timeout with three player-client retries. If it still fails:

- Check your internet connection.
- Retry the same link — YouTube's first response is often the slowest.
- Upload the file locally.

## Download stalls at a percent

Every download runs in its own process group with a watchdog. If a stage makes no progress for 45 s the worker kills the process and tries the next fallback (other player client → lower quality → captions-only mode). If you see a card stuck for more than a minute, click **Retry lower quality** or **Delete** and re-submit.

## No captions / "No viral clips found"

Some videos have no caption track. If offline STT is not enabled the app falls back to audio-signal analysis and tells you captions are off. To enable:

1. `pip install maxclipper[stt]` (installs faster-whisper)
2. In Settings, turn on "Offline speech-to-text".
3. Re-run the job.

## "Render failed" / black or silent clips

- Confirm FFmpeg is installed: `maxclipper doctor`.
- On Windows, make sure the output folder is not on a network drive or a folder locked by antivirus.
- Try the "Fast preview" quality setting.

## Disk full

The app needs ~500 MB for itself plus ~100 MB per analyzed video. Run `maxclipper doctor` to see free space. Delete old clips from the Library tab.

## The app won't open / port in use

```bash
maxclipper --port 8080 --no-browser
```

If the port is busy, pick another with `--port`.
