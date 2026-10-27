import reviewer
import scriptgen

INTRO = "Before electric light, did people sleep in two pieces? " * 6
DESC = (INTRO.strip() + "\n\nSources:\nWikipedia: Polyphasic sleep (CC BY-SA 4.0), retold in our own words\n"
        "https://en.wikipedia.org/wiki/Polyphasic_sleep\nhttps://en.wikipedia.org/wiki/Sleep\n\nChapters:\n0:00 The Hour After Midnight\n0:57 One Night, Many Shapes")


def test_a_long_description_is_cut_at_a_line_break_never_inside_a_link():
    for limit in range(len(INTRO), len(DESC) - 1, 7):
        head = reviewer.description_head({"description": DESC}, limit)
        assert DESC.startswith(head) and len(head) <= limit
        assert head == "" or DESC[len(head)] == "\n", (limit, head[-30:])  # the cut is exactly at a line end


def test_the_cut_that_left_a_lone_h_after_a_link_no_longer_happens():
    desc = "x" * 551 + "\nhttps://en.wikipedia.org/wiki/Polyphasic_sleep\nhttps://en.wikipedia.org/wiki/Sleep"
    assert desc[:600].endswith("\nh")  # the old cut: a lone "h" after the first link
    head = reviewer.description_head({"description": desc})
    assert head.endswith("Polyphasic_sleep") and not head.endswith("\nh")


def test_short_descriptions_and_one_long_line_are_left_alone_or_cut_plainly():
    assert reviewer.description_head({"description": "short"}) == "short"
    assert reviewer.description_head({}) == ""
    assert reviewer.description_head({"description": "y" * 900}) == "y" * 600  # no line break to cut at


def test_the_ai_review_prompts_use_the_clean_cut(monkeypatch):
    seen = []
    monkeypatch.setattr(scriptgen, "_review_chat", lambda prompt, *a, **k: seen.append(prompt) or {"invented_facts_risk": 1, "policy_risk": 1, "misleading_title": False})
    desc = "x" * 551 + "\nhttps://en.wikipedia.org/wiki/Polyphasic_sleep\nhttps://en.wikipedia.org/wiki/Sleep"
    meta = {"title": "T", "description": desc, "lines": [{"text": "A line."}]}
    reviewer.llm_review(meta)
    reviewer.title_ok(meta, "Another title")
    assert len(seen) == 2 and all("Polyphasic_sleep\n" in p and "\nh\n" not in p for p in seen)
