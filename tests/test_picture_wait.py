"""A film whose every scene is drawn waits for tomorrow's free pictures instead of being rendered with repeated pictures (run._wait_for_pictures, 20 Nov 2026)."""
import json

import pytest

import agentlog
import config
import footage
import run


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(run.config, "OUT", tmp_path / "out")
    monkeypatch.setattr(config, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(run, "PENDING_DOC", tmp_path / "pending_doc.json")
    art_dir = tmp_path / "cache" / "art"
    art_dir.mkdir(parents=True)
    state = {"left": 3, "render": False}

    def narrate(texts, work, pause, *a, **kw):
        work.mkdir(parents=True, exist_ok=True)
        (work / "words.json").write_text(json.dumps([{"s": i * 2.0, "e": i * 2.0 + 1.0, "w": "word", "i": i} for i in range(len(texts))]))
        (work / "n.wav").write_bytes(b"RIFF")
        return work / "n.wav", work / "a.ass", [2.0] * len(texts)

    def generate(text, visual, topic, **k):  # the free account draws three pictures, then today's allowance is spent
        if state["left"] <= 0:
            return None
        state["left"] -= 1
        p = art_dir / f"{abs(hash(text))}.jpg"
        p.write_bytes(b"x")
        return p, "AI-generated illustration"

    def pics(lns, topic, anchors, art=None, **k):
        clips = []
        for l in lns:
            got = art(l) if art else None
            clips.append(got[0] if got else (clips[0] if clips else None))  # what the real picker does when nothing can be drawn: reuse
        return clips, [], {"scenes": len(lns), "unique": len({str(c) for c in clips}), "missing": 0, "drawn": 3}

    def fake_render(*a, **k):
        state["render"] = True
        raise RuntimeError("reached render")

    import aiart

    monkeypatch.setattr(run.tts, "narrate", narrate)
    monkeypatch.setattr(run.editprofile, "load", lambda: {"sentence_pause_ms": 600, "target_lufs": -16.0, "motion": 1, "caption_pos": "bottom"})
    monkeypatch.setattr(run, "_image_judge", lambda topic: None)
    monkeypatch.setattr(run, "_real_finder", lambda data, fmt: None)
    monkeypatch.setattr(aiart, "generate", generate)
    monkeypatch.setattr(footage, "scene_images", pics)
    monkeypatch.setattr(run.render, "render", fake_render)
    monkeypatch.setattr(run, "_free_pictures_spent", lambda: state["left"] <= 0)
    return state


def film(n=8):
    return {"title": "A Long Film", "topic": "Topic", "art_style": "photo", "lines": [{"text": f"Line {i} of the story.", "visual": f"scene {i}"} for i in range(n)],
            "chapters": [{"title": "One", "start_line": 0}, {"title": "Two", "start_line": 4}]}


def test_a_film_that_runs_out_of_free_pictures_waits_and_keeps_its_script_and_tries(world):
    data = film()
    run.PENDING_DOC.write_text(json.dumps({"data": data, "folder": "", "tries": 1}))  # the make that is running counted as one try
    with pytest.raises(SystemExit, match="waiting for pictures"):
        run._produce_doc(data)
    assert not world["render"]  # never rendered with five reused pictures
    saved = json.loads(run.PENDING_DOC.read_text())
    assert saved["tries"] == 0 and saved["waiting_for_pictures"] == {"short": 5, "total": 8} and (run.config.OUT / saved["folder"]).is_dir()
    ev = json.loads(agentlog.FILE.read_text().splitlines()[-1])
    assert ev["title"].startswith("Waiting for tomorrow's free pictures") and "00:00 UTC" in ev["detail"]


def test_a_film_with_enough_pictures_is_rendered_as_before(world):
    world["left"] = 100
    with pytest.raises(RuntimeError, match="reached render"):
        run._produce_doc(film())
    assert world["render"]
