import keywords
import subtitles
import tts


def kinds(sentence):
    return keywords.kinds(sentence.split())


def test_names_numbers_and_tension_words():
    assert kinds("In 1453 the city of Constantinople fell") == [None, "number", None, None, None, "name", None]
    k = kinds("The children vanished, and a secret remained")
    assert k[2] == "tension" and k[5] == "tension" and k[0] is None


def test_first_word_of_a_sentence_is_not_a_name_but_later_capitals_are():
    k = kinds("Hamelin was quiet. Weser flowed by Hamelin")
    assert k[0] is None  # sentence start
    assert k[3] is None  # the start of the second sentence
    assert k[-1] == "name"


def test_function_words_and_short_tokens_never_coloured():
    assert kinds("I saw It In A The") == [None] * 6


def test_punctuation_and_case_are_ignored_for_lookup():
    assert keywords.kinds(["VANISHED!"]) == ["tension"]
    assert keywords.kinds(["“Secret,”"]) == ["tension"]
    assert keywords.kinds(["40,000", "1453."]) == ["number", "number"]


def test_limit_keeps_the_first_n_coloured():
    got = keywords.limit(["name", "number", "tension", None], 2)
    assert got == ["name", "number", None, None]
    assert keywords.limit([None, None], 2) == [None, None]


def test_colors_are_distinct_ass_values():
    assert len({keywords.color(k) for k in ("name", "number", "tension")}) == 3
    assert all(keywords.color(k).startswith("&H") for k in ("name", "number", "tension"))


def test_colorize_wraps_only_keywords_and_keeps_line_breaks():
    out = keywords.colorize("In 1453 the city of Constantinople\nfell in secret")
    assert "{\\c" + keywords.color("number") + "}1453{\\r}" in out
    assert "{\\c" + keywords.color("name") + "}Constantinople{\\r}" in out
    assert out.count("\n") == 1 and "{\\c" + keywords.color("tension") + "}secret{\\r}" in out
    assert keywords.colorize("a calm quiet day") == "a calm quiet day"


W = [(0.0, 0.5, "Why", 0), (0.5, 1.0, "did", 0), (1.0, 1.5, "they", 0),
     (1.9, 2.3, "Hamelin", 1), (2.3, 2.8, "vanished", 1), (2.8, 3.2, "in", 1), (3.2, 3.6, "1284", 1)]


def test_rich_captions_colour_keywords_not_the_spoken_word():
    ass = tts._ass(W, motion=2)
    caps = [l for l in ass.splitlines() if ",Cap," in l]
    assert len(caps) == 4
    first = caps[0]  # chunk "Hamelin vanished in", active word Hamelin
    assert "HAMELIN" in first and keywords.color("tension") in first
    assert tts.ACCENT not in "".join(caps)  # no more one-colour karaoke
    assert all("\\fscx115" in c for c in caps)  # the spoken word still pops


def test_rich_captions_bottom_and_top_zones():
    bottom = tts._ass(W, motion=2, pos="bottom")
    top = tts._ass(W, motion=2, pos="top")
    cap = lambda a: [l for l in a.splitlines() if l.startswith("Style: Cap")][0].split(",")
    assert cap(bottom)[10] == "2" and int(cap(bottom)[13]) >= 300  # bottom centre, clear of the player's own text
    assert cap(top)[10] == "8"
    hook = [l for l in top.splitlines() if l.startswith("Style: Hook")][0].split(",")
    assert hook[10] == "8"  # the hook title stays at the top in both layouts


def test_at_most_two_words_coloured_in_a_chunk():
    words = [(0.0, 0.3, "Vanished", 1), (0.3, 0.6, "secret", 1), (0.6, 0.9, "death", 1), (0.9, 1.2, "hmm", 0)]
    ass = tts._ass(words, motion=2)
    line = [l for l in ass.splitlines() if ",Cap," in l][0]
    assert line.count("\\c&H") <= 2


def test_documentary_subtitles_colour_keywords_and_respect_position():
    cues = [{"start": 0.0, "end": 3.0, "text": "In 1453 the city of Constantinople\nfell in secret"}]
    bottom = subtitles.to_ass(cues, (1920, 1080))
    assert "{\\c" + keywords.color("name") + "}Constantinople{\\r}" in bottom and "\\N" in bottom
    style = [l for l in bottom.splitlines() if l.startswith("Style: Sub")][0].split(",")
    assert style[10] == "2"
    top = subtitles.to_ass(cues, (1920, 1080), pos="top")
    assert [l for l in top.splitlines() if l.startswith("Style: Sub")][0].split(",")[10] == "8"
