import copy
import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

import numbershort
import subtitles
import tts

SPEC = json.loads((Path(__file__).parent.parent / "examples" / "numbershort" / "fastest-goal.json").read_text())


def spec(**over):
    s = copy.deepcopy(SPEC)
    s.update(over)
    return s


def test_the_example_spec_is_valid_and_clean():
    assert numbershort.validate(SPEC) == ([], [])


@pytest.mark.parametrize("key", ["video", "clips", "footage", "source_video", "youtube_url", "download", "images", "face"])
def test_a_spec_with_third_party_material_is_refused(key):
    errors, _ = numbershort.validate(spec(**{key: "x"}))
    assert any("third-party" in e for e in errors)


def test_two_real_sources_are_needed():
    assert any("two sources" in e for e in numbershort.validate(spec(sources=SPEC["sources"][:1]))[0])
    bad = [{**s, "passage": ""} for s in SPEC["sources"]]
    assert any("two sources" in e for e in numbershort.validate(spec(sources=bad))[0])
    http = [{**s, "url": s["url"].replace("https", "http")} for s in SPEC["sources"]]
    assert any("two sources" in e for e in numbershort.validate(spec(sources=http))[0])
    undated = [{k: v for k, v in s.items() if k != "read"} for s in SPEC["sources"]]
    assert any("two sources" in e for e in numbershort.validate(spec(sources=undated))[0])


def test_the_card_and_line_rules():
    lines = copy.deepcopy(SPEC["lines"])
    assert any("5 to 9" in e for e in numbershort.validate(spec(lines=lines[:3]))[0])
    lines[1]["card"]["type"] = "poster"
    assert any("unknown card" in e for e in numbershort.validate(spec(lines=lines))[0])
    lines = copy.deepcopy(SPEC["lines"])
    del lines[2]["card"]["last"]
    assert any("needs 'last'" in e for e in numbershort.validate(spec(lines=lines))[0])
    lines = copy.deepcopy(SPEC["lines"])
    lines[2]["card"]["last"] = "x" * 31
    assert any("longer than" in e for e in numbershort.validate(spec(lines=lines))[0])
    lines = copy.deepcopy(SPEC["lines"])
    lines[0]["card"] = {"type": "counter", "to": 5, "label": "s"}
    assert any("at most one counter" in e for e in numbershort.validate(spec(lines=lines))[0])
    lines = copy.deepcopy(SPEC["lines"])
    lines[1]["text"] = "word " * 90
    assert any("too many" in e for e in numbershort.validate(spec(lines=lines))[0])
    assert any("title" in e for e in numbershort.validate(spec(title="x" * 71))[0])


def test_the_hook_and_the_invitation_are_warnings_not_errors():
    lines = copy.deepcopy(SPEC["lines"])
    lines[0]["text"] = "Eleven seconds is the record."
    lines[-1]["text"] = "That is all."
    errors, warns = numbershort.validate(spec(lines=lines))
    assert errors == [] and len(warns) == 2


@pytest.mark.parametrize("kind", sorted(numbershort.CARDS))
def test_every_card_type_draws_a_full_size_picture(kind):
    card = next(l["card"] for l in SPEC["lines"] if l["card"]["type"] == kind) if any(l["card"]["type"] == kind for l in SPEC["lines"]) else \
        {"type": "stopwatch", "value": "00.00", "label": "x"}
    img = numbershort.draw_card(card)
    assert img.size == (1080, 1920) and img.mode == "RGB"


def test_text_is_never_wider_than_its_limit():
    d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    for size in (60, 200, 620):
        f = numbershort.fit(d, "KOREA REPUBLIC AND A VERY LONG NAME", size, 800)
        assert d.textlength("KOREA REPUBLIC AND A VERY LONG NAME", font=f) <= 800 or f.size == 40


def test_the_counter_runs_then_holds():
    card = next(l["card"] for l in SPEC["lines"] if l["card"]["type"] == "counter")
    frames = list(numbershort.counter_frames(card, 60))
    assert len(frames) == 60
    assert frames[0].tobytes() != frames[30].tobytes() != frames[-1].tobytes()
    assert frames[-1].tobytes() == frames[-5].tobytes()  # after RUN_TO the clock holds its number


def test_a_respelling_is_for_the_voice_only():
    say = {"Şükür": "Shookoor"}
    assert numbershort.restore_spelling("HAKAN SHOOKOOR and Shookoor and shookoor", say) == "HAKAN ŞÜKÜR and Şükür and şükür"
    before = dict(tts.PRONUNCIATION)
    with numbershort.respelled(say):
        assert tts.spoken("Hakan Şükür scored") == "Hakan Shookoor scored"
    assert tts.PRONUNCIATION == before


def test_a_bad_spec_builds_nothing(tmp_path):
    with pytest.raises(ValueError):
        numbershort.build(spec(footage="match.mp4"), out_root=tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_a_folder_this_tool_did_not_make_is_never_replaced(tmp_path):
    (tmp_path / numbershort.slug_of(SPEC["title"])).mkdir()
    with pytest.raises(FileExistsError, match="not made by this tool"):
        numbershort.build(spec(), out_root=tmp_path, replace=True)


def test_a_build_is_a_held_draft_with_its_sources_and_credits(tmp_path, monkeypatch):
    def narrate(lines, work, *a, **k):
        work.mkdir(parents=True, exist_ok=True)
        ass = work / "captions.ass"
        ass.write_text("Dialogue: 0,0:00:00.00,0:00:01.00,Cap,SHOOKOOR")
        (work / "words.json").write_text(json.dumps([{"s": i, "e": i + 0.5, "w": f"w{i}", "i": i} for i in range(len(lines))]))
        return work / "narration.mp3", ass, [1.0] * len(lines)

    monkeypatch.setattr(tts, "narrate", narrate)
    import render

    monkeypatch.setattr(render, "render", lambda clips, durations, narration, ass, work, out, **k: (Path(out).write_bytes(b"x"), out)[1])
    monkeypatch.setattr(numbershort, "counter_clip", lambda card, seconds, folder, work, theme="pitch": folder / "anim" / "counter.mp4")
    folder = numbershort.build(spec(), out_root=tmp_path)
    meta = json.loads((folder / "meta.json").read_text())
    assert meta["hold"] is True and meta["built_by"] == "numbershort" and meta["format"] == "short"
    assert len(meta["sources"]) == 3 and "Pictures: drawn by code" in meta["description"] and "https://www.guinnessworldrecords.com" in meta["description"]
    assert "ŞÜKÜR" in (folder / "work" / "captions.ass").read_text()
    assert (folder / "captions.srt").exists() and (folder / "card0.png").exists()
    assert numbershort.build(spec(), out_root=tmp_path, replace=True) == folder  # its own folder is rebuilt


def test_a_theme_changes_the_look_and_an_unknown_theme_is_refused():
    card = {"type": "end", "text": "Subscribe", "small": "x"}
    a, b = numbershort.draw_card(card, theme="pitch"), numbershort.draw_card(card, theme="stage")
    assert a.size == b.size == (1080, 1920) and a.tobytes() != b.tobytes()
    assert any("theme" in e for e in numbershort.validate(spec(theme="neon"))[0])
    assert numbershort.validate(spec(theme="stage"))[0] == []
    top_stage, top_pitch = b.getpixel((5, 5)), a.getpixel((5, 5))
    assert top_stage[2] > top_stage[1] and top_pitch[1] > top_pitch[2]  # navy against green


def test_a_low_big_card_keeps_clear_of_the_hook_caption():
    top = {"type": "big", "number": "?", "unit": "x"}
    a, b = numbershort.draw_card(top), numbershort.draw_card({**top, "low": True})
    box_a, box_b = a.convert("L").point(lambda v: 255 if v > 150 else 0).getbbox(), b.convert("L").point(lambda v: 255 if v > 150 else 0).getbbox()
    assert box_b[1] > 600 > box_a[1] - 1 or box_b[1] > box_a[1]  # the low card's glyphs start lower than the normal card's


def _src_file(tmp_path, text):
    f = tmp_path / "page.txt"
    f.write_text(text)
    return str(f)


def test_a_passage_must_be_in_the_saved_page_it_names(tmp_path):
    f = _src_file(tmp_path, "Ronaldo  became the first male player\nto score at five World Cups.")
    good = [{**s, "file": f, "passage": "Ronaldo became the first male player to score at five World Cups"} for s in SPEC["sources"]]
    assert numbershort.validate(spec(sources=good))[0] == []
    bad = [{**s, "file": f, "passage": "Ronaldo scored at six World Cups"} for s in SPEC["sources"]]
    assert any("not in the saved page" in e for e in numbershort.validate(spec(sources=bad))[0])


def test_a_listed_page_that_is_missing_is_refused(tmp_path):
    gone = [{**s, "file": str(tmp_path / "nope.txt")} for s in SPEC["sources"]]
    assert any("not in the saved page" in e for e in numbershort.validate(spec(sources=gone))[0])


def test_only_a_source_whose_passage_was_found_in_its_page_is_marked_checked(tmp_path):
    f = _src_file(tmp_path, "alpha beta gamma")
    srcs = [{**SPEC["sources"][0], "file": f, "passage": "alpha beta"}, {**SPEC["sources"][1]}]
    out = numbershort.mark_checked(srcs)
    assert out[0]["passage_checked"] is True and out[1]["passage_checked"] is False


def test_a_number_short_may_run_long_enough_for_the_studios_hundred_word_rule():
    assert numbershort.MAX_WORDS >= 130


def test_a_build_writes_a_claim_ledger_naming_the_listed_source_and_leaves_unchecked_claims_open(tmp_path, monkeypatch):
    page = tmp_path / "page.txt"
    page.write_text("Hakan Şükür scored in 2002 for Turkey.")
    srcs = [{**SPEC["sources"][0], "file": str(page), "passage": "Hakan Şükür scored in 2002 for Turkey"}, SPEC["sources"][1]]

    def narrate(lines, work, *a, **k):
        work.mkdir(parents=True, exist_ok=True)
        ass = work / "captions.ass"
        ass.write_text("x")
        (work / "words.json").write_text(json.dumps([{"s": i, "e": i + 0.5, "w": f"w{i}", "i": i} for i in range(len(lines))]))
        return work / "narration.mp3", ass, [1.0] * len(lines)

    monkeypatch.setattr(tts, "narrate", narrate)
    import render

    monkeypatch.setattr(render, "render", lambda clips, durations, narration, ass, work, out, **k: (Path(out).write_bytes(b"x"), out)[1])
    monkeypatch.setattr(numbershort, "counter_clip", lambda card, seconds, folder, work, theme="pitch": folder / "anim" / "counter.mp4")
    folder = numbershort.build(spec(sources=srcs), out_root=tmp_path)
    rows = json.loads((folder / "claims.json").read_text())
    by_claim = {r["claim_text"]: r for r in rows}
    assert by_claim["2002"]["verification_status"] == "VERIFIED" and by_claim["2002"]["source_url"] == srcs[0]["url"]
