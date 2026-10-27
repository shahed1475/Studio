import json

import pytest

import aiart
import compliance
import llm
import run
from test_animation import NOW, art  # noqa: F401  (the fixture that fakes the picture call)


def test_the_default_look_is_still_an_illustration_and_never_the_realistic_one():
    assert aiart.STYLE_PHOTO not in aiart.STYLES
    assert all(aiart.style_for(t) != aiart.STYLE_PHOTO for t in ("a", "b", "c", "d", "e", "f", "g", "h"))
    assert aiart.prompt_for("A line.", "a room", "Topic", False).startswith(aiart.style_for("Topic"))


def test_the_realistic_style_asks_for_invented_period_correct_people_and_no_modern_objects():
    low = aiart.STYLE_PHOTO.lower()
    assert "photorealistic" in low and "invented, unnamed" in low and "never a portrait of a real" in low
    assert "no ballpoint pens" in low and "no elastic hair ties" in low and "no text" in low  # what the first test pictures got wrong
    assert aiart.prompt_for("A monk writes.", "a desk", "T", False, style="photo").startswith(aiart.STYLE_PHOTO)
    assert aiart.THUMB_PHOTO and "never a portrait of a real or famous person" in aiart.THUMB_PHOTO


def test_a_realistic_picture_is_labelled_as_ai_and_not_as_a_real_photograph():
    assert aiart.credit_for(None) == aiart.CREDIT and aiart.credit_for("3d") == aiart.CREDIT
    label = aiart.credit_for("photo")
    assert "ai-generated" in label.lower() and "not real photographs" in label.lower()  # studiochecks.ai_art_labelled looks for "ai-generated"


def test_a_realistic_scene_gets_its_own_cache_entry_prompt_and_credit(art):  # noqa: F811
    plain = aiart.generate("A monk writes.", "a desk", "Winter", now=NOW)
    photo = aiart.generate("A monk writes.", "a desk", "Winter", now=NOW, style="photo")
    assert plain[0] != photo[0] and plain[1] == aiart.CREDIT and photo[1] == aiart.CREDIT_PHOTO
    assert aiart.STYLE_PHOTO in art[1][1] and aiart.STYLE_PHOTO not in art[0][1]
    again = aiart.generate("A monk writes.", "a desk", "Winter", now=NOW, style="photo")
    assert again == photo and len(art) == 2  # the cached picture keeps its credit and costs nothing


def test_the_realistic_thumbnail_uses_the_realistic_prompt_and_credit(art):  # noqa: F811
    got = aiart.thumbnail_art("a monk at a desk", NOW, style="photo")
    assert got and got[1] == aiart.CREDIT_PHOTO and aiart.THUMB_PHOTO in art[0][1]


def test_the_disclosure_is_still_set_on_every_upload():
    import inspect
    import upload
    assert "containsSyntheticMedia" in inspect.getsource(upload) and "disclose" in compliance.RULES[[r["id"] for r in compliance.RULES].index("ai_disclosure")]["rule"].lower()


def test_doc_photo_flag_makes_a_held_realistic_video_and_the_default_does_not(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "PENDING_DOC", tmp_path / "pending_doc.json")
    monkeypatch.setattr(run.config, "OUT", tmp_path / "out")
    monkeypatch.setattr(run, "_pending_doc", lambda: None)
    monkeypatch.setattr(run, "_script_gate", lambda data, *a: data)
    monkeypatch.setattr(run.scriptgen, "thin_script", lambda lines: False)
    monkeypatch.setattr(run.packaging, "script_repeats", lambda texts: [])
    monkeypatch.setattr(run, "anchor_terms", lambda *a: [])
    import wikipedia
    monkeypatch.setattr(wikipedia, "facts_multi", lambda *a, **k: [])
    made = []
    monkeypatch.setattr(run.scriptgen, "doc_script", lambda topic, grounded=None: {"title": "T", "topic": topic, "lines": [{"text": "x"}], "chapters": []})
    monkeypatch.setattr(run, "_produce_doc", lambda data, folder=None: made.append(dict(data)) or tmp_path)
    run._cmd_doc("Winter nights", photo=True)
    run._cmd_doc("Winter nights")
    assert made[0]["art_style"] == "photo" and made[0]["hold"] is True and made[0]["art_first"] is True
    assert "art_style" not in made[1] and "hold" not in made[1]
    assert json.loads(run.PENDING_DOC.read_text())["data"].get("art_style") is None  # the second, plain run rewrote the saved script
