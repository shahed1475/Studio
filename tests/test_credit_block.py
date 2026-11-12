"""Credits in the description YouTube receives (owner's decision, 10 Nov 2026): CC BY, CC BY-SA, NASA media and Pixabay items are credited in full where viewers read it, public-domain and CC0
items as a count, and the whole description stays inside YouTube's size limit. The one place that builds it is compliance.final_description."""
import compliance
import config
import footage
import studiochecks as sc

CBY = "Antikythera fragment A by Marsyas, Wikimedia Commons (CC BY-SA 4.0), https://commons.wikimedia.org/wiki/File:A.jpg"
NASA = "Apollo programme, NASA Image & Video Library (NASA media (credit NASA; no NASA logos)), https://images.nasa.gov/details/x"
PD = "Old engraving, Wikimedia Commons (Public domain), https://commons.wikimedia.org/wiki/File:B.jpg"
CC0 = "Bronze vase, The Met (CC0 (Met Open Access)), https://www.metmuseum.org/art/collection/search/1"
AI = "Images: AI-generated realistic scenes with invented people, not real photographs (Google Gemini image model via OpenRouter)"
FILM = "A calm retelling of a real machine.\n\nSources:\nWikipedia: Antikythera mechanism (CC BY-SA 4.0), retold\n\nChapters:\n0:00 Start\n1:00 Next"


def test_credit_needing_items_are_listed_in_full_the_rest_counted_and_the_ai_label_kept():
    lines = footage.credit_lines([CBY, PD, NASA, CC0, AI, CBY])
    assert lines[:2] == [CBY, NASA] and PD not in lines and CC0 not in lines
    assert "2 more real pictures" in lines[2] and lines[-1] == AI and len(lines) == 4


def test_no_lines_when_there_are_no_credits():
    assert footage.credit_lines([]) == []


def test_final_description_holds_each_credit_needing_item_once_inside_the_size_limit():
    many = [f"Fragment {i} of a long catalogue title by Someone Else, Wikimedia Commons (CC BY 4.0), https://commons.wikimedia.org/wiki/File:F{i}.jpg" for i in range(14)]
    pds = [f"Engraving {i}, Wikimedia Commons (Public domain), https://commons.wikimedia.org/wiki/File:E{i}.jpg" for i in range(40)]
    meta = {"format": "doc", "description": FILM, "credits": many + pds + [AI]}
    final = compliance.final_description(meta)
    assert all(final.count(c) == 1 for c in many) and "40 more real pictures" in final and pds[0] not in final
    assert len(final.encode()) < compliance.DESCRIPTION_MAX_BYTES and not compliance.metadata_problems({**meta, "title": "T", "tags": []})


# ---- security review, 10 Nov 2026: classify by the item's stored licence, never by words in its title ----
SNEAKY = "The Public Domain Map of Gears, Wikimedia Commons (CC BY 4.0), https://commons.wikimedia.org/wiki/File:Map.jpg"
SNEAKY_ASSET = {"credit": SNEAKY, "licence": "CC BY 4.0", "page": "https://commons.wikimedia.org/wiki/File:Map.jpg"}


def test_a_credit_needing_item_with_public_domain_in_its_title_is_still_credited_in_full():
    assert SNEAKY in footage.credit_lines([SNEAKY, PD], [SNEAKY_ASSET])
    assert SNEAKY in footage.credit_lines([SNEAKY])  # the text alone is enough: a credit-needing licence name anywhere wins over "public domain"


def test_the_stored_licence_decides_when_the_credit_text_names_none_or_is_misleading():
    c = "Some photo from a museum site, https://x.org/1"
    assert c in footage.credit_lines([c], [{"credit": c, "licence": "CC BY 4.0"}])
    assert c not in footage.credit_lines([c], [])
    liar = "Some photo, Wikimedia Commons (Public domain), https://x.org/1"
    assert liar in footage.credit_lines([liar], [{"credit": liar, "licence": "CC BY-SA 4.0"}])


def test_the_gate_passes_when_the_final_description_credits_them_and_blocks_when_it_does_not(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    meta = {"credits": [CBY, NASA, PD, AI], "assets": [], "footage": {"drawn": 1}, "grounded": False, "description": FILM}
    rows = {r["name"]: r for r in sc.check_licenses(meta)}
    assert rows["credits_in_description"]["ok"] and rows["licenses_allowed"]["ok"]
    monkeypatch.setattr(footage, "credit_lines", lambda credits, assets=(): [])  # mutation: the credits never reach the description
    assert not {r["name"]: r for r in sc.check_licenses(meta)}["credits_in_description"]["ok"]


def test_a_refused_stored_licence_blocks_even_behind_a_friendly_credit_text(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    refused = {"credit": "Photo, Flickr (Public domain), https://x.org/2", "licence": "CC BY-NC 4.0", "page": "https://x.org/2"}
    meta = {"credits": [refused["credit"]], "assets": [refused], "footage": {"drawn": 0}, "grounded": False, "description": "intro"}
    assert not {r["name"]: r for r in sc.check_licenses(meta)}["licenses_allowed"]["ok"]


def test_the_finder_strips_refusal_words_from_a_title_before_it_writes_the_credit():
    import openmedia
    import realmedia

    f = realmedia.Finder("T", ["T"])
    credit = f._credit(openmedia._item("commons", "image", "Non-commercial Vehicles Photo", "https://commons.example/1", "https://u/1.jpg", "CC BY 4.0", "Non-commercial Vehicles Photo, Wikimedia Commons"))
    assert "ommercial" not in credit and "CC BY 4.0" in credit and "https://commons.example/1" in credit
