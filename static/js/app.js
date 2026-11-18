/* ═══════════════════════════════════════════════════════════
   ClipForge — Local-First YouTube to Shorts Clipper
   Complete Application Logic & UX Controller
   ═══════════════════════════════════════════════════════════ */

// ═══════ STATE ═══════
let currentFile = null;
let currentTaskId = null;
let pollInterval = null;
let activeClips = [];
let editingClip = null;

// ═══════ PARTICLES SYSTEM ═══════
(function initParticles() {
  const canvas = document.getElementById('particles-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let particles = [];
  const PARTICLE_COUNT = 60;

  function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  }

  function createParticle() {
    return {
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      vx: (Math.random() - 0.5) * 0.3,
      vy: (Math.random() - 0.5) * 0.3,
      size: Math.random() * 2.5 + 0.5,
      opacity: Math.random() * 0.4 + 0.1,
      color: Math.random() > 0.5
        ? `rgba(244, 143, 177, ${Math.random() * 0.3 + 0.1})`
        : `rgba(96, 165, 250, ${Math.random() * 0.25 + 0.08})`,
      pulse: Math.random() * Math.PI * 2,
      pulseSpeed: Math.random() * 0.02 + 0.005,
    };
  }

  function init() {
    resize();
    particles = Array.from({ length: PARTICLE_COUNT }, createParticle);
  }

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    particles.forEach((p) => {
      p.x += p.vx;
      p.y += p.vy;
      p.pulse += p.pulseSpeed;

      if (p.x < 0) p.x = canvas.width;
      if (p.x > canvas.width) p.x = 0;
      if (p.y < 0) p.y = canvas.height;
      if (p.y > canvas.height) p.y = 0;

      const pulsedOpacity = p.opacity * (0.7 + Math.sin(p.pulse) * 0.3);

      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      ctx.fillStyle = p.color.replace(/[\d.]+\)$/, `${pulsedOpacity})`);
      ctx.fill();
    });

    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 150) {
          const alpha = (1 - dist / 150) * 0.06;
          ctx.beginPath();
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.strokeStyle = `rgba(244, 143, 177, ${alpha})`;
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }
      }
    }

    requestAnimationFrame(draw);
  }

  window.addEventListener('resize', resize);
  init();
  draw();
})();

// ═══════ SCROLL EFFECTS ═══════
(function initScrollEffects() {
  const navbar = document.getElementById('navbar');
  window.addEventListener('scroll', () => {
    if (window.scrollY > 50) {
      navbar.classList.add('nav-scrolled');
    } else {
      navbar.classList.remove('nav-scrolled');
    }
  });

  const revealElements = document.querySelectorAll('.reveal');
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.15 });

  revealElements.forEach((el) => observer.observe(el));
})();

// ═══════ COUNTER ANIMATION ═══════
(function initCounters() {
  const counters = document.querySelectorAll('[data-count]');
  counters.forEach((el) => {
    const target = parseInt(el.dataset.count, 10);
    const duration = 2000;
    const startTime = Date.now();

    function update() {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = Math.round(target * eased);
      el.textContent = current.toLocaleString();

      if (progress < 1) {
        requestAnimationFrame(update);
      }
    }

    const observer = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting) {
        update();
        observer.disconnect();
      }
    });
    observer.observe(el);
  });
})();

// ═══════ NAVIGATION HELPERS ═══════
function scrollToStudio() {
  const section = document.getElementById('input-section');
  if (!section) return;

  // Account for the fixed navbar so the section is not hidden behind it
  const navbar = document.getElementById('navbar');
  const navH = navbar ? navbar.offsetHeight : 80;
  const targetY = section.getBoundingClientRect().top + window.scrollY - navH - 16;

  window.scrollTo({ top: Math.max(0, targetY), behavior: 'smooth' });

  // Expand advanced settings and focus the URL field so the user can paste immediately
  setTimeout(() => {
    const panel = document.getElementById('settings-panel');
    if (panel && !panel.classList.contains('open')) toggleSettings();
    const input = document.getElementById('video-url');
    if (input) {
      input.focus();
      input.select();
    }
  }, 450);
}

function logToConsole(msg, type = 'info') {
  const logContainer = document.getElementById('agent-console-log');
  if (!logContainer) return;
  const timeStr = new Date().toLocaleTimeString();
  const line = document.createElement('div');
  line.style.margin = '3px 0';

  if (type === 'error') {
    line.style.color = '#fc8181';
    line.textContent = `[${timeStr}] ❌ ERROR: ${msg}`;
  } else if (type === 'success') {
    line.style.color = '#68d391';
    line.textContent = `[${timeStr}] ✅ SUCCESS: ${msg}`;
  } else {
    line.style.color = '#cbd5e0';
    line.textContent = `[${timeStr}] ⚡ ${msg}`;
  }

  logContainer.appendChild(line);
  logContainer.scrollTop = logContainer.scrollHeight;
}

// Load library automatically when page loads
window.addEventListener('DOMContentLoaded', () => {
  loadExistingClipsLibrary();
});

async function loadExistingClipsLibrary() {
  try {
    const res = await fetch('/api/clips');
    const data = await res.json();
    if (data.clips && data.clips.length > 0) {
      showClipsView(data.clips);
      const clipsSec = document.getElementById('clips-section');
      if (clipsSec && window.scrollY > 300) {
        clipsSec.scrollIntoView({ behavior: 'smooth' });
      }
    }
  } catch (e) {
    console.log('Failed to fetch initial library clips:', e);
  }
}

// ═══════ TAB SWITCHING ═══════
function switchTab(tab) {
  const ytTab = document.getElementById('tab-yt');
  const uploadTab = document.getElementById('tab-upload');
  const ytBtn = document.getElementById('tab-yt-btn');
  const uploadBtn = document.getElementById('tab-upload-btn');

  if (tab === 'yt') {
    ytTab.classList.remove('hidden');
    uploadTab.classList.add('hidden');
    ytBtn.classList.add('active');
    uploadBtn.classList.remove('active');
  } else {
    ytTab.classList.add('hidden');
    uploadTab.classList.remove('hidden');
    uploadBtn.classList.add('active');
    ytBtn.classList.remove('active');
  }
}

// ═══════ CLIPBOARD PASTE ═══════
async function pasteFromClipboard() {
  try {
    const text = await navigator.clipboard.readText();
    document.getElementById('video-url').value = text;
  } catch (err) {
    console.error('Clipboard error:', err);
  }
}

// ═══════ SETTINGS TOGGLE ═══════
function toggleSettings() {
  const panel = document.getElementById('settings-panel');
  const chevron = document.getElementById('settings-chevron');
  const isOpen = panel.classList.contains('open');

  if (isOpen) {
    panel.classList.remove('open');
    chevron.style.transform = 'rotate(0deg)';
  } else {
    panel.classList.add('open');
    chevron.style.transform = 'rotate(180deg)';
  }
}

// ═══════ FILE UPLOAD / DROP ═══════
(function initDropZone() {
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');
  if (!dropZone || !fileInput) return;

  dropZone.addEventListener('click', () => fileInput.click());

  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
  });

  dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('dragover');
  });

  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    if (e.dataTransfer.files.length) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length) {
      handleFileSelected(e.target.files[0]);
    }
  });
})();

function handleFileSelected(file) {
  currentFile = file;
  const label = document.getElementById('file-label');
  label.innerHTML = `✅ Selected: <strong>${file.name}</strong> (${(file.size / (1024 * 1024)).toFixed(1)} MB)`;
}

// ═══════ AGENT SWARM VISUALIZATION ═══════
function initAgentGrid() {
  const grid = document.getElementById('agent-grid');
  if (!grid) return;
  grid.innerHTML = '';
  for (let i = 0; i < 100; i++) {
    const dot = document.createElement('div');
    dot.className = 'agent-dot';
    dot.title = `Agent Group ${i + 1} (100 agents)`;
    grid.appendChild(dot);
  }
}

function animateAgentSwarm(progress) {
  const dots = document.querySelectorAll('.agent-dot');
  const totalToActivate = Math.floor((progress / 100) * dots.length);

  dots.forEach((dot, index) => {
    if (index < totalToActivate) {
      dot.classList.remove('analyzing');
      dot.classList.add('complete');
    } else if (index < totalToActivate + 5) {
      dot.classList.add('analyzing');
      dot.classList.remove('complete');
    } else {
      dot.classList.remove('analyzing', 'complete');
    }
  });

  const agentsActive = Math.min(10000, Math.floor((progress / 100) * 10000));
  const viewsCompleted = Math.min(100000, agentsActive * 10);
  const clipsFound = progress > 60 ? Math.max(1, Math.floor((progress - 60) / 10)) : 0;

  const activeEl = document.getElementById('agents-active');
  const viewsEl = document.getElementById('views-completed');
  const clipsEl = document.getElementById('clips-found');

  if (activeEl) activeEl.textContent = agentsActive.toLocaleString();
  if (viewsEl) viewsEl.textContent = viewsCompleted.toLocaleString();
  if (clipsEl) clipsEl.textContent = clipsFound;

  const statusEl = document.getElementById('swarm-status');
  if (statusEl) {
    if (progress < 20) {
      statusEl.textContent = 'Downloading video stream and parsing audio track...';
    } else if (progress < 40) {
      statusEl.textContent = 'Transcribing speech with AI word-level timestamps...';
    } else if (progress < 65) {
      statusEl.textContent = 'real minutes analyzed agents scoring hooks, speech velocity and emotional keywords...';
    } else if (progress < 85) {
      statusEl.textContent = 'Generating vertical 9:16 layout and kinetic ASS subtitles...';
    } else {
      statusEl.textContent = 'Finalizing 60fps MP4 video render and thumbnails...';
    }
  }
}

function showAgentSwarm() {
  const section = document.getElementById('agent-swarm-section');
  section.classList.add('active');
  initAgentGrid();
}

function hideAgentSwarm() {
  const section = document.getElementById('agent-swarm-section');
  section.classList.remove('active');
}

// ═══════ PROGRESS VIEW ═══════
function showProgressView() {
  document.getElementById('input-section').style.display = 'none';
  document.getElementById('progress-section').classList.add('active');
  document.getElementById('clips-section').classList.remove('active');
  showAgentSwarm();

  const logContainer = document.getElementById('agent-console-log');
  if (logContainer) {
    logContainer.innerHTML = '<div style="color:var(--pink-300);font-weight:bold;">[Agent Swarm Started] Swarm initialized. Logs streaming below:</div>';
  }
}

function hideProgressView() {
  document.getElementById('progress-section').classList.remove('active');
  hideAgentSwarm();
}

const STAGE_ORDER = ['downloading', 'transcribing', 'analyzing', 'rendering'];
let lastLoggedMessage = '';

function updateProgress(progress, message, stage) {
  const bar = document.getElementById('progress-bar');
  if (bar) bar.style.width = `${progress}%`;

  const msgEl = document.getElementById('progress-message');
  if (msgEl) msgEl.textContent = message;

  const pctEl = document.getElementById('progress-percent');
  if (pctEl) pctEl.textContent = Math.round(progress);

  const stageLabels = {
    downloading: 'Ingesting Video Stream',
    loading: 'Loading Local File',
    transcribing: 'AI Speech Transcription',
    analyzing: 'Viral Hook & Retention Analysis',
    rendering: 'Synthesizing Kinetic Shorts',
  };
  const stageEl = document.getElementById('progress-stage');
  if (stageEl) stageEl.textContent = stageLabels[stage] || stage;

  const currentIdx = STAGE_ORDER.indexOf(stage);
  document.querySelectorAll('.progress-step').forEach((step) => {
    const stepStage = step.dataset.stage;
    const stepIdx = STAGE_ORDER.indexOf(stepStage);

    step.classList.remove('active', 'done');
    if (stepIdx < currentIdx) {
      step.classList.add('done');
    } else if (stepIdx === currentIdx) {
      step.classList.add('active');
    }
  });

  animateAgentSwarm(progress);

  if (message && message !== lastLoggedMessage) {
    lastLoggedMessage = message;
    logToConsole(message);
  }

  lucide.createIcons();
}

// ═══════ CLIPS DISPLAY ═══════
function showClipsView(clips) {
  activeClips = clips;
  hideProgressView();

  const section = document.getElementById('clips-section');
  const countBadge = document.getElementById('clips-count-badge');
  const grid = document.getElementById('clips-grid');

  section.classList.add('active');
  countBadge.textContent = `${clips.length} Clips`;
  grid.innerHTML = '';

  if (!clips.length) {
    grid.innerHTML = `
      <div style="grid-column: 1/-1; text-align:center; padding:48px; color:var(--cream-muted);">
        <i data-lucide="alert-circle" style="width:40px;height:40px;margin:0 auto 16px;display:block;color:var(--pink-300);"></i>
        <p>No viral clips found. Try uploading a longer video or using a different AI engine preset.</p>
      </div>`;
    lucide.createIcons();
    return;
  }

  clips.forEach((clip, index) => {
    const score = clip.score || (90 - index * 3);
    const scoreClass = score >= 85 ? 'high' : 'medium';
    const confidence = Math.min(99, score + 4);

    const card = document.createElement('div');
    card.className = 'clip-card glass glass-hover';
    card.style.animationDelay = `${index * 0.1}s`;

    card.innerHTML = `
      <div class="clip-video-wrapper">
        <video src="${clip.download_url}" controls preload="metadata" poster="${clip.thumbnail || ''}"></video>
        <div class="clip-score-badge ${scoreClass}">
          🔥 ${score}/100 Virality
        </div>
        <div class="clip-duration-badge">
          ⏱ ${clip.duration}s
        </div>
      </div>

      <div class="clip-info">
        <h3 class="clip-headline">${clip.headline || 'Viral Highlight Clip'}</h3>
        <p class="clip-reason">${clip.reason || 'High retention opener detected with fast speech velocity.'}</p>
      </div>

      <div class="clip-confidence">
        <div class="confidence-header">
          <span class="confidence-label">Agent Consensus</span>
          <span class="confidence-value">${confidence}% Agreement</span>
        </div>
        <div class="confidence-bar-bg">
          <div class="confidence-bar-fill" style="width:${confidence}%;"></div>
        </div>
      </div>

      <div class="clip-actions">
        <button class="clip-btn clip-btn-edit" onclick="openEditor(${index})">
          <i data-lucide="edit-3" style="width:14px;height:14px;"></i>
          <span>Edit</span>
        </button>
        <a href="${clip.download_url}" download="${clip.filename}" class="clip-btn clip-btn-download">
          <i data-lucide="download" style="width:14px;height:14px;"></i>
          <span>Download</span>
        </a>
      </div>
    `;

    grid.appendChild(card);
  });

  lucide.createIcons();

  // Scroll to clips gallery
  setTimeout(() => {
    section.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, 200);
}

// ═══════ PROCESSING PIPELINE ═══════
async function startGeneration() {
  const isYt = !document.getElementById('tab-yt').classList.contains('hidden');
  const url = document.getElementById('video-url').value.trim();
  const engine = document.getElementById('setting-engine').value;
  const subtitleStyle = document.getElementById('setting-subtitles').value;
  const layout = document.getElementById('setting-layout').value;

  const durVal = document.getElementById('setting-duration')?.value || "20-60";
  const [minDur, maxDur] = durVal.split('-').map(v => parseFloat(v));

  if (isYt && !url) {
    shakeElement(document.querySelector('.url-input'));
    return;
  }
  if (!isYt && !currentFile) {
    shakeElement(document.getElementById('drop-zone'));
    return;
  }

  showProgressView();
  updateProgress(5, 'Connecting to processing pipeline...', 'downloading');

  try {
    let payload = {
      ai_method: engine,
      subtitle_style: subtitleStyle,
      layout: layout,
      min_duration: minDur || 20.0,
      max_duration: maxDur || 60.0,
      max_clips: 5,
    };

    if (isYt) {
      payload.url = url;
      logToConsole(`Initiating download for URL: ${url}`);
      const res = await fetch('/api/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      currentTaskId = data.task_id;
      logToConsole(`Task registered on server: ID #${currentTaskId}`);
      startPolling(currentTaskId);
    } else {
      updateProgress(10, 'Uploading local video file...', 'downloading');
      logToConsole(`Uploading file: ${currentFile.name} (${(currentFile.size / 1024 / 1024).toFixed(1)} MB)...`);
      const formData = new FormData();
      formData.append('file', currentFile);

      const uploadRes = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });
      const uploadData = await uploadRes.json();
      logToConsole(`File uploaded successfully to ${uploadData.filepath}`);

      payload.filepath = uploadData.filepath;
      const res = await fetch('/api/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      currentTaskId = data.task_id;
      logToConsole(`Task registered on server: ID #${currentTaskId}`);
      startPolling(currentTaskId);
    }
  } catch (err) {
    console.error('Start error:', err);
    logToConsole(err.message, 'error');
    updateProgress(0, `Error: ${err.message}`, 'downloading');
    setTimeout(resetToInput, 4000);
  }
}

function startPolling(taskId) {
  if (pollInterval) clearInterval(pollInterval);
  pollInterval = setInterval(async () => {
    try {
      const res = await fetch(`/api/status/${taskId}`);
      const state = await res.json();

      updateProgress(
        state.progress || 0,
        state.message || 'Processing...',
        state.stage || 'processing'
      );

      if (state.status === 'completed') {
        clearInterval(pollInterval);
        pollInterval = null;
        logToConsole(`Completed! Generated ${state.clips ? state.clips.length : 0} viral clips.`, 'success');
        showClipsView(state.clips || []);
      } else if (state.status === 'failed') {
        clearInterval(pollInterval);
        pollInterval = null;
        logToConsole(state.error || 'Pipeline execution failed.', 'error');
        updateProgress(0, `Error: ${state.error || 'Pipeline failed'}`, 'downloading');
        setTimeout(resetToInput, 4000);
      }
    } catch (err) {
      console.error('Poll error:', err);
    }
  }, 1200);
}

function resetToInput() {
  hideProgressView();
  hideAgentSwarm();
  document.getElementById('input-section').style.display = '';
  document.getElementById('clips-section').classList.remove('active');
}

// ═══════ SHAKE ANIMATION ═══════
function shakeElement(el) {
  if (!el) return;
  el.style.animation = 'none';
  el.offsetHeight;
  el.style.animation = 'shake 0.5s ease';
  el.style.borderColor = 'var(--pink-400)';
  setTimeout(() => {
    el.style.borderColor = '';
    el.style.animation = '';
  }, 1000);

  if (!document.getElementById('shake-style')) {
    const style = document.createElement('style');
    style.id = 'shake-style';
    style.textContent = `
      @keyframes shake {
        0%, 100% { transform: translateX(0); }
        20% { transform: translateX(-8px); }
        40% { transform: translateX(8px); }
        60% { transform: translateX(-6px); }
        80% { transform: translateX(6px); }
      }
    `;
    document.head.appendChild(style);
  }
}

// ═══════ EDITOR MODAL ═══════
function openEditor(index) {
  editingClip = activeClips[index];
  if (!editingClip) return;

  const modal = document.getElementById('editor-modal');
  const player = document.getElementById('editor-player');

  player.src = editingClip.download_url;
  document.getElementById('editor-headline').value = editingClip.headline || '';
  document.getElementById('editor-start').value = editingClip.start;
  document.getElementById('editor-end').value = editingClip.end;
  document.getElementById('editor-captions').value = (editingClip.clip_words || [])
    .map((w) => w.word)
    .join(' ');

  modal.classList.add('active');
  lucide.createIcons();
}

function closeEditor() {
  const modal = document.getElementById('editor-modal');
  const player = document.getElementById('editor-player');
  if (player) player.pause();
  modal.classList.remove('active');
}

async function saveAndReExportClip() {
  if (!editingClip) return;

  const btn = document.getElementById('re-render-btn');
  btn.disabled = true;
  const originalHTML = btn.innerHTML;
  btn.innerHTML = `
    <div class="progress-spinner" style="width:18px;height:18px;border-width:2px;"></div>
    <span>Re-rendering...</span>
  `;

  const start = parseFloat(document.getElementById('editor-start').value);
  const end = parseFloat(document.getElementById('editor-end').value);
  const headline = document.getElementById('editor-headline').value;
  const style = document.getElementById('editor-style').value;
  const layout = document.getElementById('editor-layout').value;
  const customText = document.getElementById('editor-captions').value;

  try {
    const res = await fetch('/api/edit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_video: editingClip.source_video,
        start_time: start,
        end_time: end,
        headline: headline,
        layout: layout,
        subtitle_style: style,
        custom_text: customText,
        words: editingClip.clip_words || [],
      }),
    });
    const updated = await res.json();
    if (updated.success) {
      document.getElementById('editor-player').src = updated.download_url;
      alert('✅ Re-rendered successfully! New version is playing in preview.');
    } else {
      alert('Error: ' + (updated.error || 'Re-render failed'));
    }
  } catch (err) {
    alert('Re-render failed: ' + err.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = originalHTML;
    lucide.createIcons();
  }
}

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeEditor();
});

document.getElementById('editor-modal')?.addEventListener('click', (e) => {
  if (e.target === e.currentTarget) closeEditor();
});
