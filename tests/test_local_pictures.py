"""A documentary can be made from pictures drawn elsewhere for free (1 Nov 2026, ccdoc.py): `local_pictures` replaces the picture search, the paid drawing and the stock footage."""
import json
from pathlib import Path

import pytest

import config
import footage
import run


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(run.config, "OUT", tmp_path / "out")
    monkeypatch.setattr(config, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(run, "PENDING_DOC", tmp_path / "pending.json")
    seen = {"render": None, "searched": False}

    def narrate(texts, work, pause, *a, **kw):
        work.mkdir(parents=True, exist_ok=True)
        (work / "words.json").write_text(json.dumps([{"s": i * 2.0, "e": i * 2.0 + 1.0, "w": "word", "i": i} for i in range(len(texts))]))
        return work / "n.wav", work / "a.ass", [2.0] * len(texts)

    def no_search(*a, **k):
        seen["searched"] = True
        raise AssertionError("a documentary with its own pictures must not search or draw")

    def fake_render(clips, durations, narration, ass, work, out, **kw):
        seen["render"] = {"clips": list(clips), "size": kw.get("size")}
        raise RuntimeError("reached render")

    monkeypatch.setattr(run.tts, "narrate", narrate)
    monkeypatch.setattr(run.editprofile, "load", lambda: {"sentence_pause_ms": 600, "target_lufs": -16.0, "motion": 1, "caption_pos": "bottom"})
    monkeypatch.setattr(footage, "scene_images", no_search)
    monkeypatch.setattr(run, "_real_footage", no_search)
    monkeypatch.setattr(run, "_animate", no_search)
    monkeypatch.setattr(run.render, "render", fake_render)
    return seen


def doc(tmp_path, n=8, **extra):
    pics = []
    for i in range(n):
        p = tmp_path / f"p{i % 3}.png"
        p.write_bytes(b"x")
        pics.append(str(p))
    return {"title": "T", "topic": "Topic", "lines": [{"text": f"Line {i}.", "visual": ""} for i in range(n)], "chapters": [{"title": "One", "start_line": 0}],
            "local_pictures": pics, "local_credits": ["Pictures drawn by code and AI on the owner's PC"], "art_style": "local", **extra}


def test_local_pictures_go_straight_to_the_render_without_a_search_or_a_paid_drawing(world, tmp_path):
    with pytest.raises(RuntimeError, match="reached render"):
        run._produce_doc(doc(tmp_path))
    assert world["searched"] is False and len(world["render"]["clips"]) == 8 and world["render"]["size"] == (1920, 1080)
    assert [p.name for p in world["render"]["clips"][:4]] == ["p0.png", "p1.png", "p2.png", "p0.png"]


def test_a_missing_local_picture_stops_the_build_before_any_voice_is_paid_for(world, tmp_path):
    d = doc(tmp_path)
    d["local_pictures"][3] = str(tmp_path / "gone.png")
    with pytest.raises(SystemExit, match="gone.png"):
        run._produce_doc(d)


def test_the_studios_own_free_pictures_get_camera_motion_and_a_picture_from_anywhere_else_does_not(tmp_path, monkeypatch):
    import animate
    import depth
    import parallax
    from PIL import Image

    monkeypatch.setattr(config, "CACHE", tmp_path / "cache")
    own = tmp_path / "cache" / "cc" / "f-1.png"
    own.parent.mkdir(parents=True)
    Image.new("RGB", (64, 36), (10, 20, 30)).save(own)
    other = tmp_path / "archive.png"
    Image.new("RGB", (64, 36), (10, 20, 30)).save(other)
    assert animate.own_picture(own) and not animate.own_picture(other)
    monkeypatch.setattr(depth, "depth_for", lambda clip: (Image.new("L", (64, 36), 128), "approximate"))
    made = []
    monkeypatch.setattr(parallax, "_job", lambda job: (made.append(job[0]), Path(job[2]).write_bytes(b"clip"))[0] or True)
    clips, stats = parallax.apply([own, other], [4.0, 4.0], (1920, 1080), workers=1)
    assert stats["skipped"] == 1 and len(made) == 1 and made[0] == str(own) and str(clips[0]).endswith(".mp4") and clips[1] == other
