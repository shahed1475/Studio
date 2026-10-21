from pathlib import Path

import footage
import reviewer
import wikipedia


def test_facts_for_returns_title_and_trimmed_text(monkeypatch):
    calls = []

    def fake_get(params):
        calls.append(params["action"])
        if params["action"] == "query" and params.get("list") == "search":
            return {"query": {"search": [{"title": "Pied Piper of Hamelin"}]}}
        return {"query": {"pages": {"1": {"title": "Pied Piper of Hamelin", "extract": "Intro.\n\n== History ==\n" + "word " * 5000}}}}

    monkeypatch.setattr(wikipedia, "_api", fake_get)
    title, text = wikipedia.facts_for("The Mystery of the Pied Piper", chars=1000)
    assert title == "Pied Piper of Hamelin"
    assert len(text) <= 1000 and text.startswith("Intro.")


def test_facts_for_none_when_nothing_found(monkeypatch):
    monkeypatch.setattr(wikipedia, "_api", lambda p: {"query": {"search": []}})
    assert wikipedia.facts_for("zzzz nothing") is None


def test_relevant_image_needs_an_anchor_in_title_or_categories():
    anchors = ["pied piper", "hamelin"]
    assert footage.image_relevant("Marktkirche Hameln.jpg", "Hamelin|Churches in Lower Saxony", anchors)
    assert footage.image_relevant("Illustration.jpg", "Pied Piper of Hamelin|Illustrations", anchors)
    assert not footage.image_relevant("Birmingham Quran manuscript.jpg", "Manuscripts", anchors)
    assert not footage.image_relevant("Kempele Church Bell Tower.jpg", "Churches in Finland", anchors)
    assert footage.image_relevant("anything.jpg", "", [])  # no anchors known: nothing to enforce


def _fake_images(monkeypatch, pool):
    def fake(query, anchors, limit=1, skip=(), judge=None):
        return [h for h in pool.get(query, []) if h[0] not in skip][:limit]
    monkeypatch.setattr(footage, "images_for", fake)


def test_scene_images_prefers_specific_then_pool_then_reuse(monkeypatch):
    a, b, c = Path("a.jpg"), Path("b.jpg"), Path("c.jpg")
    _fake_images(monkeypatch, {"Hamelin church": [(a, "A")], "Pied Piper": [(b, "B"), (c, "C")]})
    lines = [{"visual": "Hamelin church"}, {"visual": "nothing here"}, {"visual": "nothing here"},
             {"visual": "nothing here"}, {"visual": "nothing here"}]
    clips, credits, stats = footage.scene_images(lines, "Pied Piper", ["Pied Piper"])
    assert clips[0] == a and clips[1:3] == [b, c]          # specific first, then unused pool images
    assert all(clips) and len(clips) == 5                  # later scenes reuse rather than going blank
    assert stats == {"scenes": 5, "unique": 3, "missing": 0, "drawn": 0}
    assert credits == ["A", "B", "C"]


def test_scene_images_counts_missing_when_nothing_relevant(monkeypatch):
    _fake_images(monkeypatch, {})
    clips, credits, stats = footage.scene_images([{"visual": "x"}, {"visual": "y"}], "T", ["t"])
    assert clips == [None, None] and credits == [] and stats["missing"] == 2 and stats["unique"] == 0


def _meta(**kw):
    m = {"format": "doc", "title": "T", "grounded": True, "footage": {"scenes": 40, "unique": 12, "missing": 0}}
    m.update(kw)
    return m


def test_reviewer_blocks_missing_or_too_few_images():
    assert reviewer.footage_checks(_meta())[0]["ok"]
    bad = reviewer.footage_checks(_meta(footage={"scenes": 40, "unique": 3, "missing": 0}))
    assert not bad[0]["ok"] and bad[0]["severity"] == "block"
    gap = reviewer.footage_checks(_meta(footage={"scenes": 40, "unique": 12, "missing": 4}))
    assert not gap[0]["ok"]


def test_reviewer_flags_ungrounded_script_for_a_human():
    out = reviewer.footage_checks(_meta(grounded=False))
    g = [c for c in out if c["name"] == "grounded"][0]
    assert not g["ok"] and g["severity"] == "human"


def test_legacy_video_without_stats_only_warns():
    out = reviewer.footage_checks({"format": "doc", "title": "T"})
    assert {c["severity"] for c in out if not c["ok"]} <= {"warn", "human"}
    assert any(c["name"] == "images" and c["severity"] == "warn" for c in out)


def test_doc_script_grounded_keeps_storyteller_style_and_returns_anchors(monkeypatch):
    import scriptgen
    prompts = []

    def fake(prompt, *a, **k):
        prompts.append(prompt)
        if "Plan a" in prompt:
            return {"title": "T", "description": "d", "tags": [], "anchors": ["Hamelin", "Pied Piper", "Koppenberg"],
                    "chapters": [{"title": f"c{i}", "summary": "s"} for i in range(8)]}
        return {"lines": [{"text": "word " * 20, "visual": "Hamelin"} for _ in range(6)]}

    monkeypatch.setattr(scriptgen, "_chat", fake)
    data = scriptgen.doc_script("The Pied Piper", grounded="ARTICLE: the town record says 1284.")
    assert data["grounded"] is True and data["anchors"] == ["Hamelin", "Pied Piper", "Koppenberg"]
    assert "ONLY" in prompts[0] and "ARTICLE: the town record says 1284." in prompts[0]
    assert "calm and practical" not in prompts[0]          # the news style is not used for stories
    assert "warm male storyteller" in prompts[0]
    assert "Hamelin" in prompts[1] and "Invent no" in prompts[1]


def test_doc_script_without_source_is_not_grounded(monkeypatch):
    import scriptgen

    def fake(prompt, *a, **k):
        if "Plan a" in prompt:
            return {"title": "T", "description": "d", "tags": [], "chapters": [{"title": f"c{i}", "summary": "s"} for i in range(8)]}
        return {"lines": [{"text": "word " * 20, "visual": "x"} for _ in range(6)]}

    monkeypatch.setattr(scriptgen, "_chat", fake)
    assert scriptgen.doc_script("T")["grounded"] is False


def test_short_needs_four_images_and_ungrounded_only_warns():
    ok = reviewer.footage_checks({"format": "short", "grounded": False, "footage": {"scenes": 11, "unique": 4, "missing": 0}})
    assert ok[0]["ok"]
    assert [c for c in ok if c["name"] == "grounded"][0]["severity"] == "warn"
    assert not reviewer.footage_checks({"format": "short", "footage": {"scenes": 11, "unique": 3, "missing": 0}})[0]["ok"]


def test_short_script_accepts_a_source_and_returns_anchors(monkeypatch):
    import scriptgen
    seen = []

    def fake(prompt, *a, **k):
        seen.append(prompt)
        return {"title": "T", "description": "d", "tags": [], "anchors": ["Minotaur", "Knossos"],
                "lines": [{"text": "word " * 10, "visual": "Knossos palace"} for _ in range(12)]}

    monkeypatch.setattr(scriptgen, "_chat", fake)
    d = scriptgen.script("Minotaur", grounded="ARTICLE: Knossos had a palace.")
    assert d["grounded"] is True and d["anchors"] == ["Minotaur", "Knossos"]
    assert "ONLY" in seen[0] and "Knossos had a palace" in seen[0]


def test_judge_filters_candidates_before_download(monkeypatch, tmp_path):
    import config
    monkeypatch.setattr(config, "CACHE", tmp_path)
    monkeypatch.setattr(footage.time, "sleep", lambda s: None)
    pages = {str(i): {"title": f"File:{t}", "imageinfo": [{"thumburl": f"http://x/{i}.jpg", "extmetadata": {
        "LicenseShortName": {"value": "Public domain"}, "Categories": {"value": ""}}}]}
        for i, t in enumerate(["Delphi temple.jpg", "Apollo 11 launch Delphi.jpg"])}

    class R:
        status_code = 200
        ok = True
        content = b"img"
        def raise_for_status(self): pass
        def json(self): return {"query": {"pages": pages}}

    monkeypatch.setattr(footage.requests, "get", lambda *a, **k: R())
    got = footage.images_for("Delphi", ["Delphi"], 5, judge=lambda titles: [t for t in titles if "Apollo 11" not in t])
    assert [c.split(" (")[0] for _, c in got] == ["Delphi temple.jpg"]


def test_support_filter_drops_unsupported_lines_and_keeps_chapters(monkeypatch):
    import scriptgen
    lines = [{"text": f"line {i}", "visual": "v"} for i in range(10)]
    chapters = [{"title": "a", "start_line": 0}, {"title": "b", "start_line": 5}]
    monkeypatch.setattr(scriptgen, "_review_chat", lambda p, *a, **k: {"unsupported": [2, 6]})
    out, ch = scriptgen.support_filter(lines, chapters, "SOURCES")
    assert [l["text"] for l in out] == ["line 0", "line 1", "line 3", "line 4", "line 5", "line 7", "line 8", "line 9"]
    assert [c["start_line"] for c in ch] == [0, 4]


def test_support_filter_ignores_a_judge_that_condemns_most_of_the_script(monkeypatch):
    import scriptgen
    lines = [{"text": f"line {i}", "visual": "v"} for i in range(10)]
    monkeypatch.setattr(scriptgen, "_review_chat", lambda p, *a, **k: {"unsupported": list(range(8))})
    out, _ = scriptgen.support_filter(lines, [{"title": "a", "start_line": 0}], "S")
    assert len(out) == 10


def test_anchor_terms_add_topic_and_article_names():
    import run
    got = run.anchor_terms("The Pied Piper of Hamelin", ["Town Gate", "Hamelin"], "Pied Piper of Hamelin")
    assert "Hamelin" in got and "Pied Piper" in got and got.count("Hamelin") == 1 and "The" not in got


def test_when_real_pictures_run_out_illustrations_are_drawn_up_to_the_limit_then_pictures_repeat(monkeypatch):
    a = Path("a.jpg")
    _fake_images(monkeypatch, {"Hamelin church": [(a, "A")]})
    drawn = []

    def art(line):
        drawn.append(line["text"])
        return Path(f"art{len(drawn)}.jpg"), "Illustration: AI-generated"

    lines = [{"visual": "Hamelin church", "text": "t0"}] + [{"visual": "none", "text": f"t{i}"} for i in range(1, 6)]
    clips, credits, stats = footage.scene_images(lines, "Pied Piper", ["Pied Piper"], art=art, art_limit=3)
    assert clips[0] == a and clips[1:4] == [Path("art1.jpg"), Path("art2.jpg"), Path("art3.jpg")]
    assert drawn == ["t1", "t2", "t3"] and stats["drawn"] == 3 and stats["unique"] == 4 and all(clips)  # then the limit: repeats, never blank
    assert credits == ["A", "Illustration: AI-generated"]  # one credit line, not one per drawing


def test_no_art_function_means_no_drawing(monkeypatch):
    _fake_images(monkeypatch, {})
    clips, _, stats = footage.scene_images([{"visual": "x", "text": "t"}], "T", [], art=None, art_limit=5)
    assert clips == [None] and stats["drawn"] == 0


def _lines(n=10):
    return [{"text": f"line {i}", "visual": f"v{i}"} for i in range(n)]


def test_verify_and_revise_rewrites_flagged_lines_from_the_sources_and_checks_again(monkeypatch):
    import scriptgen
    judged = []

    def judge(prompt, *a, **k):
        judged.append(prompt)
        return {"unsupported": [{"n": 2, "why": "invented guide"}]} if len(judged) == 1 else {"unsupported": []}

    monkeypatch.setattr(scriptgen, "_review_chat", judge)
    monkeypatch.setattr(scriptgen, "_script_chat", lambda p, *a, **k: {"lines": [{"n": 2, "text": "rewritten from the source", "visual": "Delphi"}]})
    out, ch = scriptgen.verify_and_revise(_lines(), [{"title": "a", "start_line": 0}], "SOURCES")
    assert out[2] == {"text": "rewritten from the source", "visual": "Delphi"} and len(out) == 10 and len(judged) == 2


def test_verify_and_revise_drops_a_line_when_no_source_fact_fits_and_when_it_stays_flagged(monkeypatch):
    import scriptgen
    monkeypatch.setattr(scriptgen, "_review_chat", lambda p, *a, **k: {"unsupported": [{"n": 1, "why": "x"}]} if "line 1" in p else {"unsupported": []})
    monkeypatch.setattr(scriptgen, "_script_chat", lambda p, *a, **k: {"lines": [{"n": 1, "text": "", "visual": ""}]})
    out, ch = scriptgen.verify_and_revise(_lines(), [{"title": "a", "start_line": 0}, {"title": "b", "start_line": 5}], "S")
    assert [l["text"] for l in out] == [f"line {i}" for i in (0, 2, 3, 4, 5, 6, 7, 8, 9)] and [c["start_line"] for c in ch] == [0, 4]
    monkeypatch.setattr(scriptgen, "_review_chat", lambda p, *a, **k: {"unsupported": [{"n": 1, "why": "x"}]} if "line 1" in p else {"unsupported": []})
    monkeypatch.setattr(scriptgen, "_script_chat", lambda p, *a, **k: {"lines": [{"n": 1, "text": "line 1", "visual": "v"}]})  # the writer keeps the same flagged line
    out, _ = scriptgen.verify_and_revise(_lines(), [{"title": "a", "start_line": 0}], "S")
    assert "line 1" not in [l["text"] for l in out]


def test_verify_and_revise_refuses_a_script_the_source_mostly_does_not_support(monkeypatch):
    import pytest
    import scriptgen
    monkeypatch.setattr(scriptgen, "_review_chat", lambda p, *a, **k: {"unsupported": [{"n": i, "why": "x"} for i in range(6)]})
    with pytest.raises(ValueError, match="do not support"):
        scriptgen.verify_and_revise(_lines(), [{"title": "a", "start_line": 0}], "S")


def test_verify_and_revise_refuses_to_pass_a_script_it_could_not_check(monkeypatch):
    import pytest
    import scriptgen

    def boom(*a, **k):
        raise RuntimeError("no model")

    monkeypatch.setattr(scriptgen, "_review_chat", boom)
    with pytest.raises(ValueError, match="could not be fact-checked"):
        scriptgen.verify_and_revise(_lines(), [{"title": "a", "start_line": 0}], "S")


def test_a_drawn_scene_about_writing_is_told_to_show_no_legible_text():
    import aiart
    texty = aiart.prompt_for("The Rattenfaenger house carries an inscription about the children.", "Rattenfaengerhaus inscription", "Pied Piper", False)
    plain = aiart.prompt_for("A piper walks through the narrow streets of the town.", "Hamelin street", "Pied Piper", False)
    assert "no legible writing" in texty.lower() and "no legible writing" not in plain.lower()
    assert aiart.prompt_for("An old map of the colony.", "Roanoke map", "Roanoke", True).lower().count("no legible writing") == 1


class _Resp:
    def __init__(self, status, body=None, retry_after=None):
        self.status_code, self._body = status, body or {}
        self.headers = {"Retry-After": str(retry_after)} if retry_after is not None else {}

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"{self.status_code}")

    def json(self):
        return self._body


def test_wikipedia_waits_out_a_429_as_told_and_then_gets_the_answer(monkeypatch):
    import wikipedia
    answers = [_Resp(429, retry_after=7), _Resp(429, retry_after=500), _Resp(200, {"ok": 1})]
    slept = []
    monkeypatch.setattr(wikipedia.requests, "get", lambda *a, **k: answers.pop(0))
    monkeypatch.setattr(wikipedia.time, "sleep", lambda s: slept.append(s))
    assert wikipedia._api({"action": "query"}) == {"ok": 1}
    assert slept[0] == 7 and max(slept) <= wikipedia.MAX_WAIT  # a huge Retry-After is not obeyed blindly


def test_wikipedia_gives_up_after_a_few_429s_and_the_callers_see_a_request_error(monkeypatch):
    import pytest
    import requests
    import wikipedia
    monkeypatch.setattr(wikipedia.requests, "get", lambda *a, **k: _Resp(429, retry_after=1))
    monkeypatch.setattr(wikipedia.time, "sleep", lambda s: None)
    with pytest.raises(requests.RequestException):
        wikipedia._api({"action": "query"})
    assert wikipedia.facts_for("Apollo 13") is None  # unchanged: callers treat a failed read as no article (and retry, see topicrank.read_article)


def test_wikipedia_requests_are_spaced_and_identify_the_bot_with_a_contact(monkeypatch):
    import wikipedia
    times, now = [], [1000.0]
    monkeypatch.setattr(wikipedia.requests, "get", lambda *a, **k: times.append(now[0]) or _Resp(200, {}))
    monkeypatch.setattr(wikipedia.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(wikipedia.time, "sleep", lambda s: now.__setitem__(0, now[0] + s))
    wikipedia._last_call[0] = 0.0
    for _ in range(3):
        wikipedia._api({"action": "query"})
    assert all(b - a >= wikipedia.MIN_GAP - 1e-9 for a, b in zip(times, times[1:]))
    assert "http" in wikipedia.UA["User-Agent"] or "@" in wikipedia.UA["User-Agent"]


def test_search_terms_keep_accented_letters_in_names():
    import wikipedia
    assert wikipedia._terms("Göbekli Tepe") == "Göbekli Tepe"
    assert wikipedia._terms("The Çatalhöyük settlement") == "Çatalhöyük settlement"
    assert wikipedia._terms("Sagrada Família") == "Sagrada Família"
    assert wikipedia._terms("The Mystery of the Voynich manuscript") == "Voynich manuscript"  # the generic words are still dropped
