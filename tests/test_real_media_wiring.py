"""When a video uses real pictures from the libraries (run._real_media_on) and what the finder it gets is allowed to do."""
import pytest

import realmedia
import run


def data(**kw):
    return {"topic": "The Antikythera Mechanism", "anchors": ["Antikythera"], "kind": "mystery", **kw}


def test_real_media_is_on_by_default():
    assert run._real_media_on(data()) is True


@pytest.mark.parametrize("kw", [{"real_media": False}, {"art_style": "photo"}, {"art_style": "3d"}, {"draw_all": True}, {"kind": "case"}])
def test_real_media_is_off_when_the_video_is_drawn_on_purpose_or_is_a_real_case(kw):
    assert run._real_media_on(data(**kw)) is False
    assert run._real_finder(data(**kw), "doc") is None


def test_the_finder_caps_credit_needing_items_per_video_and_carries_the_judge(monkeypatch):
    monkeypatch.setattr(run, "_image_judge", lambda topic: (lambda labels: labels))
    doc, short = run._real_finder(data(), "doc"), run._real_finder(data(), "short")
    assert isinstance(doc, realmedia.Finder) and doc.credit_cap == 14 and short.credit_cap == 5
    assert doc.topic == "The Antikythera Mechanism" and doc.anchors == ["Antikythera"] and doc.judge(["a | commons"]) == ["a | commons"]


def test_a_plain_photo_less_video_other_than_a_case_is_not_blocked_by_an_unknown_kind(monkeypatch):
    assert run._real_media_on({"topic": "T", "anchors": [], "kind": "legend"}) is True
