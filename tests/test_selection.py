import pytest
from clipforge.core.selection import ClipSelector

def test_clip_selector_initialization():
    selector = ClipSelector("podcast")
    assert selector.content_type == "podcast"
    assert selector.config["weights"]["hook_score"] == 0.4

def test_nms_diversity():
    selector = ClipSelector()
    candidates = [
        {"start": 0, "end": 30, "score": 90, "text": "First clip"},
        {"start": 25, "end": 55, "score": 85, "text": "Second clip"},
        {"start": 100, "end": 130, "score": 95, "text": "Third clip"}
    ]

    selected = selector._nms_diversity(candidates, 2)

    # Should pick highest scoring non-overlapping clips
    assert len(selected) == 2
    assert selected[0]["score"] == 95  # Third clip (highest)
    assert selected[1]["score"] == 90  # First clip (next non-overlapping)

def test_calculate_overlap():
    selector = ClipSelector()

    # Overlapping clips
    cand1 = {"start": 0, "end": 30}
    cand2 = {"start": 20, "end": 50}
    overlap = selector._calculate_overlap(cand1, cand2)
    assert pytest.approx(overlap) == 0.333333333  # 10s overlap out of 30s max duration (10 / 30)

    # Non-overlapping clips
    cand3 = {"start": 0, "end": 20}
    cand4 = {"start": 30, "end": 50}
    overlap = selector._calculate_overlap(cand3, cand4)
    assert overlap == 0
