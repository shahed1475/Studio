import re

import aiart
import packaging
import scriptgen
import tts


def test_documentary_length_is_capped_at_about_eight_minutes():
    for t in ("La Llorona", "Pied Piper", "Delphi", "Hong Gildong", "Thunderbird", "Voynich", "x", "y", "z"):
        c, per = scriptgen.shape_for(t)
        assert c * per <= scriptgen.MAX_DOC_LINES and 6 <= c <= 9 and 5 <= per <= 7


def test_a_script_that_admits_its_sources_say_little_is_thin():
    assert scriptgen.thin_script([{"text": "I won't invent details about it, because my sources say very little."}])
    assert not scriptgen.thin_script([{"text": "Little is known about the builders."}])  # honest history, not an admission of a thin script
    assert not scriptgen.thin_script([{"text": "The Athenian Treasury marks their victory at Marathon in 490 BC."}])


def test_removing_retold_lines_moves_the_chapter_starts():
    lines = [{"text": str(i)} for i in range(6)]
    chapters = [{"title": "a", "start_line": 0}, {"title": "b", "start_line": 3}, {"title": "c", "start_line": 5}]
    kept, moved = scriptgen.remove_lines(lines, chapters, {1, 4})
    assert [l["text"] for l in kept] == ["0", "2", "3", "5"]
    assert [c["start_line"] for c in moved] == [0, 2, 3]


def test_each_video_gets_one_style_and_the_channel_uses_several():
    assert aiart.style_for("La Llorona") == aiart.style_for("la llorona")
    assert len({aiart.style_for(t) for t in ("a", "b", "c", "d", "e", "f", "g", "h")}) >= 3
    assert all("no text" in s and "photo" not in s.lower() for s in aiart.STYLES)


def test_the_picture_variety_warning_names_the_numbers():
    meta = {"title": "t", "format": "doc", "footage": {"scenes": 46, "unique": 13}}
    row = {r["name"]: r for r in packaging.audit(meta)}["picture_variety"]
    assert not row["ok"] and "13 different pictures for 46 scenes" in row["detail"]
    assert {r["name"]: r for r in packaging.audit({**meta, "footage": {"scenes": 30, "unique": 30}})}["picture_variety"]["ok"]


def test_captions_never_overlap_however_fast_the_words_come():
    import random
    rnd = random.Random(7)
    words, t = [], 0.0
    for line in range(12):
        for k in range(rnd.randint(4, 14)):
            d = rnd.uniform(0.08, 0.5)
            words.append((t, t + d, rnd.choice(["Navajo", "orbs", "and", "animals", "strange", "glowing", "the", "ranch", "in", "1883"]), line))
            t += d + rnd.uniform(0.0, 0.1)
    rows = []
    for l in tts._ass_rich(words).splitlines():
        if l.startswith("Dialogue: 0,"):
            p = l.split(",", 4)
            sec = lambda s: sum(float(x) * k for x, k in zip(s.split(":"), (3600, 60, 1)))
            rows.append((sec(p[1]), sec(p[2])))
    assert rows and all(b[0] >= a[1] - 0.005 for a, b in zip(rows, rows[1:]))


def test_honest_history_is_not_called_thin():
    assert not scriptgen.thin_script([{"text": "Little is known about the builders, and not much is known about the date."}])
    assert scriptgen.thin_script([{"text": "I won't invent details about it."}, {"text": "x"}])
    assert scriptgen.thin_script([{"text": "The sources say very little here."}])


def test_removing_every_line_of_a_chapter_drops_the_chapter_and_keeps_starts_distinct():
    lines = [{"text": str(i)} for i in range(6)]
    chapters = [{"title": "a", "start_line": 0}, {"title": "b", "start_line": 2}, {"title": "c", "start_line": 3}, {"title": "d", "start_line": 5}]
    kept, moved = scriptgen.remove_lines(lines, chapters, {2, 5})  # b's only line and d's only line
    assert [c["title"] for c in moved] == ["a", "c"] and [c["start_line"] for c in moved] == [0, 2]
    assert all(c["start_line"] < len(kept) for c in moved)


def test_an_uploaded_video_is_never_redone_in_place(tmp_path, monkeypatch):
    import json

    import config
    import run
    monkeypatch.setattr(config, "OUT", tmp_path)
    (tmp_path / "v").mkdir()
    (tmp_path / "v" / "meta.json").write_text(json.dumps({"title": "t", "video_id": "abc"}))
    for f in (run.cmd_redo, run.cmd_redo_short):
        try:
            f("v")
            raise AssertionError("should have refused")
        except SystemExit as e:
            assert "is on YouTube" in str(e)


def test_tags_that_are_chapter_numbers_of_a_novel_are_dropped():
    import seo
    got = seo.relevant_tags(["hong gildong", "hong gildong chapter 12", "hong gildong chapter 13", "episode 4 recap", "korean folklore"],
                            "hong gildong korean folklore chapter episode recap 12 13 4")
    assert "hong gildong" in got and "korean folklore" in got
    assert not any("chapter" in t or "episode" in t for t in got)
