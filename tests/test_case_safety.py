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


# ---- review of 30 Oct 2026: Shorts, the classifier differential, thumbnails and archive pictures ----
import json

import run


def test_a_short_about_a_case_gets_the_same_writing_rules():
    assert "never call a named" in scriptgen.short_prompt("The Zodiac Killer unsolved murders", "SOURCE TEXT").lower()
    assert "never call a named" not in scriptgen.short_prompt("The Lost Army of Cambyses", "SOURCE TEXT").lower()


def test_a_topic_that_looks_harmless_but_whose_title_or_anchors_say_case_still_gets_the_rules():
    assert scriptgen.case_rules("The Isdal Woman") == ""
    assert scriptgen.case_rules("The Isdal Woman", title="The Isdal Woman: A Cold Case and a Murder Nobody Solved") == scriptgen.CASE_RULES
    assert scriptgen.case_rules("The Isdal Woman", anchors=["homicide", "detective"]) == scriptgen.CASE_RULES
    chapters = [{"title": "The victim"}, {"title": "The investigation and the suspect"}, {"title": "The arrested man"}]
    assert scriptgen.case_rules("The Isdal Woman", anchors=["homicide"], chapters=chapters) == scriptgen.CASE_RULES   # two places say it
    assert scriptgen.case_rules("The Isdal Woman", chapters=chapters) == ""                                              # chapter titles alone never decide a kind (kinds.MIN_SCORE)
    assert scriptgen.case_rules("The Lost Army of Cambyses", title="The Lost Army of Cambyses: 50,000 Men Said to Vanish", anchors=["Siwa Oasis"]) == ""


def test_the_wider_word_list_catches_everyday_crime_words():
    import kinds

    for topic in ("A victim found in the river: the investigation", "The manhunt for a fugitive", "Homicide in 1910: who was slain?"):
        assert kinds.classify({"topic": topic}) == "case", topic


def test_a_short_whose_title_turns_out_to_be_a_case_is_written_again_once_with_the_rules(monkeypatch):
    prompts = []
    line = {"text": "A line with exactly ten words in it, said plainly here.", "visual": "a river"}

    def chat(prompt, *a, **k):
        prompts.append(prompt)
        return {"title": "The Isdal Woman: A Cold Case and a Murder Nobody Solved", "description": "d", "tags": [], "anchors": ["Bergen"], "lines": [line] * 11}

    monkeypatch.setattr(scriptgen, "_script_chat", chat)
    scriptgen.script("The Isdal Woman", "A source about a woman found in Norway.")
    assert len(prompts) == 2 and "never call a named" not in prompts[0].lower() and "never call a named" in prompts[1].lower()
    prompts.clear()
    scriptgen.script("The Zodiac Killer unsolved murders", "A source.")
    assert len(prompts) == 1  # the rules were there from the start: no second call


def test_the_case_checks_run_for_shorts_too():
    short = {"format": "short", "kind": "case", "description": "A hook.", "topic": "x", "lines": [{"text": "John Smith was the killer and the corpse was mutilated."}]}
    names = {r["name"]: r["ok"] for r in reviewer.generator_checks(short, {"duration": 55.0}) if r["name"].startswith("case_")}
    assert names == {"case_graphic": False, "case_accusation": False, "case_context": False}


def test_every_scene_of_a_case_is_drawn_so_no_archive_photograph_of_a_real_person_appears():
    data = {"kind": "case", "topic": "x", "lines": [{"text": "one"}, {"text": "two"}]}
    assert run._forced_art(data) == {"one", "two"}
    assert run._forced_art({"kind": "mystery", "topic": "x", "lines": [{"text": "one"}]}) == set()


def test_the_thumbnail_of_a_case_is_drawn_with_the_same_no_identifiable_person_rule(monkeypatch, tmp_path):
    assert "identifiable" in aiart.thumbnail_prompt("The river at night", None, case=True)
    assert aiart.thumbnail_prompt("The river at night", None, case=True).startswith(aiart.thumbnail_prompt("The river at night", None))
    assert "identifiable" not in aiart.thumbnail_prompt("The river at night", None)
    src = open(__import__("thumbnail").__file__).read()
    assert "case=" in src
