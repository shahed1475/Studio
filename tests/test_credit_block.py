"""Picture credits in the description (owner's decision, 10 Nov 2026): CC BY, CC BY-SA, NASA media and Pixabay items are credited where viewers read it, and a repackaged description keeps them."""
import config
import footage
import seo
import studiochecks as sc

CBY = "Antikythera fragment A, Wikimedia Commons (CC BY-SA 4.0), https://commons.wikimedia.org/wiki/File:A.jpg"
NASA = "Apollo programme, NASA Image & Video Library (NASA media (credit NASA; no NASA logos)), https://images.nasa.gov/details/x"
PD = "Old engraving, Wikimedia Commons (Public domain), https://commons.wikimedia.org/wiki/File:B.jpg"
CC0 = "Bronze vase, The Met (CC0 (Met Open Access)), https://www.metmuseum.org/art/collection/search/1"
AI = "Images: AI-generated realistic scenes with invented people, not real photographs (Google Gemini image model via OpenRouter)"
FILM = "A calm retelling of a real machine.\n\nSources:\nWikipedia: Antikythera mechanism (CC BY-SA 4.0), retold\n\nChapters:\n0:00 Start\n1:00 Next"


def test_block_lists_credit_needing_items_in_full_and_counts_the_rest():
    block = footage.credit_block([CBY, PD, NASA, CC0, AI, CBY])
    assert block.startswith("Picture credits:") and f"- {CBY}" in block and f"- {NASA}" in block and block.count(CBY) == 1
    assert PD not in block and CC0 not in block and AI not in block and "2 more real pictures" in block


def test_block_is_empty_when_there_is_no_real_picture_at_all():
    assert footage.credit_block([AI]) == "" and footage.credit_block([]) == ""


def test_the_block_goes_before_the_chapters_and_after_the_sources():
    out = footage.with_credits(FILM, [CBY, PD])
    assert out.index("Sources:") < out.index("Picture credits:") < out.index("Chapters:") and out.startswith("A calm retelling")


def test_with_credits_twice_gives_the_same_text_and_replaces_an_older_block():
    once = footage.with_credits(FILM, [CBY])
    assert footage.with_credits(once, [CBY]) == once
    other = footage.with_credits(once, [NASA])
    assert NASA in other and CBY not in other and other.count("Picture credits:") == 1


def test_a_short_description_without_sections_gets_the_block_at_the_end():
    out = footage.with_credits("A hook sentence about gears.", [CBY])
    assert out == "A hook sentence about gears.\n\nPicture credits:\n- " + CBY


def test_repackaging_keeps_the_credits_in_a_film_and_in_a_short():
    film = footage.with_credits(FILM, [CBY, PD])
    new = seo.rebuild_description(film, "A new intro.")
    assert new.startswith("A new intro.") and "Sources:" in new and f"- {CBY}" in new and "Chapters:" in new and new.index("Picture credits:") < new.index("Chapters:")
    short = footage.with_credits("Old hook.", [CBY])
    assert seo.rebuild_description(short, "New hook.") == "New hook.\n\nPicture credits:\n- " + CBY


def test_the_gate_passes_a_description_made_by_with_credits_and_blocks_one_without(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    credits = [CBY, NASA, PD, AI]
    ok = {"credits": credits, "footage": {"drawn": 1}, "grounded": False, "description": footage.with_credits(FILM, credits)}
    rows = {r["name"]: r for r in sc.check_licenses(ok)}
    assert rows["credits_in_description"]["ok"] and rows["licenses_allowed"]["ok"]
    bad = {**ok, "description": FILM}
    assert not {r["name"]: r for r in sc.check_licenses(bad)}["credits_in_description"]["ok"]
