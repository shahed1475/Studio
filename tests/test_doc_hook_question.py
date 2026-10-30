"""YouTube's own hook advice (blog, retained in docs/studio/VIDEO_CRAFT_RESEARCH_2026-10-29.md): start with a question and tell viewers within five seconds what they will see. The owner (30 Oct 2026):
curiosity from the first second. The film's first two narration lines (about five seconds) must hold the question, and the writer is told so. A warning, never a block."""
import reviewer
import scriptgen

PROBE = {"duration": 500.0}


def meta(*lines, kind="default"):
    return {"format": "doc", "kind": kind, "description": "A hook.", "lines": [{"text": t} for t in lines]}


def row(m):
    return next((r for r in reviewer.generator_checks(m, PROBE) if r["name"] == "hook_question"), None)


def test_a_film_with_no_question_in_its_first_two_lines_is_warned():
    r = row(meta("Close to modern Mexico City, an ancient city burned.", "Its people left behind stone and ash.", "So who set the fire?"))
    assert r and not r["ok"] and r["severity"] == "warn" and "question" in r["detail"]


def test_a_question_in_line_one_or_two_passes():
    assert row(meta("Where did fifty thousand soldiers go?", "The legend says a sandstorm."))["ok"]
    assert row(meta("In 525 BC an army set out.", "Did a single man come home?"))["ok"]
    assert row(meta("A calm start. And a question: why did the city burn?", "x"))["ok"]


def test_a_short_is_judged_by_its_own_rules_not_this_one():
    short = {"format": "short", "description": "A hook.", "lines": [{"text": "The army vanished."}]}
    assert row(short) is None


def test_the_writer_is_told_to_put_the_question_and_the_promise_in_the_first_two_lines():
    s = scriptgen.DOC_STRUCTURE
    assert "first two lines" in s and "question mark" in s and "by the end" in s
