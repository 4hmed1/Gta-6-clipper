import pytest
import numpy as np
from maxclipper.core.signals import analyze_audio_signals, get_dead_air_map

def test_analyze_audio_signals():
    # Test with synthetic audio data
    # In a real test, you'd use a fixture with known audio file
    pass

def test_get_dead_air_map():
    # Test with synthetic RMS data
    rms = np.array([0.1, 0.05, 0.02, 0.1, 0.3, 0.05, 0.01])
    dead_air = get_dead_air_map(rms)

    # Should detect silence at indices 2 and 6
    assert dead_air[2] == True
    assert dead_air[6] == True
    assert dead_air[4] == False  # High energy segment
