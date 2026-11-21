"""The documentary fact-check (20 Nov 2026): a long script is checked in parts, a busy judge does not throw the draft away, and rewrites keep the script's line length."""
import pytest

import scriptgen


def test_a_long_script_is_checked_in_parts_with_true_line_numbers(monkeypatch):
    asked = []

    def judge(prompt, avoid=None):
        text = str(prompt)
        asked.append(text)
        return {"unsupported": [{"n": 31, "why": "not in SOURCES"}, {"n": 5, "why": "outside this part"}]} if "lines 30 to 59" in text else {"unsupported": []}

    monkeypatch.setattr(scriptgen, "_review_chat", judge)
    lines = [{"text": f"Line {i} says something."} for i in range(75)]
    assert scriptgen.unsupported(lines, "SRC") == {31: "not in SOURCES"}  # a number outside the part it was asked about is ignored
    assert len(asked) == 3 and "lines 0 to 29 of a 75-line script" in asked[0] and "74: Line 74" in asked[2]


def test_busy_judges_make_the_same_draft_wait_and_be_checked_again(monkeypatch):
    calls, waits = [], []

    def verify(lines, chapters, sources):
        calls.append(list(lines))
        if len(calls) < 3:
            raise ValueError("the script could not be fact-checked (ModelUnavailable)")
        return lines, chapters

    monkeypatch.setattr(scriptgen, "verify_and_revise", verify)
    draft = [{"text": "a"}, {"text": "b"}]
    assert scriptgen.checked(draft, [], "SRC", sleep=waits.append) == (draft, [])
    assert waits == list(scriptgen.JUDGE_WAITS) and all(c == draft for c in calls)  # the same draft each time, never rewritten


def test_the_error_stands_after_the_waits_and_other_errors_are_not_waited_for(monkeypatch):
    waits = []
    monkeypatch.setattr(scriptgen, "verify_and_revise", lambda *a: (_ for _ in ()).throw(ValueError("the script could not be fact-checked (ModelUnavailable)")))
    with pytest.raises(ValueError, match="could not be fact-checked"):
        scriptgen.checked([{"text": "a"}], [], "SRC", sleep=waits.append)
    assert len(waits) == len(scriptgen.JUDGE_WAITS)  # never passed on unchecked
    monkeypatch.setattr(scriptgen, "verify_and_revise", lambda *a: (_ for _ in ()).throw(ValueError("the sources do not support 60 of 90 lines")))
    with pytest.raises(ValueError, match="do not support"):
        scriptgen.checked([{"text": "a"}], [], "SRC", sleep=waits.append)
    assert len(waits) == len(scriptgen.JUDGE_WAITS)  # a script the sources do not support is not waited for: the writer is asked again


def test_a_rewritten_line_keeps_the_script_s_own_length():
    assert scriptgen.rewrite_words([{"text": " ".join(["w"] * 35)}] * 9) == (31, 39)
    assert scriptgen.rewrite_words([{"text": " ".join(["w"] * 12)}] * 9) == (16, 24)  # Shorts and shorter films as before


def test_the_behaviour_check_holds_and_fails_on_each_broken_rule(monkeypatch):
    import agenteval

    ok, why = agenteval.case_busy_judges_never_discard_a_draft_and_never_pass_it_unchecked()
    assert ok, why
    real_checked = scriptgen.checked

    def throws_draft_away(lines, chapters, sources, sleep=None):  # mutation: the first busy answer discards the draft (the old behaviour)
        return scriptgen.verify_and_revise(lines, chapters, sources)

    def passes_unchecked(lines, chapters, sources, sleep=None):  # mutation: after the waits the draft goes on unchecked
        try:
            return real_checked(lines, chapters, sources, sleep=sleep)
        except ValueError:
            return lines, chapters

    for name, value in (("checked", throws_draft_away), ("checked", passes_unchecked), ("CHECK_CHUNK", 10_000)):  # the last: one request for the whole script again
        with monkeypatch.context() as m:
            m.setattr(scriptgen, name, value)
            assert not agenteval.case_busy_judges_never_discard_a_draft_and_never_pass_it_unchecked()[0], name
