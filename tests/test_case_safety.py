"""An unsolved crime or case is a real event with real victims and sometimes real, living suspects. YouTube's own pages (read 30 Oct 2026) forbid shock violence, forbid content that
realistically simulates deceased or abused individuals describing their death, and allow documentary context only when it appears in the video's own images or audio. So a case film: documented
facts only with attribution, nobody named as guilty beyond the official findings, nothing graphic, no identifiable person in the pictures, and the documentary purpose said in the narration."""
import inspect

import aiart
import reviewer
import scriptgen

CASE = {"format": "doc", "kind": "case", "description": "A hook.", "topic": "The Zodiac Killer unsolved murders"}


def meta(*lines, **k):
    return {**CASE, "lines": [{"text": t} for t in lines], **k}


def row(m, name):
    return next((r for r in reviewer.generator_checks(m, {"duration": 500.0}) if r["name"] == name), None)


def test_the_writer_gets_the_case_rules_for_a_case_topic_and_only_for_one():
    r = scriptgen.case_rules("The Zodiac Killer unsolved murders")
    assert r == scriptgen.CASE_RULES and scriptgen.case_rules("The Lost Army of Cambyses") == "" and scriptgen.case_rules("Cleopatra queen") == ""
    low = r.lower()
    for need in ("documented", "attribute", "never call a named", "court", "graphic", "documentary account", "victim"):
        assert need in low, need
    assert "case_rules(topic)" in inspect.getsource(scriptgen)  # the documentary writer adds them to its shared rules


def test_a_case_film_that_calls_a_named_person_the_killer_without_attribution_is_warned():
    bad = row(meta("Where did he go?", "Investigators looked for him.", "John Smith was the killer and everyone knew it."), "case_accusation")
    assert bad and not bad["ok"] and bad["severity"] == "warn" and "line 3" in bad["detail"]
    ok = row(meta("Where did he go?", "Police said John Smith was the killer, but he was never charged.", "A court found him not guilty."), "case_accusation")
    assert ok and ok["ok"]


def test_a_case_film_with_graphic_detail_is_warned_and_one_without_is_not():
    bad = row(meta("Why?", "The corpse was mutilated and the scene was gory."), "case_graphic")
    assert bad and not bad["ok"] and "mutilated" in bad["detail"]
    assert row(meta("Why?", "The victim was found in the river in March."), "case_graphic")["ok"]


def test_a_case_film_must_say_in_its_narration_that_it_is_a_documentary_account_of_a_real_case():
    assert not row(meta("Why did he vanish?", "The river was cold."), "case_context")["ok"]
    assert row(meta("Why did he vanish?", "This documentary account sticks to the court records."), "case_context")["ok"]
    assert row(meta("What do the investigators' files say?", "x"), "case_context")["ok"]


def test_other_kinds_of_film_are_not_asked_for_any_of_it():
    other = {"format": "doc", "kind": "person", "description": "A hook.", "lines": [{"text": "A king was the killer of his brother and the corpse was mutilated."}]}
    assert [row(other, n) for n in ("case_accusation", "case_graphic", "case_context")] == [None, None, None]


def test_the_pictures_of_a_case_show_no_identifiable_person_and_other_prompts_are_unchanged():
    plain = aiart.prompt_for("He walked home.", "a street", "The Zodiac Killer", False, "photo")
    case = aiart.prompt_for("He walked home.", "a street", "The Zodiac Killer", False, "photo", case=True)
    assert case.startswith(plain) and "identifiable" in case and "violent" in case
    assert aiart.prompt_for("He walked home.", "a street", "The Zodiac Killer", False, "photo", case=False) == plain  # a cached picture of any other video keeps its key
