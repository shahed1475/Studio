"""A documentary script well under the owner's length gets more lines in its shortest chapters before the fact-check (scriptgen.extend_to_length, 20 Nov 2026)."""
import pytest
import scriptgen


def script(per_chapter_words):
    lines, chapters = [], []
    for n, words in enumerate(per_chapter_words):
        chapters.append({"title": f"C{n}", "start_line": len(lines)})
        lines += [{"text": " ".join(["word"] * words), "visual": "v"} for _ in range(3)]
    return lines, chapters


def test_a_short_script_gets_lines_in_its_shortest_chapters_and_chapter_starts_move(monkeypatch):
    # 23 Nov 2026: this test used three chapters and expected all three to grow; the closing chapter growing is what ended the Mary Celeste film on a stray
    # background fact, so the hook and closing chapters are now never extended and the test uses five chapters (three of them in the middle).
    monkeypatch.setattr(scriptgen, "min_doc_words", lambda: 1000)
    lines, chapters = script([40, 10, 60, 5, 20])  # 405 words against 900 needed
    asked = []

    def chat(prompt):
        asked.append(prompt)
        return {"lines": [{"text": " ".join(["new"] * 35), "visual": "x"} for _ in range(4)]}

    out, ch = scriptgen.extend_to_length(lines, chapters, {"title": "T"}, "topic", "rules", "calm", chat=chat)
    assert [str(p).split("Chapter '")[1][:2] for p in asked] == ["C3", "C1", "C2"]  # the shortest middle chapter first, then the next shortest
    assert [c["start_line"] for c in ch] == [0, 3, 10, 17, 24] and len(out) == 27
    assert out[6]["text"].startswith("new") and out[3] == lines[3]  # added at the end of their own chapter, nothing rewritten
    assert out[:3] == lines[:3] and out[-3:] == lines[-3:]  # the opening and the ending exactly as written


def test_the_hook_and_closing_chapters_are_never_extended_but_a_two_chapter_script_may_grow(monkeypatch):
    monkeypatch.setattr(scriptgen, "min_doc_words", lambda: 1000)
    asked = []

    def chat(prompt):
        asked.append(str(prompt).split("Chapter '")[1][:2])
        return {"lines": [{"text": " ".join(["new"] * 35), "visual": "x"} for _ in range(4)]}

    lines, chapters = script([5, 40, 5])  # the first and last are the shortest: still only the middle grows
    out, _ = scriptgen.extend_to_length(lines, chapters, {"title": "T"}, "topic", "rules", "calm", chat=chat)
    assert asked == ["C1"] and out[-1] == lines[-1] and out[:3] == lines[:3]
    asked.clear()
    lines, chapters = script([5, 40])  # no middle: the shorter chapter may grow, as before
    scriptgen.extend_to_length(lines, chapters, {"title": "T"}, "topic", "rules", "calm", chat=chat)
    assert asked[0] == "C0"


def test_a_long_line_is_split_at_whole_sentences_and_never_inside_one(monkeypatch):
    monkeypatch.setattr(scriptgen, "LINE_WORDS_MAX", 44)
    a = "Captain James H. Winchester bought the ship from the creditors of Richard W. Haines in New York that autumn."  # 19 words, initials inside
    b = " ".join(["Word"] + ["word"] * 23) + "."  # a sentence of 24 words
    c = "Doyle named the captain J. W. Tibbs and set the voyage from Boston to Lisbon in his story."  # 18 words
    long_one = " ".join(["long"] * 50) + "."
    lines = [{"text": "Short opening line here.", "visual": "v0"}, {"text": f"{a} {b} {c}", "visual": "ship"}, {"text": long_one, "visual": "sea"}]
    out, ch = scriptgen.split_long_lines(lines, [{"title": "A", "start_line": 0}, {"title": "B", "start_line": 2}])
    assert [l["text"] for l in out] == ["Short opening line here.", f"{a} {b}", c, long_one]  # 19 + 24 = 43 | 18; the 50-word sentence stays whole
    assert [l["visual"] for l in out] == ["v0", "ship", "ship", "sea"] and ch == [{"title": "A", "start_line": 0}, {"title": "B", "start_line": 3}]
    assert " ".join(l["text"] for l in out) == " ".join(l["text"] for l in lines)  # not a word changed or lost
    assert scriptgen.sentences("He met St. John and Mr. Lee. Then he left!") == ["He met St. John and Mr. Lee.", "Then he left!"]


def test_the_writer_never_returns_a_line_over_the_long_film_limit(monkeypatch):
    monkeypatch.setattr(scriptgen, "LINE_WORDS_MAX", 44)
    monkeypatch.setattr(scriptgen, "min_doc_words", lambda: 10)
    import itertools

    count = itertools.count()

    def two_sentences():
        k = next(count)
        return " ".join(f"a{k}x{j}" for j in range(30)) + ". " + " ".join(f"B{k}y{j}" for j in range(30)) + "."

    def chat(prompt):
        if "Plan a" in str(prompt):
            return {"title": "T", "description": "d", "tags": [], "anchors": [], "chapters": [{"title": f"C{n}", "summary": "s"} for n in range(6)]}
        return {"lines": [{"text": two_sentences(), "visual": "v"} for _ in range(4)]}

    monkeypatch.setattr(scriptgen, "_script_chat", chat)
    monkeypatch.setattr(scriptgen, "checked", lambda lines, chapters, sources, sleep=None: (lines, chapters))
    out = scriptgen.doc_script("Topic", grounded="SRC")
    assert max(len(l["text"].split()) for l in out["lines"]) <= 44 and len(out["lines"]) == 48  # 24 lines of 60 words, each cut into two whole sentences


def test_a_script_long_enough_or_a_writer_with_nothing_new_leaves_the_script_as_it_was(monkeypatch):
    monkeypatch.setattr(scriptgen, "min_doc_words", lambda: 100)
    lines, chapters = script([40, 10, 60])
    assert scriptgen.extend_to_length(lines, chapters, {}, "t", "r", "s", chat=lambda p: 1 / 0) == (lines, chapters)
    monkeypatch.setattr(scriptgen, "min_doc_words", lambda: 5000)
    assert scriptgen.extend_to_length(lines, chapters, {}, "t", "r", "s", chat=lambda p: {"lines": []}) == (lines, chapters)
    calls = []
    scriptgen.extend_to_length(lines, chapters, {}, "t", "r", "s", chat=lambda p: calls.append(p) or {"lines": []})
    assert len(calls) <= scriptgen.MAX_EXTENSIONS


def _writer(per_line_words):
    """A fake writer: an outline with 13 chapters, then chapters of 4 lines of `per_line_words` words, then extensions of 4 lines of 35 words. Every line has words of
    its own (a writer that repeats itself would be cut by the retold-line rule)."""
    import itertools

    count = itertools.count()

    def line(n):
        k = next(count)
        return {"text": " ".join(f"x{k}y{j}" for j in range(n)) + ".", "visual": "v"}  # a sentence, as a real writer gives

    def chat(prompt):
        text = str(prompt)
        if "Plan a" in text:
            return {"title": "T", "description": "d", "tags": [], "anchors": [], "chapters": [{"title": f"C{n}", "summary": "s"} for n in range(13)]}
        if "is too short" in text:
            return {"lines": [line(35) for _ in range(4)]}
        return {"lines": [line(per_line_words) for _ in range(4)]}
    return chat


def test_a_checked_script_under_the_owners_length_grows_again_and_the_new_lines_are_checked(monkeypatch):
    monkeypatch.setattr(scriptgen, "min_doc_words", lambda: 2000)
    monkeypatch.setattr(scriptgen, "_script_chat", _writer(20))  # 13 chapters x 4 lines x 20 words = 1,040 words
    checks = []

    def check(lines, chapters, sources, sleep=None):  # a judge that drops a fifth of every script it sees, the way the real check drops lines
        checks.append(sum(len(l["text"].split()) for l in lines))
        return scriptgen._drop_lines(lines, chapters, {i for i in range(len(lines)) if i % 5 == 4})

    monkeypatch.setattr(scriptgen, "checked", check)
    out = scriptgen.doc_script("Topic", grounded="SRC")
    words = sum(len(l["text"].split()) for l in out["lines"])
    assert len(checks) >= 2  # the grown script went through the check again
    assert words > checks[0] * 0.8  # longer than what one check alone left
    assert words >= 2000  # and it reaches the owner's length although every check removes a fifth (the growth aims above the target by what the check removed)


def test_the_growth_stops_when_the_writer_has_nothing_more_and_is_bounded(monkeypatch):
    monkeypatch.setattr(scriptgen, "min_doc_words", lambda: 100_000)
    base = _writer(20)
    monkeypatch.setattr(scriptgen, "_script_chat", lambda p: {"lines": []} if "is too short" in str(p) else base(p))
    checks = []
    monkeypatch.setattr(scriptgen, "checked", lambda lines, chapters, sources, sleep=None: checks.append(1) or (lines, chapters))
    scriptgen.doc_script("Topic", grounded="SRC")
    assert len(checks) == 1  # nothing new from the sources: no second check, the film stays as long as its sources allow
    monkeypatch.setattr(scriptgen, "_script_chat", _writer(20))
    checks.clear()
    scriptgen.doc_script("Topic", grounded="SRC")
    assert len(checks) <= 1 + scriptgen.LENGTH_ROUNDS


def test_short_lines_of_a_long_film_are_joined_inside_their_chapter_never_across(monkeypatch):
    monkeypatch.setattr(scriptgen, "LINE_WORDS_MAX", 44)
    lines = [{"text": " ".join([f"a{i}"] * 18), "visual": f"v{i}"} for i in range(6)] + [{"text": " ".join(["b"] * 18), "visual": "vb"}]
    chapters = [{"title": "One", "start_line": 0}, {"title": "Two", "start_line": 6}]
    out, ch = scriptgen.join_short_lines(lines, chapters)
    assert [len(l["text"].split()) for l in out] == [36, 36, 36, 18] and ch == [{"title": "One", "start_line": 0}, {"title": "Two", "start_line": 3}]
    assert out[0]["visual"] == "v0" and out[0]["text"] == lines[0]["text"] + " " + lines[1]["text"]  # sentences joined, never changed; the first picture words kept
    assert sum(len(l["text"].split()) for l in out) == sum(len(l["text"].split()) for l in lines)  # not a word lost


def test_an_eight_to_ten_minute_film_keeps_its_pacing(monkeypatch):
    monkeypatch.setattr(scriptgen, "LINE_WORDS_MAX", 30)
    lines = [{"text": " ".join(["w"] * 20), "visual": "v"} for _ in range(4)]
    assert scriptgen.join_short_lines(lines, [{"title": "x", "start_line": 0}]) == (lines, [{"title": "x", "start_line": 0}])


def test_the_source_text_grows_with_the_owners_length(monkeypatch):
    monkeypatch.setattr(scriptgen, "DOC_MINUTES", (8.0, 10.0))
    assert scriptgen.source_budget() == (7000, 2)  # the old size, unchanged
    monkeypatch.setattr(scriptgen, "DOC_MINUTES", (20.0, 26.0))
    chars, n = scriptgen.source_budget()
    assert 17000 <= chars <= 24000 and n == 3


def test_a_long_documentary_is_written_from_three_articles_of_its_full_budget(monkeypatch, tmp_path):
    import run
    import wikipedia

    monkeypatch.setattr(scriptgen, "DOC_MINUTES", (20.0, 26.0))
    monkeypatch.setattr(run, "PENDING_DOC", tmp_path / "pending_doc.json")
    asked = {}

    def facts(topic, n=2, chars_each=7000):
        asked.update(n=n, chars=chars_each)
        return [{"title": f"A{i}", "url": f"https://en.wikipedia.org/wiki/A{i}", "text": "x " * 3000} for i in range(n)]

    seen = {}
    monkeypatch.setattr(wikipedia, "facts_multi", facts)
    monkeypatch.setattr(wikipedia, "is_media_work", lambda text: False)
    monkeypatch.setattr(run, "_second_sources", lambda topic, arts: (False, None))
    monkeypatch.setattr(run.scriptgen, "doc_script", lambda topic, grounded=None: seen.update(sources=grounded) or (_ for _ in ()).throw(RuntimeError("stop")))
    with pytest.raises(SystemExit):
        run._cmd_doc("Seven Sleepers")
    assert asked == {"n": 4, "chars": scriptgen.source_budget()[0]} and seen["sources"].count("[A") == 3


def test_a_line_that_retells_an_earlier_one_is_removed_inside_the_writer():
    told = "The seven young Christians walled inside the cave near Ephesus slept through two centuries of Roman persecution under Decius."
    lines = [{"text": told, "visual": "cave"}, {"text": "Bishops later argued about the meaning of the tale in sermons.", "visual": "x"},
             {"text": "A shepherd heard about the war and the harvest that autumn.", "visual": "y"},
             {"text": "Seven young Christians walled inside a cave near Ephesus slept through two centuries of persecution under Decius.", "visual": "z"}]
    out, ch = scriptgen.drop_retold(lines, [{"title": "a", "start_line": 0}, {"title": "b", "start_line": 2}])
    assert [l["visual"] for l in out] == ["cave", "x", "y"] and ch == [{"title": "a", "start_line": 0}, {"title": "b", "start_line": 2}]


def test_every_line_ends_a_sentence_notes_are_dropped_and_cut_lines_trimmed():
    lines = [{"text": "The cave was sealed. Later the youths were found by a shepherd who", "visual": "a"},      # cut mid-sentence after a whole one
             {"text": "No site empirically proven as original cave Homily draws on earlier lost Greek source", "visual": "b"},  # notes, no sentence
             {"text": "Gregory of Tours retold the legend in Latin.", "visual": "c"},
             {"text": "The feast is kept on 27 July in the Roman Martyrology, many say", "visual": "d"}]  # no whole sentence of six words or more: dropped
    out, ch = scriptgen.finish_lines(lines, [{"title": "a", "start_line": 0}, {"title": "b", "start_line": 2}])
    assert [l["text"] for l in out] == ["The cave was sealed.", "Gregory of Tours retold the legend in Latin."] or \
        [l["text"] for l in out] == ["Gregory of Tours retold the legend in Latin."]
    assert all(scriptgen._END.search(l["text"]) for l in out) and all(l["text"] in " ".join(x["text"] for x in lines) for l in out)  # only words taken away
    assert ch[-1]["title"] == "b" and ch[-1]["start_line"] == len(out) - 1
