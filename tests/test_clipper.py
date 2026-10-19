import json

import clipper
import config
import pytest

LINES = [{"text": f"Line {i} " + ("in 1453 the city fell " if i == 2 else "text here ") + ("? " if i == 3 else ""), "visual": f"v{i}"} for i in range(12)]
CHAPTERS = [{"title": "One", "start_line": 0}, {"title": "Two", "start_line": 4}, {"title": "Three", "start_line": 8}]
SECS = [8.0] * 12  # every line 8 seconds: a chapter is 32 s


def test_line_seconds_from_word_timings_and_estimate():
    words = [{"s": 0.0, "e": 1.0, "w": "a", "i": 0}, {"s": 1.0, "e": 3.0, "w": "b", "i": 0}, {"s": 3.2, "e": 4.0, "w": "c", "i": 1}]
    assert clipper.line_seconds(words, ["a b", "c"]) == [3.12, 0.92]
    est = clipper.line_seconds([], ["one two three four five six"])
    assert est == [pytest.approx(6 / 2.3 + 0.12, abs=0.01)]


def test_windows_start_at_chapters_and_fit_the_length_band():
    ws = clipper.windows(LINES, CHAPTERS, SECS, lo=25, hi=40)
    assert [(w["start"], w["end"]) for w in ws] == [(0, 4), (4, 8), (8, 12)]  # 4 lines = 32 s, a fifth line would be 40+... stays at 4
    assert all(25 <= w["secs"] <= 40 for w in ws)


def test_windows_skip_chapters_that_are_too_short_and_cut_long_ones():
    ws = clipper.windows(LINES, CHAPTERS, [3.0] * 12, lo=25, hi=40)
    assert ws == []  # 4 lines * 3 s = 12 s, even with the next chapter (24 s) it never reaches 25 inside one chapter
    ws = clipper.windows(LINES, [{"title": "All", "start_line": 0}], [10.0] * 12, lo=25, hi=45)
    assert [(w["start"], w["end"]) for w in ws] == [(0, 4)]  # stops at 40 s, the next line would pass 45


def test_score_prefers_numbers_questions_and_contrast():
    plain = clipper.score([{"text": "A calm quiet day went by"}] * 3)
    rich = clipper.score([{"text": "In 1453 the city fell, but why?"}, {"text": "Nobody knew the secret"}])
    assert rich > plain


def test_pick_is_non_overlapping_ranked_and_skips_used_starts():
    ws = clipper.windows(LINES, CHAPTERS, SECS, lo=25, hi=40)
    got = clipper.pick(ws, 2, used=[0])
    assert all(w["start"] != 0 for w in got) and len(got) == 2
    assert clipper.pick(ws, 5, used=[0, 4, 8]) == []
    assert got[0]["score"] >= got[1]["score"]


def test_hook_uses_model_and_falls_back_and_trims():
    meta = {"title": "Why Constantinople fell", "topic": "t"}
    w = {"start": 0, "end": 4, "lines": LINES[:4], "chapter": "One"}
    got = clipper.hook(meta, w, chat=lambda p: {"hook": "What really happened inside the walls on the final night of the siege today?", "title": "T" * 200})
    assert len(got["hook"].split()) <= 12 and len(got["title"]) <= 70
    got = clipper.hook(meta, w, chat=lambda p: (_ for _ in ()).throw(RuntimeError("down")))
    assert got["hook"] and len(got["hook"].split()) <= 12 and got["title"]


def test_build_short_shape():
    meta = {"topic": "Fall of Constantinople", "title": "Doc title", "tags": ["a"], "anchors": ["Hagia Sophia"], "grounded": True,
            "sources": ["https://en.wikipedia.org/wiki/X"], "video_id": "abc123", "description": "d"}
    w = {"start": 4, "end": 8, "lines": LINES[4:8], "chapter": "Two"}
    s = clipper.build_short(meta, w, {"hook": "What happened next?", "title": "The siege"}, "doc-x")
    assert s["format"] == "short" and s["title"] == "The siege" and s["source_doc"] == "doc-x" and s["clip_start_line"] == 4
    assert s["lines"][0]["text"] == "What happened next?" and s["lines"][-1]["text"] == clipper.OUTRO
    assert len(s["lines"]) == 6 and s["anchors"] == ["Hagia Sophia"]
    assert "https://youtu.be/abc123" in s["description"]
    assert "youtu.be" not in clipper.build_short({**meta, "video_id": None}, w, {"hook": "H?", "title": "T"}, "doc-x")["description"]


def make_doc(root, name, clips=(), verdict="pass", n=12, secs=8.0):
    d = root / name
    d.mkdir()
    words = [{"s": i * secs, "e": i * secs + secs - 0.1, "w": "w", "i": i} for i in range(n)]
    (d / "words.json").write_text(json.dumps(words))
    meta = {"topic": "t", "format": "doc", "title": name, "tags": [], "anchors": ["A"], "lines": LINES[:n], "chapters": CHAPTERS,
            "review": {"verdict": verdict}, "clips": list(clips), "approved": True, "publish_at": "2026-10-25T14:00:00Z"}
    (d / "meta.json").write_text(json.dumps(meta))
    return d


def test_make_next_builds_a_short_records_the_clip_and_stops_at_the_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path)
    make_doc(tmp_path, "doc-a")
    made = []
    produce = lambda data, topic, **kw: made.append(data) or tmp_path / "short-1"
    got = clipper.make_next(produce=produce, chat=lambda p: {"hook": "Why did it fall?", "title": "The fall"})
    assert got == tmp_path / "short-1" and made[0]["source_doc"] == "doc-a"
    assert json.loads((tmp_path / "doc-a" / "meta.json").read_text())["clips"] == [made[0]["clip_start_line"]]
    for _ in range(5):
        clipper.make_next(produce=produce, chat=lambda p: {"hook": "Why did it fall?", "title": "The fall"})
    assert len(json.loads((tmp_path / "doc-a" / "meta.json").read_text())["clips"]) == clipper.MAX_CLIPS


def test_make_next_ignores_failed_review_and_missing_docs(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path)
    assert clipper.make_next(produce=lambda *a, **k: pytest.fail("no docs")) is None
    make_doc(tmp_path, "doc-bad", verdict="fail")
    assert clipper.make_next(produce=lambda *a, **k: pytest.fail("failed review")) is None


def test_clippable_counts_docs_with_room(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path)
    make_doc(tmp_path, "doc-a")
    make_doc(tmp_path, "doc-b", clips=(0, 4, 8))
    assert clipper.clippable() == 1


def test_failed_chapter_is_remembered_and_next_one_is_tried(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path)
    make_doc(tmp_path, "doc-a")
    calls = []

    def produce(data, topic, **kw):
        calls.append(data["clip_start_line"])
        if len(calls) == 1:
            raise SystemExit("not enough footage found for this Short")
        return tmp_path / "short-2"

    got = clipper.make_next(produce=produce, chat=lambda p: {"hook": "Why?", "title": "T"})
    meta = json.loads((tmp_path / "doc-a" / "meta.json").read_text())
    assert got == tmp_path / "short-2" and len(calls) == 2 and calls[0] != calls[1]
    assert meta["clips_failed"] == [calls[0]] and meta["clips"] == [calls[1]]


def test_all_chapters_failing_returns_none_and_never_retries(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path)
    make_doc(tmp_path, "doc-a")
    n = []

    def produce(data, topic, **kw):
        n.append(1)
        raise RuntimeError("no audio")

    assert clipper.make_next(produce=produce, chat=lambda p: {"hook": "Why?", "title": "T"}) is None
    assert len(n) == 2  # two tries per run, then it stops
    assert clipper.make_next(produce=produce, chat=lambda p: {"hook": "Why?", "title": "T"}) is None
    assert len(n) == 3  # the third chapter, the last one; after that nothing is left
    assert clipper.make_next(produce=produce, chat=lambda p: {"hook": "Why?", "title": "T"}) is None
    assert len(n) == 3


def test_clips_ask_for_a_bigger_image_pool_and_accept_three_images(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path)
    make_doc(tmp_path, "doc-a")
    seen = {}

    def produce(data, topic, **kw):
        seen.update(kw)
        return tmp_path / "s"

    clipper.make_next(produce=produce, chat=lambda p: {"hook": "Why?", "title": "T"})
    assert seen == {"requeue": False, "pool_size": 10, "min_unique": 3}


def test_produce_short_threshold_is_configurable(tmp_path, monkeypatch):
    import footage
    import run

    monkeypatch.setattr(run.config, "OUT", tmp_path)
    monkeypatch.setattr(run.config, "PEXELS_KEY", "")
    monkeypatch.setattr(run.tts, "narrate", lambda lines, work, pause=0.12, motion=0, pos="bottom": (work / "n.mp3", work / "c.ass", [1.0] * len(lines)))
    monkeypatch.setattr(footage, "scene_images", lambda lines, topic, anchors, pool_size=6, judge=None, **kw: (["a", "b", "c", "a"], [], {"scenes": 4, "unique": 3, "missing": 0, "pool": pool_size}))
    monkeypatch.setattr(footage, "enough_footage", lambda clips: all(clips))
    monkeypatch.setattr(run.render, "render", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("reached render")))
    data = {"title": "T", "topic": "t", "anchors": [], "lines": [{"text": "x", "visual": "y"}] * 4}
    with pytest.raises(RuntimeError, match="reached render"):
        run._produce_short(data, "t", requeue=False, pool_size=10, min_unique=3)
    with pytest.raises(SystemExit, match="not enough footage"):  # the stricter default needs 4 different pictures
        run._produce_short(data, "t", requeue=False)


def test_a_doc_that_is_not_scheduled_yet_is_not_clipped(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path)
    d = make_doc(tmp_path, "doc-a")
    m = json.loads((d / "meta.json").read_text())
    m.pop("publish_at")
    (d / "meta.json").write_text(json.dumps(m))
    assert clipper.clippable() == 0  # its Short would say "the full story is on our channel" before it is
