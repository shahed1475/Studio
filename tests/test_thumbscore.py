import json

import pytest
from PIL import Image

import llm
import modelcfg
import thumbnail
import thumbscore
import videoinspect


def make_imgs(tmp_path, n):
    paths = []
    for i in range(n):
        p = tmp_path / f"c{i}.jpg"
        Image.new("RGB", (1280, 720), (20 * i, 40, 60)).save(p)
        paths.append(p)
    return paths


@pytest.fixture
def world(monkeypatch):
    monkeypatch.setattr(llm, "load_config", lambda: {"ai_art": True, "daily_budget_usd": 5.0, "models": {}, "enabled": True})
    monkeypatch.setattr(llm, "spent_today", lambda now=None: 0.0)
    monkeypatch.setattr(llm, "key_for", lambda model: "k")
    monkeypatch.setattr(llm, "_account", lambda *a, **k: None)
    monkeypatch.setattr(videoinspect, "model_modalities", lambda *a, **k: {"anthropic/claude-sonnet-5.5": ["text", "image"]})


def reply(parts_by_index):
    return {"choices": [{"message": {"content": json.dumps({"scores": [{"i": i, **p} for i, p in parts_by_index.items()]})}}]}


ALL8 = {k: 8 for k in thumbscore.PARTS}


def test_the_rubric_weights_add_up_and_every_part_is_named():
    assert abs(sum(thumbscore.PARTS.values()) - 1.0) < 1e-9
    assert set(thumbscore.PARTS) == {"focal_point", "mood", "contrast", "text_legibility", "text_adds_info", "honest_match"}


def test_candidates_are_scored_by_the_configured_vision_model_with_the_craft_rules(world, tmp_path):
    sent = []

    def post(body, key):
        sent.append(body)
        return reply({0: ALL8, 1: {**ALL8, "focal_point": 10, "text_legibility": 10}})

    got = thumbscore.score(make_imgs(tmp_path, 2), "Pied Piper: The Earliest Accounts Have No Rats", "NO RATS AT FIRST", post=post)
    assert [g["index"] for g in got] == [0, 1] and got[0]["total"] == 8.0 and got[1]["total"] > got[0]["total"]
    body = sent[0]
    assert body["model"] == modelcfg.get("thumbnail_score") and body["temperature"] <= 0.2
    text = body["messages"][0]["content"][0]["text"]
    assert "untrusted" in text and "NO RATS AT FIRST" in text and "Earliest Accounts" in text and "bottom-right" in text and "phone" in text
    images = [c for c in body["messages"][0]["content"] if c["type"] == "image_url"]
    assert len(images) == 4  # a full view and a phone-size view of each candidate


def test_a_thumbnail_that_does_not_match_the_story_cannot_win(world, tmp_path):
    post = lambda body, key: reply({0: {**ALL8, "honest_match": 2}, 1: {**ALL8, "focal_point": 5}})
    got = thumbscore.score(make_imgs(tmp_path, 2), "t", "h", post=post)
    assert got[0]["total"] <= 3.0 and got[1]["total"] > got[0]["total"]


def test_out_of_range_numbers_are_clamped_and_a_candidate_with_a_missing_part_gets_no_score(world, tmp_path):
    post = lambda body, key: reply({0: {**ALL8, "mood": 15, "contrast": -4}, 1: {"focal_point": 9}})
    got = thumbscore.score(make_imgs(tmp_path, 2), "t", "h", post=post)
    assert [g["index"] for g in got] == [0] and got[0]["parts"]["mood"] == 10 and got[0]["parts"]["contrast"] == 0


def test_no_score_when_the_model_fails_answers_nonsense_cannot_see_images_or_the_day_is_spent(world, tmp_path, monkeypatch):
    imgs = make_imgs(tmp_path, 2)
    assert thumbscore.score(imgs, "t", "h", post=lambda b, k: 1 / 0) is None
    assert thumbscore.score(imgs, "t", "h", post=lambda b, k: {"choices": [{"message": {"content": "no json here"}}]}) is None
    monkeypatch.setattr(videoinspect, "model_modalities", lambda *a, **k: {"anthropic/claude-sonnet-5.5": ["text"]})
    assert thumbscore.score(imgs, "t", "h", post=lambda b, k: reply({0: ALL8})) is None
    monkeypatch.setattr(videoinspect, "model_modalities", lambda *a, **k: {"anthropic/claude-sonnet-5.5": ["text", "image"]})
    monkeypatch.setattr(llm, "spent_today", lambda now=None: 9.0)
    called = []
    assert thumbscore.score(imgs, "t", "h", post=lambda b, k: called.append(1)) is None and not called


def test_the_best_candidate_goes_first_and_without_scores_the_order_is_kept():
    names = ["a", "b", "c", "d"]
    scores = [{"index": 1, "total": 7.0}, {"index": 3, "total": 9.0}]
    assert thumbscore.order(names, scores) == ["d", "b", "a", "c"]  # scored by total, the unscored after them in their old order
    assert thumbscore.order(names, None) == names and thumbscore.order(names, []) == names


def test_make_puts_the_best_scored_thumbnail_first_and_remembers_the_scores(monkeypatch, tmp_path):
    import aiart

    folder = tmp_path / "v"
    folder.mkdir()
    (folder / "video.mp4").write_bytes(b"x")
    (folder / "meta.json").write_text(json.dumps({"title": "T", "topic": "T", "format": "doc", "subtitles": None, "lines": [{"text": "x"}], "chapters": []}))
    frames = []
    for i in range(3):
        p = tmp_path / f"f{i}.jpg"
        Image.new("RGB", (thumbnail.W, thumbnail.H), (10 * i, 20, 30)).save(p)
        frames.append(p)
    monkeypatch.setattr(thumbnail, "_frames", lambda video, work, n=14, drop=None: (work.mkdir(parents=True, exist_ok=True), frames)[1])
    monkeypatch.setattr(thumbnail, "_best", lambda fr, k=3: fr[:k])
    monkeypatch.setattr(thumbnail, "fit_frames", lambda *a, **k: None)
    monkeypatch.setattr(thumbnail, "art_subject", lambda meta, chat=None: "a scene")  # no model call in this test
    monkeypatch.setattr(aiart, "thumbnail_art", lambda scene, now=None, **k: None)  # no drawing in this test: three frame thumbnails
    monkeypatch.setattr(thumbscore, "score", lambda paths, title, hook, post=None: [{"index": 0, "total": 5.0, "parts": {}}, {"index": 1, "total": 9.1, "parts": {}}, {"index": 2, "total": 6.0, "parts": {}}])
    names = thumbnail.make(folder, hook="HOOK")
    meta = json.loads((folder / "meta.json").read_text())
    assert names[0] == "thumbs/thumb-2.jpg" and meta["thumbnail"] == "thumbs/thumb-2.jpg" and meta["thumb_scores"]["thumbs/thumb-2.jpg"] == 9.1
    monkeypatch.setattr(thumbscore, "score", lambda *a, **k: None)
    assert thumbnail.make(folder, hook="HOOK")[0] == "thumbs/thumb-1.jpg"  # no score: the studio's own order
    assert "thumb_scores" not in json.loads((folder / "meta.json").read_text())  # and the old scores are not kept: they would describe a different order (27 Oct, Mami Wata v2)
