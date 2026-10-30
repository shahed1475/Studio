"""The picture review looked at 10 frames of every video: 10 of 15,000 frames of an 8-minute film, and the same 10 of a 55-second Short. The sample now grows with the length
(about one frame every 25 seconds, never fewer than 10, never more than 24 so the cost stays at a few cents) and the coverage line still says plainly that it is not a viewing."""
from pathlib import Path

import videoinspect


def test_the_sample_grows_with_the_length_and_has_a_floor_and_a_ceiling():
    assert videoinspect.sample_frames(None) == 10 and videoinspect.sample_frames(0) == 10
    assert videoinspect.sample_frames(55) == 10          # a Short
    assert videoinspect.sample_frames(250) == 10
    assert videoinspect.sample_frames(502) == 20         # the Lost Army film
    assert videoinspect.sample_frames(900) == 24 and videoinspect.sample_frames(5000) == 24


def test_the_review_asks_for_that_many_frames_unless_told_otherwise(monkeypatch, tmp_path):
    asked = []
    monkeypatch.setattr(videoinspect, "_video_seconds", lambda p: 502.0)
    monkeypatch.setattr(videoinspect, "inspect_source", lambda src, q, frames, post=None, **k: asked.append(frames) or {"analysis": None, "errors": [{"error": "x"}]})
    videoinspect.visual_review(tmp_path / "doc-x")
    videoinspect.visual_review(tmp_path / "doc-x", frames=6)
    assert asked == [20, 6]
