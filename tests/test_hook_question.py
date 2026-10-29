"""A Short's hook asks an OPEN question (29 Oct 2026). The remade Cambyses Short opened "Did a sandstorm really swallow 50,000 soldiers?": a yes/no question that already holds the
explanation and never says whose soldiers they were. The owner preferred the earlier hook, "Where did an army of fifty thousand Persian soldiers go?": it names who the story is about
and keeps the answer back. The prompt now asks for that and the reviewer warns (never fails) about a yes/no hook. The rule is the studio's own taste, not a YouTube rule."""
import pytest

import reviewer
import scriptgen


def check(first, rest=("Only the desert knows, and it has never said.", "Subscribe for the next story.")):
    meta = {"format": "short", "description": "A hook first.", "lines": [{"text": t} for t in (first, "Around 525 BC the king sent them out.", *rest)]}
    return {c["name"]: c for c in reviewer.generator_checks(meta, {"duration": 45})}["short_hook_open"]


@pytest.mark.parametrize("hook", ["Did a sandstorm really swallow 50,000 soldiers?", "Is La Llorona's weeping really a silenced people's voice?",
                                  "Was Hong Gildong a real man?", "Can a book nobody reads still hold a secret?", "Does the Voynich manuscript say anything at all?"])
def test_a_yes_or_no_hook_gets_a_warning(hook):
    got = check(hook)
    assert not got["ok"] and got["severity"] == "warn" and "yes/no" in got["detail"]


@pytest.mark.parametrize("hook", ["Where did an army of fifty thousand Persian soldiers go?", "What kind of dragon would a king wish to become?",
                                  "Why is a Utah cattle ranch named after a Navajo legend?", "No one has ever found the army that vanished.",
                                  "Everyone knows this race. But do we know its lesson?", "Who leads lost travelers astray in the mountains after dark?"])
def test_an_open_question_or_a_statement_is_fine(hook):
    assert check(hook)["ok"]


def test_a_documentary_gets_no_hook_question_check():
    meta = {"format": "doc", "description": "d", "lines": [{"text": "Did it happen?"}] * 3}
    assert "short_hook_open" not in {c["name"] for c in reviewer.generator_checks(meta, {"duration": 400})}


def test_the_writer_is_asked_for_an_open_question_that_names_the_subject_and_keeps_the_answer_back():
    low = scriptgen.short_prompt("A topic").lower()
    assert "never as a yes/no question" in low and "who, what, where, why or how" in low and "keep the explanation out of the hook" in low
    assert "loop" not in low  # still never asks for loops
