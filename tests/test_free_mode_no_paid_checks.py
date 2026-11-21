"""Free Mode never sends a request to a paid model through the checks that run around a video (20 Nov 2026).

The thumbnail score, the narration listen before an approval and the video analysis looked only at the daily dollar cap, so with paid models switched
off they still called anthropic/claude-sonnet-5.5, google/gemini-3.1-flash-lite and google/gemini-3.1-pro-preview."""
import json

import pytest

import config
import llm
import thumbscore
import videoinspect
import voicecheck

FREE = {"enabled": False, "free": True, "free_review": True, "ai_art": False, "daily_budget_usd": 5.0, "models": {}, "max_output_tokens": 6000}


@pytest.fixture
def free_mode(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "load_config", lambda: dict(FREE))
    monkeypatch.setattr(llm, "spent_today", lambda now=None: 0.0)  # plenty of cap left: only the switch may refuse
    monkeypatch.setattr(llm, "_post", lambda *a, **k: pytest.fail("Free Mode sent a request to a paid model"))
    monkeypatch.setattr(videoinspect, "model_modalities", lambda: pytest.fail("Free Mode asked OpenRouter about a paid model"))
    monkeypatch.setattr(config, "OUT", tmp_path)
    folder = tmp_path / "a-video"
    folder.mkdir()
    (folder / "video.mp4").write_bytes(b"\x00" * 64)
    (folder / "meta.json").write_text(json.dumps({"title": "T", "lines": [{"text": "A line."}]}))
    return folder


def test_paid_allowed_follows_the_paid_models_switch():
    assert llm.paid_allowed(dict(FREE)) is False and llm.paid_allowed({**FREE, "enabled": True}) is True


def test_the_thumbnail_score_is_skipped(free_mode):
    assert thumbscore.score([free_mode / "a.jpg"], "Title", "hook", post=lambda *a, **k: pytest.fail("paid vision model called")) is None


def test_the_video_analysis_refuses(free_mode):
    got = videoinspect.gemini_analyze(free_mode, post=lambda *a, **k: pytest.fail("paid video model called"))
    assert "Free Mode" in got.get("error", "")


def test_the_narration_listen_refuses_the_paid_model_but_not_local_whisper(free_mode, monkeypatch):
    got = voicecheck.listen(free_mode)
    assert "Free Mode" in got.get("error", "") and "--local" in got["error"]
    local = voicecheck.listen(free_mode, local=lambda audio: "a line")  # free, on this PC: allowed (it fails later here only because the test video has no words file)
    assert "Free Mode" not in local.get("error", "")
