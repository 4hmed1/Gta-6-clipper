import pytest
import numpy as np
from clipforge.core.stream_clipper import StreamClipperEngine

def test_stream_clipper_fusion():
    engine = StreamClipperEngine()
    duration = 100.0

    chat_timeline = np.zeros(100)
    chat_timeline[40:50] = 3.0  # Spike in chat

    heatmap_timeline = np.zeros(100)
    heatmap_timeline[42:48] = 0.9

    audio_signals = {
        "rms": np.zeros(200)
    }
    audio_signals["rms"][80:100] = 0.8

    fused = engine.fuse_signals(duration, chat_timeline, heatmap_timeline, audio_signals)

    assert len(fused) == 100
    assert fused[45] > 1.0  # Should reflect the spike

def test_stream_moment_detection():
    engine = StreamClipperEngine()
    timeline = np.zeros(300)
    timeline[100:120] = 5.0  # Clear peak

    moments = engine.detect_stream_moments(timeline, min_duration=15.0, max_duration=30.0)

    assert len(moments) > 0
    assert moments[0]["start"] <= 100
    assert moments[0]["end"] >= 100
