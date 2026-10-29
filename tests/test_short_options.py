"""Options of a Short made on purpose (29 Oct 2026): every scene drawn, an energetic voice, a louder target, the whole source article, set aside held."""
import pytest

import footage
import run
import scriptgen


def lines(n=6):
    return [{"text": f"Line {i}.", "visual": "v"} for i in range(n)]


def test_draw_all_forces_every_line_to_be_drawn_and_nothing_else_does():
    ls = lines()
    assert run._forced_art({"lines": ls, "draw_all": True}) == {l["text"] for l in ls}
    assert run._forced_art({"lines": ls}) == set()
    assert run._forced_art({"lines": ls, "art_style": "3d"}) == {l["text"] for l in ls[:4]}  # unchanged
    assert run._forced_art({"lines": ls, "draw_all": True, "redraw_lines": ["Extra."]}) >= {"Extra."}


def _short_run(tmp_path, monkeypatch, data):
    seen = {}
    monkeypatch.setattr(run.config, "OUT", tmp_path)
    monkeypatch.setattr(run.config, "PEXELS_KEY", "")

    def narrate(ls, work, pause=0.12, motion=0, pos="bottom", **kw):
        seen["narrate"] = kw
        return work / "n.mp3", work / "c.ass", [1.0] * len(ls)

    def render(*a, **k):
        seen["render"] = k
        raise RuntimeError("reached render")

    monkeypatch.setattr(run.tts, "narrate", narrate)
    monkeypatch.setattr(footage, "scene_images", lambda ls, topic, anchors, pool_size=6, judge=None, **kw: (["a", "b", "c", "d"], [], {"scenes": 4, "unique": 4, "missing": 0}))
    monkeypatch.setattr(footage, "enough_footage", lambda clips: True)
    monkeypatch.setattr(run.render, "render", render)
    with pytest.raises(RuntimeError, match="reached render"):
        run._produce_short(data, "t", requeue=False)
    return seen


def test_a_styled_loud_short_reaches_the_voice_and_the_renderer(tmp_path, monkeypatch):
    base = {"title": "T", "topic": "t", "anchors": [], "lines": [{"text": "x", "visual": "y"}] * 4}
    seen = _short_run(tmp_path, monkeypatch, {**base, "voice_style": "energetic", "target_lufs": -13.0})
    assert seen["narrate"] == {"style": "energetic"} and seen["render"]["loudness"] == -13.0


def test_a_plain_short_is_made_exactly_as_before(tmp_path, monkeypatch):
    base = {"title": "T", "topic": "t", "anchors": [], "lines": [{"text": "x", "visual": "y"}] * 4}
    seen = _short_run(tmp_path, monkeypatch, base)
    assert seen["narrate"] == {} and seen["render"]["loudness"] == run.editprofile.load()["target_lufs"]


def test_a_short_script_is_written_from_the_whole_article_not_its_first_3500_characters(monkeypatch):
    got = {}
    monkeypatch.setattr("wikipedia.facts_for", lambda topic, chars=7000: got.setdefault("chars", chars) and None)
    monkeypatch.setattr(scriptgen, "script", lambda *a, **k: (_ for _ in ()).throw(ValueError("stop here")))
    with pytest.raises(SystemExit, match="could not generate"):
        run._cmd_make("A topic")
    assert got["chars"] == run.SHORT_SOURCE_CHARS and run.SHORT_SOURCE_CHARS >= 7000


def test_make_options_become_settings_of_the_video(monkeypatch):
    assert run._make_options(["Lost", "Army", "--draw-all", "--voice", "energetic", "--lufs", "-13", "--hold"]) == (
        "Lost Army", {"art_style": "3d", "draw_all": True, "voice_style": "energetic", "target_lufs": -13.0, "hold": True})
    assert run._make_options(["Lost", "Army"]) == ("Lost Army", {})
    with pytest.raises(SystemExit):
        run._make_options(["x", "--voice", "shouting"])  # an unknown voice style is refused, not ignored
    with pytest.raises(SystemExit):
        run._make_options(["x", "--lufs", "loud"])


def test_the_extra_settings_are_merged_into_the_script_before_the_short_is_made(monkeypatch):
    made = {}
    monkeypatch.setattr("wikipedia.facts_for", lambda topic, chars=7000: ("Title", "Some source text."))
    monkeypatch.setattr(scriptgen, "script", lambda *a, **k: {"title": "T", "lines": [{"text": "x", "visual": "y"}], "anchors": []})
    monkeypatch.setattr(run, "_script_gate", lambda data, src, topic: data)
    monkeypatch.setattr(run, "_produce_short", lambda data, topic, **k: made.update(data) or "folder")
    run._cmd_make("A topic", {"voice_style": "energetic", "hold": True})
    assert made["voice_style"] == "energetic" and made["hold"] is True and made["sources"]
