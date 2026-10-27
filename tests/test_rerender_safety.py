import pytest

import aiart
import llm
import run
from test_animation import NOW, art  # noqa: F401  (the fixture that fakes the picture call)


@pytest.fixture
def doc_world(tmp_path, monkeypatch):
    monkeypatch.setattr(run.config, "OUT", tmp_path / "out")
    monkeypatch.setattr(run, "PENDING_DOC", tmp_path / "pending_doc.json")
    monkeypatch.setattr(run.tts, "narrate", lambda texts, work, pause: ("n.wav", "a.ass", [2.0] * len(texts)))
    monkeypatch.setattr(run.editprofile, "load", lambda: {"sentence_pause_ms": 300})
    monkeypatch.setattr(run, "_image_judge", lambda topic: None)
    monkeypatch.setattr(aiart, "enabled", lambda now=None: False)
    # the pictures could not be found or drawn: 3 different ones for 10 scenes
    monkeypatch.setattr(run.footage, "scene_images", lambda lines, *a, **k: ([None] * len(lines), [], {"scenes": len(lines), "unique": 3, "missing": 0, "drawn": 0}))
    return {"title": "T", "topic": "Topic", "lines": [{"text": f"Line {i}.", "visual": "v"} for i in range(10)], "chapters": [{"title": "A", "start_line": 0}]}


def test_a_re_render_that_finds_too_few_pictures_never_removes_the_video_it_was_redoing(doc_world, tmp_path):
    folder = tmp_path / "out" / "doc-t"
    (folder / "thumbs").mkdir(parents=True)
    for name in ("video.mp4", "meta.json", "claims.json", "words.json"):
        (folder / name).write_text("kept")
    (folder / "thumbs" / "thumb-1.jpg").write_text("kept")
    with pytest.raises(SystemExit, match="not rendering a video of unrelated pictures"):
        run._produce_doc(doc_world, folder)
    assert sorted(p.name for p in folder.iterdir()) == ["claims.json", "meta.json", "thumbs", "video.mp4", "words.json"]
    assert (folder / "thumbs" / "thumb-1.jpg").read_text() == "kept" and (folder / "video.mp4").read_text() == "kept"


def test_a_new_video_with_too_few_pictures_still_leaves_no_half_made_folder(doc_world, tmp_path):
    with pytest.raises(SystemExit):
        run._produce_doc(doc_world)
    assert not list((tmp_path / "out").glob("doc-*"))


def test_a_picture_already_drawn_is_served_when_the_days_budget_is_spent_or_drawing_is_off(art, monkeypatch):  # noqa: F811
    first = aiart.generate("A monk writes.", "a desk", "Winter", now=NOW, style="photo")
    thumb = aiart.thumbnail_art("a monk at a desk", NOW, style="photo")
    assert first and thumb and len(art) == 2
    monkeypatch.setattr(llm, "spent_today", lambda now=None: 99.0)  # the budget is spent
    assert aiart.generate("A monk writes.", "a desk", "Winter", now=NOW, style="photo") == first
    assert aiart.thumbnail_art("a monk at a desk", NOW, style="photo") == thumb
    monkeypatch.setattr(aiart, "enabled", lambda now=None: False)  # drawing off
    assert aiart.generate("A monk writes.", "a desk", "Winter", now=NOW, style="photo") == first
    assert len(art) == 2  # nothing was bought


def test_a_new_picture_is_still_refused_when_the_budget_is_spent(art, monkeypatch):  # noqa: F811
    monkeypatch.setattr(llm, "spent_today", lambda now=None: 99.0)
    assert aiart.generate("A new scene.", "a hall", "Winter", now=NOW) is None
    assert aiart.thumbnail_art("a new subject", NOW) is None
    assert art == []
