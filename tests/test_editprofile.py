import json
import subprocess
from pathlib import Path

import editprofile
import render
import tts


def test_defaults_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(editprofile, "FILE", tmp_path / "p.json")
    assert editprofile.load() == {"target_lufs": -16.0, "sentence_pause_ms": 120, "motion": 2, "caption_pos": "bottom"}


def test_validate_drops_unknown_and_out_of_range():
    assert editprofile.validate({"target_lufs": -5, "evil": 1, "sentence_pause_ms": "300"}) == {"sentence_pause_ms": 300}
    assert editprofile.validate({"target_lufs": "loud", "sentence_pause_ms": 5000}) == {}


def test_update_persists(tmp_path, monkeypatch):
    monkeypatch.setattr(editprofile, "FILE", tmp_path / "p.json")
    got = editprofile.update({"target_lufs": -14, "junk": 3})
    assert got["target_lufs"] == -14.0 and got["sentence_pause_ms"] == 120 and got["motion"] == 2
    assert json.loads((tmp_path / "p.json").read_text())["target_lufs"] == -14.0
    assert editprofile.load()["target_lufs"] == -14.0


def _capture_render(tmp_path, monkeypatch, music, loudness):
    calls = []
    monkeypatch.setattr(render, "_ff", lambda *a, cwd: calls.append(list(a)))
    work = tmp_path / "w"
    work.mkdir(exist_ok=True)
    render.render([None], [1.0], work / "n.mp3", None, work, tmp_path / "out.mp4", music=music, loudness=loudness)
    return calls[-1]


def test_render_adds_loudnorm_filter(tmp_path, monkeypatch):
    last = _capture_render(tmp_path, monkeypatch, None, -16.0)
    assert any("loudnorm=I=-16" in str(x) for x in last)
    last = _capture_render(tmp_path, monkeypatch, tmp_path / "m.mp3", -14.0)
    assert any("loudnorm=I=-14" in str(x) for x in last)


def test_render_without_loudness_has_no_loudnorm(tmp_path, monkeypatch):
    assert not any("loudnorm" in str(x) for x in _capture_render(tmp_path, monkeypatch, None, None))


def test_narrate_uses_pause(tmp_path, monkeypatch):
    async def fake(text, mp3):
        return [(0.0, 0.5, "hi")]

    monkeypatch.setattr(tts, "_synth_line", fake)
    monkeypatch.setattr(tts, "_duration", lambda p: 1.0)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: None)
    _, _, durations = tts.narrate(["one", "two"], tmp_path, pause=0.5)
    assert durations == [1.5, 1.5]
    _, _, durations = tts.narrate(["one"], tmp_path)
    assert durations == [1.12]


def test_synth_line_retries_then_succeeds(tmp_path, monkeypatch):
    import asyncio

    calls = []

    async def once(text, mp3):
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("No audio was received")
        return [(0.0, 0.1, "ok")]

    async def nosleep(s):
        return None

    monkeypatch.setattr(tts, "_synth_once", once)
    monkeypatch.setattr(tts.asyncio, "sleep", nosleep)
    assert asyncio.run(tts._synth_line("hello", tmp_path / "a.mp3")) == [(0.0, 0.1, "ok")]
    assert len(calls) == 3


def test_synth_line_gives_up_after_four_tries(tmp_path, monkeypatch):
    import asyncio

    calls = []

    async def once(text, mp3):
        calls.append(1)
        raise RuntimeError("No audio was received")

    async def nosleep(s):
        return None

    monkeypatch.setattr(tts, "_synth_once", once)
    monkeypatch.setattr(tts.asyncio, "sleep", nosleep)
    import pytest

    with pytest.raises(RuntimeError, match="No audio"):
        asyncio.run(tts._synth_line("hello", tmp_path / "a.mp3"))
    assert len(calls) == 4


def test_motion_level_is_a_validated_integer():
    assert editprofile.validate({"motion": 1}) == {"motion": 1}
    assert editprofile.validate({"motion": "0"}) == {"motion": 0}
    assert editprofile.validate({"motion": 3}) == {}
    assert editprofile.validate({"motion": -1}) == {}


def test_caption_position_is_a_validated_choice():
    assert editprofile.validate({"caption_pos": "top"}) == {"caption_pos": "top"}
    assert editprofile.validate({"caption_pos": "middle"}) == {}
    assert editprofile.validate({"caption_pos": 3}) == {}
