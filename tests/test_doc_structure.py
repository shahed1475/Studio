"""A documentary has the owner's shape and length (30 Oct 2026): first the hook, then curiosity, then the story, and it finishes with value; 8 to 10 minutes. The writer's 50-line cap
had made the Cambyses documentary 7.6 minutes."""
import pytest

import reviewer
import scriptgen


def test_the_outline_prompt_asks_for_hook_then_curiosity_then_story_then_a_closing_chapter_of_value_in_8_to_10_minutes(monkeypatch):
    prompts = []

    def fake(prompt):
        prompts.append(prompt)
        raise RuntimeError("stop after the outline")

    monkeypatch.setattr(scriptgen, "_script_chat", fake)
    with pytest.raises(RuntimeError):
        scriptgen.doc_script("The Lost Army", grounded="Some article text.")
    low = prompts[0].lower()
    assert "8 to 10 minute" in low and "6 to 8 minute" not in low
    marks = ["chapter 1 is the hook", "chapter 2 builds curiosity", "middle chapters are the story", "last chapter gives value"]
    assert all(m in low for m in marks) and [low.index(m) for m in marks] == sorted(low.index(m) for m in marks)  # the order the owner asked for
    assert "promise" in low and "weigh" in low  # the bridge promises what the film will answer; the last chapter teaches how to weigh such a claim
    assert "no thanks, no subscribe" in low  # unchanged: it still ends on the story


def test_the_line_cap_leaves_room_for_nine_minutes_and_every_shape_stays_inside_it():
    assert 56 <= scriptgen.MAX_DOC_LINES <= 64
    for topic in ("The Pied Piper", "The Oracle of Delphi", "Lost Army of Cambyses", "Srivijaya", "The Minotaur", "Roanoke", "Atlantis", "The Bell Witch"):
        chapters, per = scriptgen.shape_for(topic)
        assert chapters * per <= scriptgen.MAX_DOC_LINES and 6 <= chapters <= 9 and 5 <= per <= 7
    assert max(c * p for c, p in (scriptgen.shape_for(t) for t in ("A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"))) >= 50  # a long shape is reachable


def doc(seconds):
    return {"format": "doc", "description": "d", "lines": [{"text": "A cold open that raises the question?"}] * 3}, {"duration": seconds}


def test_a_documentary_outside_8_to_10_minutes_gets_a_warning_and_one_inside_does_not():
    for seconds, ok in ((456, False), (540, True), (480, True), (600, True), (601, False), (900, False)):
        meta, probe = doc(seconds)
        row = {c["name"]: c for c in reviewer.generator_checks(meta, probe)}["doc_length"]
        assert row["ok"] is ok and row["severity"] == "warn", seconds
    meta, probe = doc(456)
    assert "480" in {c["name"]: c for c in reviewer.generator_checks(meta, probe)}["doc_length"]["detail"]


def test_a_short_gets_no_documentary_length_check():
    meta = {"format": "short", "description": "d", "lines": [{"text": "Why?"}] * 3}
    assert "doc_length" not in {c["name"] for c in reviewer.generator_checks(meta, {"duration": 45})}
