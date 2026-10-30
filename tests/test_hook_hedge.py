"""30 Oct 2026: the Lost Army film opened "...an army of fifty thousand Persian soldiers simply vanished." as plain fact and only the second line said "the legend says". Shorts already
refuse an absolute (clipper.OVERCLAIM). A documentary about a legend or a mystery now has to frame the opening claim as a claim: the writer is told, the reviewer warns (never blocks)."""
import reviewer
import scriptgen

PROBE = {"duration": 500.0}


def meta(first, kind="mystery"):
    return {"format": "doc", "kind": kind, "description": "A hook.", "lines": [{"text": first}, {"text": "The legend says Cambyses sent them to the oasis."}]}


def row(m):
    return next((r for r in reviewer.generator_checks(m, PROBE) if r["name"] == "hook_claims_as_fact"), None)


def test_a_legend_opening_that_states_the_claim_as_plain_fact_is_warned_about():
    r = row(meta("Somewhere in the Western Desert of Egypt, in 525 BC, an army of fifty thousand Persian soldiers simply vanished."))
    assert r and not r["ok"] and r["severity"] == "warn" and "claim" in r["detail"]


def test_a_hedged_or_questioning_opening_is_fine():
    assert row(meta("In 525 BC an army of fifty thousand Persian soldiers is said to have vanished in the Egyptian desert."))["ok"]
    assert row(meta("Where did an army of fifty thousand Persian soldiers go?"))["ok"]
    assert row(meta("According to Herodotus, fifty thousand Persian soldiers walked into the desert and never came out."))["ok"]
    assert row(meta("The legend of the lost army begins with a sandstorm."))["ok"]


def test_only_legend_and_mystery_films_are_asked_for_it_and_shorts_are_left_to_their_own_rule():
    assert row(meta("Napoleon crossed the Alps in May 1800.", kind="person")) is None
    assert row(meta("The army vanished.", kind="default")) is None
    short = {"format": "short", "kind": "mystery", "description": "A hook.", "lines": [{"text": "The army vanished."}]}
    assert row(short) is None


def test_the_writer_is_told_to_frame_a_legend_as_a_claim_in_the_first_sentence():
    assert "said to" in scriptgen.DOC_STRUCTURE and "never as plain fact" in scriptgen.DOC_STRUCTURE
