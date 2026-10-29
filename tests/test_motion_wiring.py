"""The motion switches reach the render (29 Oct 2026): a video can ask for 2.5D camera motion (`parallax`), 2D chapter cards and date badges (`graphics`), a trimmed voice
tail (`voice_tail`) and its own loudness (`target_lufs`). A video that asks for none of them is made exactly as before."""
import json

import pytest

import config
import footage
import motiongraphics
import parallax
import run
import tts


def lines(n=12):
    return [{"text": "In 1983 a team searched the dunes." if i == 6 else f"Line number {i} of the story.", "visual": "v"} for i in range(n)]


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(run.config, "OUT", tmp_path / "out")
    monkeypatch.setattr(config, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(run, "PENDING_DOC", tmp_path / "pending.json")
    art = tmp_path / "cache" / "art"
    art.mkdir(parents=True)
    seen = {"narrate": [], "render": None, "parallax": None}

    def narrate(texts, work, pause, *a, **kw):
        seen["narrate"].append(kw)
        work.mkdir(parents=True, exist_ok=True)
        (work / "words.json").write_text(json.dumps([{"s": i * 2.0, "e": i * 2.0 + 1.0, "w": "word", "i": i} for i in range(len(texts))]))
        return work / "n.wav", work / "a.ass", [2.0] * len(texts)

    def pics(lns, *a, **k):
        clips = []
        for i in range(len(lns)):
            p = art / f"{i}.jpg"
            p.write_bytes(b"x")
            clips.append(p)
        return clips, [], {"scenes": len(lns), "unique": len(lns), "missing": 0, "drawn": len(lns)}

    def fake_apply(clips, durations, size, **kw):
        seen["parallax"] = (list(clips), list(durations), size)
        return [p.with_suffix(".mp4") for p in clips], {"scenes": len(clips), "made": len(clips), "cached": 0, "model": len(clips), "approximate": 0, "skipped": 0, "failed": 0}

    def fake_render(clips, durations, narration, ass, work, out, **kw):
        seen["render"] = {"clips": list(clips), "ass": ass.read_text() if ass and ass.exists() else None, **kw}
        raise RuntimeError("reached render")

    monkeypatch.setattr(run.tts, "narrate", narrate)
    monkeypatch.setattr(run.editprofile, "load", lambda: {"sentence_pause_ms": 600, "target_lufs": -16.0, "motion": 1, "caption_pos": "bottom"})
    monkeypatch.setattr(run, "_image_judge", lambda topic: None)
    monkeypatch.setattr(footage, "scene_images", pics)
    monkeypatch.setattr(parallax, "apply", fake_apply)
    monkeypatch.setattr(run.render, "render", fake_render)
    return seen


def doc(**extra):
    return {"title": "T", "topic": "Topic", "lines": lines(), "chapters": [{"title": "The Legend", "start_line": 0}, {"title": "The Search", "start_line": 4}], **extra}


def test_a_document_that_asks_for_motion_gets_parallax_clips_graphics_loudness_and_a_voice_tail(world):
    with pytest.raises(RuntimeError, match="reached render"):
        run._produce_doc(doc(parallax=True, graphics=True, voice_tail=0.15, target_lufs=-14.0))
    clips, durations, size = world["parallax"]
    assert size == (1920, 1080) and len(clips) == 12 and durations == [2.0] * 12
    assert all(str(c).endswith(".mp4") for c in world["render"]["clips"])  # the render got the moving clips
    assert world["render"]["loudness"] == -14.0
    assert world["narrate"] == [{"tail": 0.15}]
    ass = world["render"]["ass"]
    assert "Style: Card," in ass and "CHAPTER 2" in ass and "The Search" in ass and "1983" in ass and "Style: Badge," in ass


def test_a_document_that_asks_for_nothing_is_made_as_before(world):
    with pytest.raises(RuntimeError, match="reached render"):
        run._produce_doc(doc())
    assert world["parallax"] is None and world["narrate"] == [{}]
    assert world["render"]["loudness"] == -16.0
    assert "Card" not in world["render"]["ass"] and "Badge" not in world["render"]["ass"]
    assert all(str(c).endswith(".jpg") for c in world["render"]["clips"])


def test_the_stats_of_the_motion_are_kept_on_the_video_and_a_failure_keeps_the_plain_camera(world, monkeypatch):
    data = doc(parallax=True)
    monkeypatch.setattr(parallax, "apply", lambda *a, **k: (_ for _ in ()).throw(OSError("no ffmpeg")))
    with pytest.raises(RuntimeError, match="reached render"):
        run._produce_doc(data)
    assert data["parallax"]["failed"] is True and all(str(c).endswith(".jpg") for c in world["render"]["clips"])  # the video is still made, with the usual camera moves


def test_a_short_can_ask_for_the_same_motion_at_its_own_size(world, monkeypatch):
    monkeypatch.setattr(run.config, "PEXELS_KEY", "")
    monkeypatch.setattr(footage, "enough_footage", lambda clips: True)
    monkeypatch.setattr(run.editprofile, "load", lambda: {"sentence_pause_ms": 600, "target_lufs": -16.0, "motion": 1, "caption_pos": "bottom"})
    data = {"title": "T", "topic": "t", "anchors": [], "lines": lines(), "parallax": True, "voice_tail": 0.15}
    with pytest.raises(RuntimeError, match="reached render"):
        run._produce_short(data, "t", requeue=False)
    assert world["parallax"][2] == (config.WIDTH, config.HEIGHT) and world["narrate"] == [{"tail": 0.15}]


def test_a_voice_tail_set_for_one_video_overrides_a_styles_tail(tmp_path, monkeypatch):
    import subprocess

    async def fake(text, mp3, prosody=None):
        return [(0.0, 0.5, "hi")]

    monkeypatch.setattr(tts, "_synth_line", fake)
    monkeypatch.setattr(tts, "_duration", lambda p: 2.0)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: None)
    _, _, d = tts.narrate(["one"], tmp_path, pause=0.5, style="energetic", tail=0.3)
    assert d == [pytest.approx(0.5 + 0.3 + 0.5)]
    _, _, d = tts.narrate(["one"], tmp_path, pause=0.5, tail=0.3)  # no style at all: the tail still applies when the video asks for it
    assert d == [pytest.approx(0.5 + 0.3 + 0.5)]
    _, _, d = tts.narrate(["one"], tmp_path, pause=0.5)
    assert d == [2.5]
