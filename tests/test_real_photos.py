"""13 Nov 2026 (owner: "use real photos"): the free picture model drew a wooden pagoda for the stone Seokgatap and a generic sepia crown for the Cheonmachong gold. Under the photo look every
scene is drawn whatever a search finds, so the real public-domain photos never got a chance. A scene whose own search names an anchor of the story and whose photo is titled with that
name now gets the real photo; everything else is still drawn."""
from pathlib import Path

import footage
import run

ANCHORS = ["Bulguksa", "Seokgatap", "Dabotap"]


def fake_search(monkeypatch, table):
    monkeypatch.setattr(footage, "images_for", lambda q, anchors, n, skip=(), judge=None: [(Path(f"{t}.jpg"), f"{t}.jpg (Wikimedia Commons, CC0)") for t in table.get(q, [])][:n])


def art(l):
    return Path("drawn.jpg"), "AI-generated"


def test_a_forced_scene_gets_the_real_photo_when_its_file_is_named_for_the_subject(monkeypatch):
    fake_search(monkeypatch, {"Seokgatap pagoda": ["Seokgatap Pagoda"], "Dabotap pagoda": ["Dabotap Pagoda 01"]})
    lines = [{"text": "a", "visual": "Seokgatap pagoda"}, {"text": "b", "visual": "Dabotap pagoda"}]
    clips, credits, stats = footage.scene_images(lines, "Bulguksa Temple", ANCHORS, art=art, art_limit=5, force_art={"a", "b"}, real_when_named=True)
    assert [c.name for c in clips] == ["Seokgatap Pagoda.jpg", "Dabotap Pagoda 01.jpg"] and stats["drawn"] == 0
    assert credits == ["Seokgatap Pagoda.jpg (Wikimedia Commons, CC0)", "Dabotap Pagoda 01.jpg (Wikimedia Commons, CC0)"]


def test_a_scene_that_names_nothing_specific_or_finds_an_unnamed_photo_is_still_drawn(monkeypatch):
    fake_search(monkeypatch, {"Silla royal court": ["Silla court painting"], "Seokgatap pagoda": ["Gyeongju street 03"]})
    lines = [{"text": "a", "visual": "Silla royal court"}, {"text": "b", "visual": "Seokgatap pagoda"}, {"text": "c", "visual": "ancestral rites"}]
    clips, credits, stats = footage.scene_images(lines, "Bulguksa Temple", ANCHORS, art=art, art_limit=5, force_art={"a", "b", "c"}, real_when_named=True)
    assert [c.name for c in clips] == ["drawn.jpg"] * 3 and stats["drawn"] == 3 and credits == ["AI-generated"]


def test_without_the_switch_nothing_changes(monkeypatch):
    fake_search(monkeypatch, {"Seokgatap pagoda": ["Seokgatap Pagoda"]})
    lines = [{"text": "a", "visual": "Seokgatap pagoda"}]
    clips, _, stats = footage.scene_images(lines, "Bulguksa Temple", ANCHORS, art=art, art_limit=5, force_art={"a"})
    assert clips[0].name == "drawn.jpg" and stats["drawn"] == 1


def test_a_photo_of_a_person_is_only_used_for_a_scene_about_that_person(monkeypatch):
    fake_search(monkeypatch, {"Kim Daeseong portrait": ["Seokgatap Pagoda"]})
    monkeypatch.setattr(footage, "unrelated_portrait", lambda title, query: True)
    clips, _, stats = footage.scene_images([{"text": "a", "visual": "Kim Daeseong portrait"}], "t", ["Seokgatap", "Kim Daeseong"], art=art, art_limit=5, force_art={"a"}, real_when_named=True)
    assert clips[0].name == "drawn.jpg"


def test_real_photos_are_off_for_a_case_a_3d_video_and_a_video_that_draws_everything():
    assert run._real_photos_on({"art_style": "photo", "lines": [], "title": "t"}) is True
    assert run._real_photos_on({"art_style": "3d"}) is False
    assert run._real_photos_on({"art_style": "photo", "draw_all": True}) is False
    assert run._real_photos_on({"art_style": "photo", "real_photos": False}) is False
    assert run._real_photos_on({"art_style": "photo", "kind": "case"}) is False
