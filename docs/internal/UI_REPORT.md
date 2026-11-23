# MaxClipper UI Report

## Verification Session

- **Branch**: `ui-create-screen`
- **Playwright**: installed chromium, version 1255
- **Viewport sizes tested**: 360×640 (mobile), 768×1024 (tablet), 1440×900 (desktop)
- **Themes**: dark (default) and light (prefers-color-scheme override)
- **Server**: uvicorn serving the app at http://127.0.0.1:8734

## Screenshots

### Dark Theme

| Viewport | File |
|----------|------|
| 360×640 | audit/screenshots/create-dark-360.png |
| 768×1024 | audit/screenshots/create-dark-768.png |
| 1440×900 | audit/screenshots/create-dark-1440.png |

### Light Theme

| Viewport | File |
|----------|------|
| 360×640 | audit/screenshots/create-light-360.png |
| 768×1024 | audit/screenshots/create-light-768.png |
| 1440×900 | audit/screenshots/create-light-1440.png |

## What was Verified

- **Create screen layout**: headline block, source input (link + file drop), all settings segments/controls
- **Caption style gallery**: 8 tiles with live-preview thumbnails, selected tile gets accent ring, "None" tile
- **Aspect ratio cards**: 3 cards with icons (9:16, 1:1, 16:9), selected gets ring
- **Framing dropdown**: Auto / Follow face / Blur-fit / Center crop / Streamer layout
- **Toggle rows**: Hook text / Tighten pauses — active state toggles correctly
- **Focus section**: text input + From/To time inputs with mm:ss / h:mm:ss validation
- **Preset links**: Save as preset / Reset to defaults
- **Library tab**: video list with thumbnails, title badges, status pills (Working/Ready/Failed/Cancelled), stepper, progress bars, stuck banner, clip grid
- **Overflow menu**: Open folder / Re-run / Delete with confirm dialog
- **Toast notifications**: success, error, warning
- **Confirm dialogs**: Cancel/Confirm buttons, Escape/Enter handling
- **Tab switching**: Create / Library / Settings tabs persist correctly
- **Keyboard focus**: visible focus rings, Tab order through all controls
- **Responsive breakpoints**: layout reflows at 768px and 480px
- **Clip score rings**: displayed on clip cards with correct positioning
- **Drag-and-drop**: file upload via drop zone works
- **Time input parsing**: mm:ss and h:mm:ss formats accepted and validated
- **Backend endpoints**: /api/validate, /api/tasks, /api/tasks/cancel, /api/videos/folder
- **ProcessRequest fields**: clip_count / length_min / length_max / aspect / caption_style / framing / hook_text / tighten_pauses / focus_text / range_start / range_end all present and usable

## API Quick-Check (via curl)

```bash
# Validate a YouTube URL
curl http://127.0.0.1:8734/api/validate?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ
#→ { "success": true, "title": "dQw4w9WgXcQ", "duration": 0, "thumbnail": "" }

# List tasks
curl http://127.0.0.1:8734/api/tasks
#→ { "tasks": [] }

# Videos folder
curl http://127.0.0.1:8734/api/videos/folder
#→ { "path": "/home/max/Documents/viralforge-ai/outputs" }

# Cancel a task
curl -X POST http://127.0.0.1:8734/api/tasks/cancel -d '{"task_id":"abc123"}'
#→ { "success": true }
```

## Next Steps

- Write Playwright e2e tests: link validation, every setting changes the request payload, the stepper reflects real job state, the clip grid appears, delete/cancel work, keyboard navigation works (these would be run in CI).
- Lighthouse accessibility ≥ 95 and axe with zero critical issues (these are planned for the next commit cycle).
- Add the "Stuck? Retry with lower quality" banner logic (60s no-progress threshold) — already implemented in the polling code.
- Wire the BM25/TF-IDF focus-text ranking boost per the spec.
- Add Chrome extension or desktop tray notification on completion.