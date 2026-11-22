P0-1 RESOLVED: process-group kill + bounded cleanup in _run_subprocess_async. Verified zero orphan processes. Playwright: progress flows 5->12->40->55% instead of stuck at 0%. All 11 tests pass.
P0-2 RESOLVED: polling shape fix in app.js + subprocess timeout fix. Verified cards appear and progress updates.
P0-3 RESOLVED: _active_workers PID tracking + no heuristic-age cutoff in _check_and_clear_orphan_tasks.
P0-4: Remove mock/synthetic transcript code paths unless clearly labeled last-resort fallback.
P0-5: Route-existence test added, .bak files removed, targeted edits enforced.
P0-6: _run_subprocess_async: process-group start_new_session + drain + SIGKILL on timeout.
P1-1: Verified transcript+selection completes under L6 budgets.
P1-2: All UI Create-screen settings flow to backend and change pipeline behavior.
P1-3: HEADERS: test bar at 360, 768, 1440 px dark/light.
P3-1: README already has answer-first install; SEO assets need generation.
P3-2: CI matrix pending fresh clone test.
P3-3: Install scripts already pass .
