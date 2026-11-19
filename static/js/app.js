/**
 * GTA 6 Clipper App
 * UI interactivity and backend communication for the Create screen
 * and the "Your videos" list.
 */

(function () {
  'use strict';

  // ══════ CONFIG ═════
  const API = {
    process: '/api/process',
    upload: '/api/upload',
    tasks: '/api/tasks',
    cancel: '/api/tasks/cancel',
    validate: '/api/validate',
    deleteVideo: '/api/videos',
  };

  const VIDEO_EXTENSIONS = ['mp4', 'mov', 'mkv', 'webm'];
  const MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024; // 2 GB

  const DEFAULT_SETTINGS = {
    clipCount: 5,
    clipLengthMin: 30,
    clipLengthMax: 45,
    aspect: '9:16',
    captionStyle: 'pop-bold',
    framing: 'auto',
    hookText: false,
    tightenPauses: true,
    focusText: '',
    rangeStart: null,
    rangeEnd: null,
  };

  // ══════ STATE ═════
  const state = {
    activeTab: 'create',
    settings: loadSettings(),
    pollTimer: null,
  };

  // ══════ DOM REFS ═════
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const els = {
    tabs: $$('.app-bar-tab'),
    tabPanels: $$('.tab-content'),
    videoUrl: $('#video-url'),
    pasteBtn: $('#paste-btn'),
    findClipsBtn: $('#find-clips-btn'),
    dropZone: $('#drop-zone'),
    fileInput: $('#file-input'),
    focusInput: $('#focus-input'),
    timeFrom: $('#time-from'),
    timeTo: $('#time-to'),
    framingSelect: $('#framing-select'),
    hookToggle: $('#hook-text-toggle'),
    tightenToggle: $('#tighten-pauses-toggle'),
    savePreset: $('#save-preset-link'),
    resetPreset: $('#reset-preset-link'),
    videoCards: $('#video-cards-container'),
    emptyState: $('#empty-state'),
    videoCount: $('#video-count'),
    videoSearch: $('#video-search'),
    toastContainer: $('#toast-container'),
    confirmDialog: $('#confirm-dialog'),
    dialogTitle: $('#dialog-title'),
    dialogMessage: $('#dialog-message'),
    dialogCancel: $('#dialog-cancel'),
    dialogConfirm: $('#dialog-confirm'),
    engineStatus: $('#engine-status'),
  };

  // ══════ SETTINGS PERSISTENCE ═════
  function loadSettings() {
    try {
      const raw = localStorage.getItem('gta6_clipper_settings');
      return raw ? { ...DEFAULT_SETTINGS, ...JSON.parse(raw) } : { ...DEFAULT_SETTINGS };
    } catch {
      return { ...DEFAULT_SETTINGS };
    }
  }

  function saveSettings() {
    localStorage.setItem('gta6_clipper_settings', JSON.stringify(state.settings));
  }

  // ══════ TIME PARSING ═════
  function parseTimeInput(str) {
    // Accepts mm:ss, m:ss, h:mm:ss
    const m = String(str).trim().match(/^(?:(\d+):)?(\d{1,2}):(\d{2})$/);
    if (!m) return null;
    const h = m[1] ? parseInt(m[1], 10) : 0;
    const min = parseInt(m[2], 10);
    const sec = parseInt(m[3], 10);
    if (min >= 60 || sec >= 60) return null;
    return h * 3600 + min * 60 + sec;
  }

  function formatTime(seconds) {
    if (!isFinite(seconds) || seconds < 0) return '0:00';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    return h > 0
      ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
      : `${m}:${String(s).padStart(2, '0')}`;
  }

  // ══════ TOASTS ═════
  function showToast(message, kind = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast ${kind}`;
    toast.setAttribute('role', 'status');
    toast.innerHTML = `<span class="toast-message"></span>
      <button class="toast-close" aria-label="Dismiss">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
      </button>`;
    toast.querySelector('.toast-message').textContent = message;
    els.toastContainer.appendChild(toast);
    const dismiss = () => {
      toast.style.transition = 'opacity 250ms ease';
      toast.style.opacity = '0';
      setTimeout(() => toast.remove(), 300);
    };
    toast.querySelector('.toast-close').addEventListener('click', dismiss);
    setTimeout(dismiss, 4500);
  }

  // ══════ CONFIRM DIALOG ═════
  function confirmDialog(title, message) {
    return new Promise((resolve) => {
      els.dialogTitle.textContent = title;
      els.dialogMessage.textContent = message;
      els.confirmDialog.classList.add('active');
      els.dialogCancel.focus();

      const cleanup = (val) => {
        els.confirmDialog.classList.remove('active');
        els.dialogCancel.removeEventListener('click', onCancel);
        els.dialogConfirm.removeEventListener('click', onConfirm);
        document.removeEventListener('keydown', onKey);
        resolve(val);
      };
      const onCancel = () => cleanup(false);
      const onConfirm = () => cleanup(true);
      const onKey = (e) => {
        if (e.key === 'Escape') cleanup(false);
        if (e.key === 'Enter') cleanup(true);
      };
      els.dialogCancel.addEventListener('click', onCancel);
      els.dialogConfirm.addEventListener('click', onConfirm);
      document.addEventListener('keydown', onKey);
    });
  }

  // ══════ TABS ═════
  function switchTab(tabId) {
    state.activeTab = tabId;
    els.tabs.forEach((t) => t.classList.toggle('active', t.dataset.tab === tabId));
    els.tabPanels.forEach((p) => p.classList.toggle('hidden', p.id !== `${tabId}-tab`));
    if (tabId === 'library') renderVideoList();
  }

  // ══════ BUTTON STATES ═════
  function setFindClipsButton(stateName, label) {
    const btn = els.findClipsBtn;
    btn.disabled = stateName !== 'idle';
    btn.querySelector('.button-text').textContent = label || 'Find my clips';
    const spinner = btn.querySelector('.spinner');
    if (spinner) {
      spinner.style.display = stateName === 'working' ? 'inline-block' : 'none';
    }
    if (stateName === 'error') {
      btn.querySelector('.button-text').textContent = label || 'Try again';
      btn.setAttribute('aria-busy', 'false');
    } else {
      btn.setAttribute('aria-busy', stateName === 'working' ? 'true' : 'false');
    }
  }

  // ══════ SOURCE VALIDATION ═════
  const YOUTUBE_RE = /^(https?:\/\/)?(www\.|m\.)?(youtube\.com\/(watch\?v=|shorts\/|embed\/)|youtu\.be\/)[\w-]{6,}/i;

  async function validateLink(url) {
    if (!YOUTUBE_RE.test(url.trim())) {
      return { ok: false, error: 'That does not look like a YouTube link.' };
    }
    try {
      const res = await fetch(`${API.validate}?url=${encodeURIComponent(url.trim())}`);
      if (res.ok) {
        const data = await res.json();
        if (data.success) {
          return { ok: true, title: data.title, duration: data.duration, thumbnail: data.thumbnail };
        }
        return { ok: false, error: data.error || 'Could not read that video.' };
      }
      // Endpoint not available yet — accept the URL and let the pipeline report
      return { ok: true, title: url, duration: 0, thumbnail: '' };
    } catch {
      return { ok: true, title: url, duration: 0, thumbnail: '' };
    }
  }

  function validateFile(file) {
    const ext = (file.name.split('.').pop() || '').toLowerCase();
    if (!VIDEO_EXTENSIONS.includes(ext)) {
      return { ok: false, error: `Unsupported file type .${ext}. Use MP4, MOV, MKV or WebM.` };
    }
    if (file.size > MAX_FILE_SIZE) {
      return { ok: false, error: 'File is larger than 2 GB.' };
    }
    return { ok: true, title: file.name, duration: 0, thumbnail: '' };
  }

  // ══════ PIPELINE SUBMIT ═════
  async function startJob() {
    // 1. Determine source
    const url = els.videoUrl.value.trim();
    let source = null;

    if (url) {
      const validation = await validateLink(url);
      if (!validation.ok) {
        showToast(validation.error, 'error');
        setFindClipsButton('error');
        return;
      }
      source = { type: 'url', url, title: validation.title, duration: validation.duration };
    } else if (els.fileInput.files.length > 0) {
      const file = els.fileInput.files[0];
      const validation = validateFile(file);
      if (!validation.ok) {
        showToast(validation.error, 'error');
        setFindClipsButton('error');
        return;
      }
      source = { type: 'file', title: file.name };
    } else {
      showToast('Paste a link or choose a video file first.', 'error');
      return;
    }

    // 2. Validate time range
    let rangeStart = null;
    let rangeEnd = null;
    const fromRaw = els.timeFrom.value.trim();
    const toRaw = els.timeTo.value.trim();
    if (fromRaw) {
      rangeStart = parseTimeInput(fromRaw);
      if (rangeStart === null) {
        showToast('Invalid "From" time. Use mm:ss or h:mm:ss.', 'error');
        els.timeFrom.focus();
        return;
      }
    }
    if (toRaw) {
      rangeEnd = parseTimeInput(toRaw);
      if (rangeEnd === null) {
        showToast('Invalid "To" time. Use mm:ss or h:mm:ss.', 'error');
        els.timeTo.focus();
        return;
      }
    }
    if (rangeStart !== null && rangeEnd !== null && rangeEnd <= rangeStart) {
      showToast('"To" must be later than "From".', 'error');
      return;
    }

    // 3. Build payload
    const s = state.settings;
    const clipCount = s.clipCount === 'auto' ? 0 : Number(s.clipCount);
    const payload = {
      url: source.type === 'url' ? source.url : null,
      filepath: source.type === 'file' ? source.value : null,
      clip_count: clipCount,
      length_min: s.clipLengthMin,
      length_max: s.clipLengthMax,
      aspect: s.aspect,
      caption_style: s.captionStyle,
      framing: s.framing,
      hook_text: s.hookText,
      tighten_pauses: s.tightenPauses,
      focus_text: s.focusText,
      range_start: rangeStart,
      range_end: rangeEnd,
    };

    setFindClipsButton('working');

    // 4. Submit
    try {
      let res;
      if (source.type === 'url') {
        res = await fetch(API.process, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
      } else {
        const fd = new FormData();
        fd.append('file', els.fileInput.files[0]);
        fd.append('settings', JSON.stringify(payload));
        res = await fetch(API.upload, { method: 'POST', body: fd });
      }

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || err.error || `Server responded ${res.status}`);
      }

      const data = await res.json();
      const taskId = data.task_id || data.id;
      if (!taskId) throw new Error('No task id returned');

      // 5. Track the job
      trackTask(taskId, source);
      switchTab('library');
    } catch (e) {
      setFindClipsButton('error');
      showToast(`Could not start: ${e.message}`, 'error');
    }
  }

  // ══════ TASK TRACKING (stepper, detail row, progressive clips) ═════
  const ACTIVE_STAGES = {
    ingesting: 0,
    downloading: 0,
    audio_download: 0,
    captions: 0,
    transcribing: 1,
    analyzing: 1,
    selecting: 1,
    rendering: 2,
    processing: 0,
  };

  function trackTask(taskId, source) {
    let card = els.videoCards.querySelector(`[data-task-id="${taskId}"]`);
    if (!card) {
      card = createVideoCard(taskId, source);
      els.videoCards.prepend(card);
      els.emptyState.classList.add('hidden');
    }
    startPolling(taskId);
  }

  function createVideoCard(taskId, source) {
    const card = document.createElement('article');
    card.className = 'video-card';
    card.dataset.taskId = taskId;

    card.innerHTML = `
      <div class="video-card-header">
        <div class="video-thumbnail" aria-hidden="true">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="23 7 16 12 23 17 23 7"></polygon><rect x="1" y="5" width="15" height="14" rx="2"></rect></svg>
        </div>
        <div class="video-info">
          <h3 class="video-title"></h3>
          <div class="video-meta">
            <span class="source-badge">${source.type === 'url' ? 'YouTube' : 'File'}</span>
            <span class="video-time"></span>
            <span class="status-pill working" data-role="status-pill">Working</span>
          </div>
        </div>
        <div class="video-actions">
          <button class="icon-button expand-btn" aria-label="Expand" aria-expanded="false">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
          </button>
          <button class="icon-button overflow-btn" aria-label="More actions">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="1"></circle><circle cx="12" cy="5" r="1"></circle><circle cx="12" cy="19" r="1"></circle></svg>
          </button>
        </div>
      </div>
      <div class="card-body hidden">
        <div class="progress-stepper" data-role="stepper" aria-hidden="true">
          <div class="progress-step-item" data-step="0">
            <div class="step-indicator"><div class="step-fill"></div></div>
            <span class="step-label">Get the video</span>
          </div>
          <div class="progress-step-item" data-step="1">
            <div class="step-indicator"><div class="step-fill"></div></div>
            <span class="step-label">Pick the best moments</span>
          </div>
          <div class="progress-step-item" data-step="2">
            <div class="step-indicator"><div class="step-fill"></div></div>
            <span class="step-label">Cut, frame and caption</span>
          </div>
        </div>
        <div class="progress-detail" data-role="progress-detail">
          <span class="progress-stage-text" data-role="stage-text">Starting…</span>
          <div class="progress-stats">
            <span data-role="percent">0%</span>
            <span data-role="eta"></span>
            <button class="cancel-button" data-role="cancel">Cancel</button>
          </div>
        </div>
        <div class="progress-detail hidden" data-role="stuck-banner">
          <span class="progress-stage-text" data-role="stuck-text">Stuck? Retry with lower quality</span>
          <button class="retry-button" data-role="retry">Retry lower quality</button>
          <button class="retry-button" data-role="resume">Resume</button>
          <button class="retry-button" data-role="delete">Delete</button>
        </div>
        <div class="progress-detail hidden" data-role="error-banner">
          <span class="progress-stage-text" data-role="error-text"></span>
          <button class="retry-button" data-role="fix">Fix it</button>
        </div>
        <div data-role="clips-wrap">
          <div class="clip-grid" data-role="clip-grid"></div>
          <button class="download-all-button hidden" data-role="download-all">
            Download all (zip)
          </button>
        </div>
      </div>
    `;

    card.querySelector('.video-title').textContent = source.title || 'Video';
    card.querySelector('.video-time').textContent = 'just now';

    // Wire up buttons
    const expandBtn = card.querySelector('.expand-btn');
    const body = card.querySelector('.card-body');
    expandBtn.addEventListener('click', () => {
      const open = body.classList.toggle('hidden');
      expandBtn.setAttribute('aria-expanded', String(!open));
    });

    card.querySelector('[data-role="cancel"]').addEventListener('click', async () => {
      try {
        await fetch(`${API.cancel}/${taskId}`, { method: 'POST' });
        setCardStatus(card, 'cancelled');
      } catch {
        showToast('Could not cancel the job.', 'error');
      }
    });

    card.querySelector('[data-role="retry"]').addEventListener('click', () => {
      fetch(`${API.cancel}/${taskId}`, { method: 'POST' }).catch(() => {});
      startJobWithQuality('lower');
    });

    card.querySelector('[data-role="resume"]').addEventListener('click', () => {
      // Resume an interrupted job: re-submit the same URL with the same settings
      const cardTitle = card.querySelector('.video-title')?.textContent || '';
      const url = cardTitle.startsWith('http') ? cardTitle : (card.dataset.url || '');
      if (url) {
        // Re-submit via the same form values, lower quality
        const focus = els.focusInput?.value || '';
        startJobWithQuality('lower', url, focus);
      }
    });

    card.querySelector('[data-role="delete"]').addEventListener('click', () => {
      fetch(`${API.cancel}/${taskId}`, { method: 'POST' });
      card.remove();
    });

    card.querySelector('[data-role="fix"]').addEventListener('click', () => {
      // Offer the fix options as a toast menu — simplest honest behavior:
      // retry, or open the card so the user can re-run with new settings.
      body.classList.remove('hidden');
      expandBtn.setAttribute('aria-expanded', 'true');
    });

    card.querySelector('.overflow-btn').addEventListener('click', () => showOverflowMenu(card, taskId));

    // Auto-open body when job starts
    body.classList.remove('hidden');
    expandBtn.setAttribute('aria-expanded', 'true');

    return card;
  }

  function showOverflowMenu(card, taskId) {
    // Remove any existing menu
    const existing = document.querySelector('.overflow-menu');
    if (existing) existing.remove();

    const menu = document.createElement('div');
    menu.className = 'overflow-menu';
    menu.style.cssText =
      'position:absolute;z-index:500;background:var(--bg-elevated);border:1px solid var(--border);border-radius:var(--radius-md);box-shadow:var(--shadow-lg);overflow:hidden;min-width:180px;';
    menu.innerHTML = `
      <button data-act="open-folder" style="display:block;width:100%;padding:10px 14px;background:none;border:none;color:var(--text-primary);font-size:0.8125rem;cursor:pointer;text-align:left;font-family:inherit;">Open folder</button>
      <button data-act="rerun" style="display:block;width:100%;padding:10px 14px;background:none;border:none;color:var(--text-primary);font-size:0.8125rem;cursor:pointer;text-align:left;font-family:inherit;">Re-run with new settings</button>
      <button data-act="delete" style="display:block;width:100%;padding:10px 14px;background:none;border:none;color:var(--error);font-size:0.8125rem;cursor:pointer;text-align:left;font-family:inherit;">Delete</button>
    `;
    const rect = card.querySelector('.overflow-btn').getBoundingClientRect();
    menu.style.position = 'fixed';
    menu.style.top = `${rect.bottom + 4}px`;
    menu.style.left = `${Math.max(8, rect.right - 180)}px`;
    document.body.appendChild(menu);

    const close = () => {
      menu.remove();
      document.removeEventListener('click', close, true);
    };
    setTimeout(() => document.addEventListener('click', close, true), 0);

    menu.querySelector('[data-act="open-folder"]').addEventListener('click', async (e) => {
      e.stopPropagation();
      close();
      try {
        const res = await fetch(`/api/videos/folder?task_id=${taskId}`);
        const data = await res.json();
        if (data.path) window.open(`file://${data.path}`);
        else showToast('No folder yet for this job.', 'warning');
      } catch {
        showToast('Could not open folder.', 'error');
      }
    });

    menu.querySelector('[data-act="rerun"]').addEventListener('click', (e) => {
      e.stopPropagation();
      close();
      switchTab('create');
    });

    menu.querySelector('[data-act="delete"]').addEventListener('click', async (e) => {
      e.stopPropagation();
      close();
      const ok = await confirmDialog('Delete this video?', 'This removes the job and its clips.');
      if (!ok) return;
      try {
        await fetch(`${API.deleteVideo}/${taskId}`, { method: 'DELETE' });
        card.remove();
        updateVideoCount();
        if (els.videoCards.children.length === 0) els.emptyState.classList.remove('hidden');
        showToast('Deleted.', 'success');
      } catch {
        showToast('Could not delete.', 'error');
      }
    });
  }

  function setCardStatus(card, status) {
    const pill = card.querySelector('[data-role="status-pill"]');
    pill.className = `status-pill ${status}`;
    pill.textContent = status.charAt(0).toUpperCase() + status.slice(1);
  }

  function updateVideoCount() {
    const videos = els.videoCards.querySelectorAll('.video-card').length;
    const clips = els.videoCards.querySelectorAll('[data-role="clip-grid"] .clip-card').length;
    els.videoCount.textContent = `${videos} video${videos === 1 ? '' : 's'}, ${clips} clip${clips === 1 ? '' : 's'}`;
    els.videoSearch.style.display = videos > 5 ? '' : 'none';
  }

  // ══════ POLLING ═════
  function startPolling(taskId) {
    if (state.pollTimer) clearInterval(state.pollTimer);
    let lastProgressAt = Date.now();
    let lastProgressValue = -1;

    const tick = async () => {
      let data;
      try {
        const res = await fetch(API.tasks);
        data = await res.json();
      } catch {
        return; // server unreachable — keep polling
      }
      // /api/tasks returns {tasks: [ {task_id, status, ...} ]}.
      // Find this job's entry by task_id (works for list or dict shape).
      const taskList = Array.isArray(data.tasks)
        ? data.tasks
        : Object.values(data.tasks || data || {});
      const task = taskList.find((t) => (t.task_id || t.id) === taskId);
      if (!task) return;

      const card = els.videoCards.querySelector(`[data-task-id="${taskId}"]`);
      if (!card) return;

      const status = task.status || task.state;
      const progress = typeof task.progress === 'number' ? task.progress : 0;
      const message = task.message || '';

      // Stepper
      const stage = task.stage || 'processing';
      const stepIdx = ACTIVE_STAGES[stage] !== undefined ? ACTIVE_STAGES[stage] : 0;
      const steps = card.querySelectorAll('[data-role="stepper"] .progress-step-item');
      steps.forEach((el, i) => {
        const fill = el.querySelector('.step-fill');
        if (i < stepIdx) fill.style.width = '100%';
        else if (i === stepIdx) fill.style.width = `${progress}%`;
        else fill.style.width = '0%';
      });

      // Detail row
      card.querySelector('[data-role="stage-text"]').textContent = message || stage;
      card.querySelector('[data-role="percent"]').textContent = `${Math.round(progress)}%`;

      // Stuck detection: no progress change for 60 s while working
      if (status === 'working' || status === 'processing') {
        setCardStatus(card, 'working');
        if (progress !== lastProgressValue) {
          lastProgressValue = progress;
          lastProgressAt = Date.now();
        }
        const stuck = Date.now() - lastProgressAt > 60000 && progress < 100;
        card.querySelector('[data-role="stuck-banner"]').classList.toggle('hidden', !stuck);
      } else {
        lastProgressValue = -1;
        card.querySelector('[data-role="stuck-banner"]').classList.add('hidden');
      }

      if (status === 'completed' || status === 'done') {
        setCardStatus(card, 'ready');
        card.querySelectorAll('.progress-step-item .step-fill').forEach((f) => (f.style.width = '100%'));
        card.querySelector('[data-role="stage-text"]').textContent = 'Done';
        card.querySelector('[data-role="progress-detail"]').classList.add('hidden');
        renderClips(card, task.clips || []);
        notifyCompletion(task, card);
        state.pollTimer && clearInterval(state.pollTimer);
      } else if (status === 'failed' || status === 'error') {
        setCardStatus(card, 'failed');
        card.querySelector('[data-role="progress-detail"]').classList.add('hidden');
        const errBanner = card.querySelector('[data-role="error-banner"]');
        errBanner.classList.remove('hidden');
        card.querySelector('[data-role="error-text"]').textContent = task.error || 'Something went wrong.';
        state.pollTimer && clearInterval(state.pollTimer);
      } else if (status === 'cancelled') {
        setCardStatus(card, 'cancelled');
        card.querySelector('[data-role="progress-detail"]').classList.add('hidden');
        state.pollTimer && clearInterval(state.pollTimer);
      } else if (status === 'interrupted') {
        setCardStatus(card, 'interrupted');
        card.querySelector('[data-role="progress-detail"]').classList.add('hidden');
        const stuckBanner = card.querySelector('[data-role="stuck-banner"]');
        stuckBanner.classList.remove('hidden');
        stuckBanner.querySelector('[data-role="stuck-text"]')
          || stuckBanner.querySelector('.progress-stage-text');
        state.pollTimer && clearInterval(state.pollTimer);
      }

      updateVideoCount();
    };

    state.pollTimer = setInterval(tick, 2000);
    tick();
  }

  function renderClips(card, clips) {
    const grid = card.querySelector('[data-role="clip-grid"]');
    clips.forEach((clip) => {
      if (grid.querySelector(`[data-clip-id="${clip.clip_id || clip.id}"]`)) return;
      const el = document.createElement('div');
      el.className = 'clip-card';
      el.dataset.clipId = clip.clip_id || clip.id || '';

      const videoUrl = clip.download_url || (clip.filepath ? `/${clip.filepath}` : '');
      el.innerHTML = `
        <div class="clip-preview">
          ${videoUrl ? `<video src="${videoUrl}" preload="metadata" muted playsinline></video>` : ''}
          <span class="clip-score-ring">${clip.score || 0}</span>
          <span class="clip-duration">${formatTime(clip.duration || 0)}</span>
        </div>
        <div class="clip-info">
          <p class="clip-headline">${escapeHtml(clip.headline || clip.title || 'Clip')}</p>
          <div class="clip-reasons">
            ${Array.isArray(clip.reasons)
              ? clip.reasons.slice(0, 4).map((r) => `<span class="reason-chip">${escapeHtml(r)}</span>`).join('')
              : clip.reason
                ? `<span class="reason-chip">${escapeHtml(clip.reason)}</span>`
                : ''}
          </div>
          <div class="clip-actions-row">
            <button class="clip-action-button" data-act="download">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
              Download
            </button>
            <button class="clip-action-button" data-act="copy">Copy title</button>
          </div>
        </div>
      `;

      // Hover-play
      const video = el.querySelector('video');
      if (video) {
        el.addEventListener('mouseenter', () => video.play().catch(() => {}));
        el.addEventListener('mouseleave', () => video.pause());
      }

      el.querySelector('[data-act="download"]').addEventListener('click', () => {
        if (clip.download_url) {
          const a = document.createElement('a');
          a.href = clip.download_url;
          a.download = clip.filename || 'clip.mp4';
          a.click();
        } else if (videoUrl) {
          window.open(videoUrl, '_blank');
        }
      });

      el.querySelector('[data-act="copy"]').addEventListener('click', async () => {
        const text = `${clip.headline || clip.title || ''} #shorts #viral`;
        try {
          await navigator.clipboard.writeText(text);
          showToast('Title and hashtags copied.');
        } catch {
          showToast('Could not copy to clipboard.', 'error');
        }
      });

      grid.appendChild(el);
      const dlAll = card.querySelector('[data-role="download-all"]');
      if (grid.children.length >= 2) dlAll.classList.remove('hidden');
    });
    updateVideoCount();
  }

  function notifyCompletion(task, card) {
    showToast('Your clips are ready.', 'success');
    if ('Notification' in window && Notification.permission === 'granted') {
      new Notification('GTA 6 Clipper', { body: `${task.message || 'Clips ready'}` });
    }
    document.title = 'GTA 6 Clipper — Clips ready';
  }

  function startJobWithQuality(quality, urlOverride, focusOverride) {
    showToast('Re-running with lower quality settings…');
    localStorage.setItem('gta6_clipper_quality_override', quality);
    if (urlOverride) els.videoUrl.value = urlOverride;
    if (focusOverride !== undefined) els.focusInput.value = focusOverride;
    startJob();
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  // ══════ RENDER VIDEO LIST FROM API (persist across restarts) ═════
  async function renderVideoList() {
    try {
      const res = await fetch(API.tasks);
      const data = await res.json();
      const tasks = data.tasks || (Array.isArray(data) ? data : Object.values(data || {}));
      if (!tasks || tasks.length === 0) return;

      // Render persisted jobs not yet on the page
      for (const task of tasks) {
        const taskId = task.task_id || task.id;
        if (!taskId) continue;
        if (els.videoCards.querySelector(`[data-task-id="${taskId}"]`)) continue;
        const source = {
          type: task.source_type === 'file' ? 'file' : 'url',
          title: task.title || task.url || 'Video',
        };
        const card = createVideoCard(taskId, source);
        els.videoCards.prepend(card);
        els.emptyState.classList.add('hidden');
        // Rehydrate completed state
        const status = task.status || task.state;
        if (status === 'completed' || status === 'done') {
          setCardStatus(card, 'ready');
          card.querySelector('[data-role="progress-detail"]').classList.add('hidden');
          renderClips(card, task.clips || []);
        } else if (status === 'working' || status === 'processing') {
          trackTask(taskId, source);
        }
      }
      updateVideoCount();
    } catch {
      // API not up — leave empty state
    }
  }

  // ══════ SETTINGS CONTROLS ═════
  function initSettings() {
    const s = state.settings;

    // Clip count segmented control
    $$('#clip-count-control .segmented-btn').forEach((btn) => {
      btn.classList.toggle('active', String(s.clipCount) === btn.dataset.value);
      btn.addEventListener('click', () => {
        $$('#clip-count-control .segmented-btn').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        s.clipCount = btn.dataset.value === 'auto' ? 'auto' : Number(btn.dataset.value);
        saveSettings();
      });
    });

    // Clip length segmented control
    $$('#clip-length-control .segmented-btn').forEach((btn) => {
      const min = Number(btn.dataset.min);
      const max = Number(btn.dataset.max);
      btn.classList.toggle('active', s.clipLengthMin === min && s.clipLengthMax === max);
      btn.addEventListener('click', () => {
        $$('#clip-length-control .segmented-btn').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        s.clipLengthMin = min;
        s.clipLengthMax = max;
        saveSettings();
      });
    });

    // Aspect ratio
    $$('.aspect-ratio-card').forEach((card) => {
      card.classList.toggle('selected', s.aspect === card.dataset.value);
      card.setAttribute('role', 'radio');
      card.setAttribute('tabindex', '0');
      card.setAttribute('aria-checked', String(s.aspect === card.dataset.value));
      const pick = () => {
        $$('.aspect-ratio-card').forEach((c) => {
          c.classList.remove('selected');
          c.setAttribute('aria-checked', 'false');
        });
        card.classList.add('selected');
        card.setAttribute('aria-checked', 'true');
        s.aspect = card.dataset.value;
        saveSettings();
      };
      card.addEventListener('click', pick);
      card.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          pick();
        }
      });
    });

    // Caption style
    $$('.caption-style-tile').forEach((tile) => {
      tile.classList.toggle('selected', s.captionStyle === tile.dataset.style);
      tile.setAttribute('role', 'radio');
      tile.setAttribute('tabindex', '0');
      const pick = () => {
        $$('.caption-style-tile').forEach((t) => t.classList.remove('selected'));
        tile.classList.add('selected');
        s.captionStyle = tile.dataset.style;
        saveSettings();
      };
      tile.addEventListener('click', pick);
      tile.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          pick();
        }
      });
    });

    // Framing
    els.framingSelect.value = s.framing;
    els.framingSelect.addEventListener('change', () => {
      s.framing = els.framingSelect.value;
      saveSettings();
    });

    // Toggles
    els.hookToggle.classList.toggle('active', s.hookText);
    els.hookToggle.setAttribute('role', 'switch');
    els.hookToggle.setAttribute('tabindex', '0');
    els.hookToggle.setAttribute('aria-checked', String(s.hookText));
    const toggleHook = () => {
      s.hookText = !s.hookText;
      els.hookToggle.classList.toggle('active', s.hookText);
      els.hookToggle.setAttribute('aria-checked', String(s.hookText));
      saveSettings();
    };
    els.hookToggle.addEventListener('click', toggleHook);
    els.hookToggle.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        toggleHook();
      }
    });

    els.tightenToggle.classList.toggle('active', s.tightenPauses);
    els.tightenToggle.setAttribute('role', 'switch');
    els.tightenToggle.setAttribute('tabindex', '0');
    els.tightenToggle.setAttribute('aria-checked', String(s.tightenPauses));
    const toggleTighten = () => {
      s.tightenPauses = !s.tightenPauses;
      els.tightenToggle.classList.toggle('active', s.tightenPauses);
      els.tightenToggle.setAttribute('aria-checked', String(s.tightenPauses));
      saveSettings();
    };
    els.tightenToggle.addEventListener('click', toggleTighten);
    els.tightenToggle.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        toggleTighten();
      }
    });

    // Focus text + time inputs
    els.focusInput.value = s.focusText || '';
    els.focusInput.addEventListener('input', () => {
      s.focusText = els.focusInput.value.trim();
      saveSettings();
    });

    // Preset links
    els.savePreset.addEventListener('click', (e) => {
      e.preventDefault();
      saveSettings();
      showToast('Preset saved.');
    });
    els.resetPreset.addEventListener('click', async (e) => {
      e.preventDefault();
      const ok = await confirmDialog('Reset settings?', 'All clip settings go back to defaults.');
      if (!ok) return;
      state.settings = { ...DEFAULT_SETTINGS };
      saveSettings();
      location.reload();
    });

    // Search filter
    els.videoSearch.addEventListener('input', () => {
      const q = els.videoSearch.value.toLowerCase();
      els.videoCards.querySelectorAll('.video-card').forEach((card) => {
        const title = (card.querySelector('.video-title')?.textContent || '').toLowerCase();
        card.style.display = title.includes(q) ? '' : 'none';
      });
    });
  }

  // ══════ DRAG & DROP ═════
  function initDropZone() {
    let dragDepth = 0;
    els.dropZone.addEventListener('dragenter', (e) => {
      e.preventDefault();
      dragDepth++;
      els.dropZone.classList.add('dragover');
    });
    els.dropZone.addEventListener('dragleave', (e) => {
      e.preventDefault();
      dragDepth--;
      if (dragDepth <= 0) {
        dragDepth = 0;
        els.dropZone.classList.remove('dragover');
      }
    });
    els.dropZone.addEventListener('dragover', (e) => e.preventDefault());
    els.dropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      dragDepth = 0;
      els.dropZone.classList.remove('dragover');
      const files = e.dataTransfer.files;
      if (files && files.length > 0) {
        els.fileInput.files = files;
        const validation = validateFile(files[0]);
        if (validation.ok) {
          els.videoUrl.value = '';
          showToast(`Loaded ${files[0].name}`);
        } else {
          showToast(validation.error, 'error');
        }
      }
    });
    els.dropZone.addEventListener('click', () => els.fileInput.click());
    els.fileInput.addEventListener('change', () => {
      if (els.fileInput.files.length > 0) {
        els.videoUrl.value = '';
        showToast(`Loaded ${els.fileInput.files[0].name}`);
      }
    });
  }

  // ══════ INIT ═════
  function init() {
    initSettings();
    initDropZone();
    setFindClipsButton('idle');
    updateVideoCount();
    renderVideoList();

    els.findClipsBtn.addEventListener('click', startJob);
    els.videoUrl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') startJob();
    });

    // Wire tab clicks
    els.tabs.forEach((tab) => {
      tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });
    els.pasteBtn.addEventListener('click', async () => {
      try {
        const text = await navigator.clipboard.readText();
        els.videoUrl.value = text;
        showToast('Link pasted. Press Find my clips.');
      } catch {
        els.videoUrl.focus();
        els.videoUrl.select();
      }
    });

    // Update tab title with progress
    setInterval(() => {
      const working = els.videoCards.querySelector('.status-pill.working');
      if (working) {
        const card = working.closest('.video-card');
        const pct = card?.querySelector('[data-role="percent"]')?.textContent || '…';
        document.title = `Clipping ${pct} — GTA 6 Clipper`;
      } else if (!document.title.includes('ready')) {
        document.title = 'GTA 6 Clipper — Turn Long Videos into Ready Shorts';
      }
    }, 3000);
  }

  document.addEventListener('DOMContentLoaded', init);
})();
