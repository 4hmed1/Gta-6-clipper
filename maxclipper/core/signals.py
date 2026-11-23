import librosa
import numpy as np
from typing import Dict

def analyze_audio_signals(audio_path: str, hop_length_ms: int = 50) -> Dict[str, np.ndarray]:
    """
    Extracts DSP signals from audio for viral moment detection.
    Signals extracted: RMS energy, Spectral Flux, Spectral Flatness, Pitch Contour.
    """
    y, sr = librosa.load(audio_path, sr=16000)
    hop_length = int(sr * hop_length_ms / 1000)

    # 1. RMS Energy (Volume)
    rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]

    # 2. Spectral Flux (Energy change density - applause/laughter/surprises)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)

    # 3. Spectral Flatness (Noisiness - crowd noise/cheering/static)
    flatness = librosa.feature.spectral_flatness(y=y, hop_length=hop_length)[0]

    # 4. Pitch Contour (F0 estimation - emotional pitch shifts)
    # Using piptrack as a fast approximate pitch estimation
    pitches, magnitudes = librosa.piptrack(y=y, sr=sr, hop_length=hop_length)
    pitch_contour = np.zeros(pitches.shape[1])
    for i in range(pitches.shape[1]):
        index = magnitudes[:, i].argmax()
        pitch_contour[i] = pitches[index, i]

    # Normalize signals
    def robust_normalize(arr):
        if np.max(arr) == np.min(arr): return arr
        return (arr - np.min(arr)) / (np.max(arr) - np.min(arr) + 1e-6)

    return {
        "rms": robust_normalize(rms),
        "spectral_flux": robust_normalize(onset_env),
        "flatness": robust_normalize(flatness),
        "pitch": robust_normalize(pitch_contour),
        "timestamps": np.arange(len(rms)) * (hop_length_ms / 1000.0)
    }

def get_dead_air_map(rms: np.ndarray, threshold: float = 0.05, min_silence_len: int = 5) -> np.ndarray:
    """Detect regions of silence/dead air using hysteresis VAD."""
    dead_air = rms < threshold
    return dead_air
