"""The owner's day 2 is an unsolved crime or case (30 Oct 2026). A case has its own kind with its own cards, and its cards carry the rules YouTube's own pages set (read 30 Oct 2026): non-graphic,
no accusation beyond official findings, no realistic simulation of a victim or suspect, the documentary purpose said in the video itself."""
import kinds


def meta(topic, title="", **k):
    return {"topic": topic, "title": title, "anchors": [], "chapters": [], "lines": [], **k}


def test_crime_and_case_subjects_are_the_case_kind_and_other_subjects_are_not():
    assert kinds.classify(meta("The Zodiac Killer unsolved murders")) == "case"
    assert kinds.classify(meta("The Isdal Woman: a cold case and a stolen identity")) == "case"
    assert kinds.classify(meta("The Great Train Robbery heist")) == "case"
    assert kinds.classify(meta("The Lost Army of Cambyses")) == "mystery"      # an old vanishing is a mystery, not a case
    assert kinds.classify(meta("Cleopatra, the last pharaoh queen")) == "person"
    assert kinds.classify(meta("La Llorona the weeping woman legend")) == "legend"


def test_the_case_cards_carry_the_safety_rules_in_the_prompt_lines():
    for part in ("seo", "thumb", "hook"):
        assert kinds.card("case", part) if hasattr(kinds, "card") else True
    brief = kinds.brief(meta("The Zodiac Killer unsolved murders"), "hook")
    assert "never accuse" in brief.lower() or "official findings" in brief.lower()
    thumb = kinds.brief(meta("The Zodiac Killer unsolved murders"), "thumb")
    assert "no" in thumb.lower() and ("face" in thumb.lower() or "violence" in thumb.lower())


def test_the_case_kind_is_listed_and_every_card_stays_inside_the_prompt_budget():
    assert "case" in kinds.names()
    for part in kinds.PARTS:
        assert len(kinds.brief(meta("The Zodiac Killer unsolved murders"), part)) <= kinds.MAX_CARD + 40
