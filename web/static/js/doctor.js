import { ref } from 'vue'
import { defineAsyncComponent } from 'vue'

export default {
  setup() {
    const doctor = ref(null)
    const loading = ref(true)
    const error = ref(null)

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

    return { doctor, loading, error }
  }
}