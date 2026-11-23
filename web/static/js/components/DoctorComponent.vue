<template>
  <div class="container">
    <div class="header">
      <h1>🔍 MaxClipper Doctor</h1>
      <p>System Diagnostics & Environment Check</p>
    </div>

    <div v-if="loading" class="card">
      <div class="status info">Loading diagnostics...</div>
    </div>

    <div v-else-if="error" class="error-message">
      {{ error }}
    </div>

    <div v-else-if="doctor" class="card">
      <div class="status success">✓ All Systems Operational</div>

      <div class="check-item">
        <strong>Python Version:</strong>
        <span :class="['status', doctor.python.ok ? 'success' : 'error']">
          {{ doctor.python.version }} (min: {{ doctor.python.minVersion }})
        </span>
      </div>

      <div class="check-item">
        <strong>FFmpeg:</strong>
        <span :class="['status', doctor.ffmpeg.found ? 'success' : 'error']">
          {{ doctor.ffmpeg.found ? 'Found at ' + doctor.ffmpeg.path : 'Not Found' }}
        </span>
      </div>

      <div v-if="doctor.ffmpeg.encoders.length > 0">
        <strong>Hardware Encoders:</strong>
        <ul>
          <li v-for="encoder in doctor.ffmpeg.encoders" :key="encoder">
            {{ encoder }}
          </li>
        </ul>
      </div>

      <div class="check-item">
        <strong>Disk Space:</strong>
        <span :class="['status', doctor.disk.warning ? 'warning' : 'success']">
          {{ doctor.disk.free.toFixed(2) }} GB available
        </span>
      </div>

      <div class="check-item">
        <strong>yt-dlp:</strong>
        <span :class="['status', doctor.ytdlp.found ? 'success' : 'error']">
          {{ doctor.ytdlp.found ? 'Available' : 'Not Found' }}
        </span>
      </div>

      <div class="check-item">
        <strong>Port 3000:</strong>
        <span :class="['status', doctor.port.available ? 'success' : 'warning']">
          {{ doctor.port.available ? 'Available' : 'In use' }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const loading = ref(true)
const error = ref(null)
const doctor = ref(null)

// Simulate loading
setTimeout(() => {
  loading.value = false
  doctor.value = {
    status: "healthy",
    python: {
      version: "3.14.4",
      minVersion: "3.11",
      ok: true
    },
    ffmpeg: {
      found: true,
      path: "/usr/bin/ffmpeg",
      encoders: [
        "nvenc (NVIDIA)",
        "qsv (Intel QuickSync)",
        "vaapi (Linux)"
      ]
    },
    disk: {
      free: 48.48,
      warning: false
    },
    ytdlp: {
      found: true
    },
    port: {
      available: true,
      usedBy: null
    }
  }
}, 1000)
</script>

<style scoped>
.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.header {
  text-align: center;
  margin-bottom: 30px;
}

.header h1 {
  color: #2d3748;
  font-size: 2.5rem;
  margin-bottom: 10px;
}

.header p {
  color: #718096;
  font-size: 1.1rem;
}

.card {
  background: white;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24);
  padding: 20px;
  margin-bottom: 20px;
}

.card h2 {
  color: #2d3748;
  margin-bottom: 15px;
  font-size: 1.5rem;
}

.card p {
  color: #4a5568;
  margin-bottom: 10px;
}

.status {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 0.9rem;
  font-weight: 600;
}

.status.success {
  background-color: #c6f6d5;
  color: #2b7a48;
}

.status.warning {
  background-color: #fef6e6;
  color: #d69e2e;
}

.status.error {
  background-color: #fed7d7;
  color: #e53e3e;
}

.status.info {
  background-color: #e6f7ff;
  color: #2b7db0;
}

.check-item {
  margin: 10px 0;
}

.check-item strong {
  display: block;
  margin-bottom: 5px;
}

.error-message {
  color: #e53e3e;
  background-color: #fed7d7;
  padding: 15px;
  border-radius: 4px;
  margin: 20px 0;
}

ul {
  margin-left: 20px;
}
</style>