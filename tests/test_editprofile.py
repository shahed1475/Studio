import json
import subprocess
from pathlib import Path

import editprofile
import render
import tts


def test_defaults_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(editprofile, "FILE", tmp_path / "p.json")
    assert editprofile.load() == {"target_lufs": -14.0, "sentence_pause_ms": 120, "motion": 2, "caption_pos": "bottom"}


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


# ---- an energetic voice for a Short, and a loudness target of its own (29 Oct 2026) ----
def test_the_energetic_voice_lifts_the_hook_and_the_questions_and_settles_the_payoff():
    lines = ["Did a sandstorm really swallow them?", "Herodotus wrote that it did.", "So where did they go?", "Kaper argued a rebel ambushed them.", "Subscribe, and I'll tell you the next story."]
    style = lambda i: tts.line_prosody("energetic", lines[i], i, len(lines))
    base = tts.VOICE_STYLES["energetic"]
    assert style(0)["pitch"] != style(1)["pitch"] and style(0)["rate"] != style(1)["rate"]  # the hook has its own lift
    assert style(2)["pitch"] != style(1)["pitch"]  # a question rises
    assert style(3)["rate"] != style(1)["rate"]  # the payoff is settled, not rushed
    assert style(4)["rate"] != style(1)["rate"]  # the invitation is bright
    assert all(style(i)["voice"] == base["voice"] for i in range(len(lines)))
    assert tts.line_prosody(None, lines[0], 0, 5) is None and tts.line_prosody("no-such-style", lines[0], 0, 5) is None  # no style, no change


def test_a_style_reaches_the_voice_service_and_no_style_leaves_the_old_call_alone(tmp_path, monkeypatch):
    import asyncio
    seen = []

    class FakeComm:
        def __init__(self, text, voice, **kw):
            seen.append((voice, kw))

        async def stream(self):
            yield {"type": "audio", "data": b"x"}

    monkeypatch.setattr(tts.edge_tts, "Communicate", FakeComm)
    asyncio.run(tts._synth_once("hello", tmp_path / "a.mp3"))
    asyncio.run(tts._synth_once("hello?", tmp_path / "b.mp3", tts.line_prosody("energetic", "Why?", 0, 5)))
    assert seen[0][0] == tts.config.VOICE and seen[0][1]["rate"] == tts.config.VOICE_RATE and seen[0][1]["pitch"] == tts.config.VOICE_PITCH
    assert seen[1][0] == tts.VOICE_STYLES["energetic"]["voice"] and seen[1][1]["rate"].startswith("+")


def test_a_video_may_ask_for_a_louder_target_but_never_outside_what_the_reviewer_accepts():
    import editprofile
    prof = {"target_lufs": -16.0}
    assert editprofile.lufs_for({"target_lufs": -13.0}, prof) == -13.0
    assert editprofile.lufs_for({}, prof) == -16.0
    for bad in (-9.0, -30.0, "loud", None):
        assert editprofile.lufs_for({"target_lufs": bad}, prof) == -16.0  # outside LIMITS or not a number: the profile's own target
