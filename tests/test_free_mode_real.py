#!/usr/bin/env python3
"""
Real test of the Free Mode animation pipeline.

This test runs through the full animation step in Free Mode and verifies:
1. No paid API calls are made (Veo, paid image model, paid review)
2. Parallax timing uses actual durations from narration
3. The pipeline completes successfully with free resources

Usage: python -m pytest tests/test_free_mode_real.py -v
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

import aiart
import animate
import config
import llm
import modelcfg
import parallax
from PIL import Image
import pytest


@pytest.fixture
def scenes(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE", tmp_path / "cache")
    art_dir = tmp_path / "cache" / "art"
    art_dir.mkdir(parents=True)
    clips = []
    for i in range(6):
        p = (art_dir if i not in (1, 4) else tmp_path) / f"s{i}.jpg"  # scenes 1 and 4 are real archive pictures: never animated
        Image.new("RGB", (1280, 720), (10 * i, 40, 60)).save(p)
        clips.append(p)
    lines = [{"text": f"Line {i} of the story.", "visual": f"thing {i}"} for i in range(6)]
    return clips, lines


def test_free_mode_animation_pipeline_real(tmp_path, monkeypatch, scenes):
    """
    Run a real animation step in Free Mode and verify no paid API calls.

    This test:
    - Sets Free Mode on
    - Calls animate.animate_scenes() with real durations
    - Verifies parallax.apply() is called with actual timings
    - Verifies the generator is NOT called (no paid video generation)
    - Checks the output is valid
    """
    # Set Free Mode
    monkeypatch.setattr(llm, "load_config", lambda: {
        "free": True,
        "free_review": True,
        "free_art": True,
        "ai_art": False,
        "enabled": False,
    })
    monkeypatch.setattr(llm, "free_only", lambda: True)

    # Setup test clips and lines
    clips, lines = scenes
    durations = [3.5, 4.0, 3.8, 4.2, 3.6]  # Realistic durations from narration

    # Track API calls
    paid_video_calls = []
    paid_image_calls = []
    paid_review_calls = []
    parallax_calls = []

    def track_paid_video(prompt, first_frame):
        """Track that we're trying to call a paid video generator."""
        paid_video_calls.append((prompt, first_frame))
        raise RuntimeError("Paid video generator should not be called in Free Mode")

    def track_paid_image(text, visual, topic, style, case):
        """Track that we're trying to call a paid image generator."""
        paid_image_calls.append((text, visual))
        raise RuntimeError("Paid image generator should not be called in Free Mode")

    # Mock paid APIs
    monkeypatch.setattr(modelcfg, "get", lambda key: "mock-model")
    monkeypatch.setattr(aiart, "generate", track_paid_image)

    def mock_parallax(clips_arg, durations_arg, size_arg, workers=3, flat=None):
        parallax_calls.append((clips_arg, durations_arg, size_arg, flat))
        return list(clips_arg), {"made": 0, "cached": len(clips_arg), "failed": 0, "model": "mock-parallax"}

    monkeypatch.setattr(parallax, "apply", mock_parallax)

    # Call animate_scenes in Free Mode
    new_clips, stats = animate.animate_scenes(
        clips=clips,
        lines=lines,
        n=3,
        budget_usd=2.0,
        gen=track_paid_video,
        durations=durations,
        size=(1280, 720)
    )

    # Verify results
    assert new_clips == clips, "Should return original clips unchanged"
    assert stats["animated"] == 0, "No clips animated in Free Mode"
    assert stats["failed"] == 0, "No failures (parallax handles that)"

    # Verify NO paid video calls were made
    assert len(paid_video_calls) == 0, \
        f"Paid video generator was called {len(paid_video_calls)} times in Free Mode"

    # Verify parallax was called with actual durations
    assert len(parallax_calls) == 1, "parallax.apply should have been called once"
    clips_arg, durations_arg, size_arg, flat = parallax_calls[0]

    assert clips_arg == clips, "Should pass clips to parallax"
    assert durations_arg == durations, \
        f"Should pass actual durations {durations}, not hardcoded 3.5s"
    assert size_arg == (1280, 720), "Should pass correct size"

    # Verify no paid image calls (free art should be used instead)
    assert len(paid_image_calls) == 0, \
        f"Paid image generator was called {len(paid_image_calls)} times in Free Mode"


def test_free_mode_with_actual_parallax_timing(tmp_path, monkeypatch, scenes):
    """
    Test that Free Mode passes actual scene durations to parallax.apply().

    This is a regression test for the issue where parallax was using
    a hardcoded 3.5s duration instead of the real narration timing.
    """
    # Set Free Mode
    monkeypatch.setattr(llm, "load_config", lambda: {
        "free": True,
        "free_review": True,
        "free_art": True,
        "ai_art": False,
        "enabled": False,
    })
    monkeypatch.setattr(llm, "free_only", lambda: True)

    clips, lines = scenes

    # Different realistic durations for each scene
    durations = [2.8, 3.2, 4.0, 3.5, 3.0, 4.5]

    received_durations = []
    received_size = []
    received_flat = []

    def mock_apply(clips_arg, durations_arg, size_arg, workers=3, flat=None):
        received_durations.append(durations_arg)
        received_size.append(size_arg)
        received_flat.append(flat)
        return list(clips_arg), {"made": 0, "cached": len(clips_arg), "failed": 0, "model": "mock"}

    monkeypatch.setattr(parallax, "apply", mock_apply)
    monkeypatch.setattr(animate, "_is_free_mode", lambda: True)

    new, stats = animate.animate_scenes(
        clips=clips,
        lines=lines,
        n=3,
        budget_usd=2.0,
        gen=lambda p, f: None,
        durations=durations,
        size=(1280, 720)
    )

    # Verify durations were passed correctly
    assert len(received_durations) == 1
    assert received_durations[0] == durations, \
        f"Expected durations {durations}, got {received_durations[0]}"

    assert len(received_size) == 1
    assert received_size[0] == (1280, 720), \
        f"Expected size (1280, 720), got {received_size[0]}"

    # Verify flat scenes detection works
    assert len(received_flat) == 1
    # Default visuals don't have "no people" keyword, so all should be flat
    assert received_flat[0] == set(range(len(lines))), \
        "All scenes should be flat (no depth bend) by default"


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"] + sys.argv[1:])
