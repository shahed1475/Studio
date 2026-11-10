"""The studio's one rule for "may this picture or clip be used, and does it need a credit" (owner's decision, 10 Nov 2026: public domain, CC0, CC BY, CC BY-SA, NASA media without NASA logos,
and the Pixabay Content License, as long as every item keeps its address, licence and credit and the credits go in the description)."""
import pytest

import assetledger
import config
import footage_real
import licences
import openmedia
import studiochecks as sc

ACCEPTED = ["Public domain", "Public Domain Mark", "PD-old-70", "PD-US", "Public domain (US government)", "CC0", "CC0 (Met Open Access)", "CC0 (Smithsonian Open Access)",
            "CC BY 4.0", "CC BY 2.0", "CC BY-SA 3.0", "CC BY-SA 4.0", "cc by-sa 4.0", "Wikimedia Commons, CC BY-SA 4.0",
            "NASA media (credit NASA; no NASA logos)", "NASA media", "Pixabay Content License", "Pixabay License"]
REFUSED = ["CC BY-NC 4.0", "CC BY-NC-SA 2.0", "CC BY-ND 4.0", "CC BY-NC-ND 3.0", "cc by-nc 2.0", "All rights reserved", "Fair use", "Used with permission", "Non-commercial use only",
           "Pexels License", "Photo via Pexels (CC0)", "Video via Pexels, CC BY 4.0", "GFDL", "GFDL and CC BY-SA 3.0", "", "unknown", "some blog", "Standard YouTube licence"]


@pytest.mark.parametrize("name", ACCEPTED)
def test_accepted_licences(name):
    assert licences.accepted(name), name
    assert footage_real.licence_ok(name), name  # the footage code and the library search use the same rule
    assert openmedia._item("x", "image", "t", "https://p", "https://u", name, "c")["accepted"] is True


@pytest.mark.parametrize("name", REFUSED)
def test_refused_licences(name):
    assert not licences.accepted(name), name
    assert not footage_real.licence_ok(name), name


@pytest.mark.parametrize("name,needs", [("Public domain", False), ("PD-old-70", False), ("CC0", False), ("CC0 (Met Open Access)", False), ("CC BY 4.0", True), ("CC BY-SA 3.0", True),
                                        ("NASA media (credit NASA; no NASA logos)", True), ("Pixabay Content License", True)])
def test_which_licences_need_a_credit_line(name, needs):
    assert licences.needs_credit(name) is needs


def test_a_refusal_word_beats_an_accepted_one_in_the_same_text():
    assert not licences.accepted("CC BY-SA 4.0 but non-commercial use only")
    assert not licences.accepted("Public domain, all rights reserved")


def test_the_nasa_label_no_longer_holds_the_word_copyright_the_gate_forbids():
    assert "copyright" not in " ".join(i for i in [openmedia.NASA_LICENCE]).lower() and licences.accepted(openmedia.NASA_LICENCE)


# ---- the gate that decides whether a finished video may go out ----
def credits_row(meta, tmp_path, monkeypatch, name):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    return next(r for r in sc.check_licenses(meta) if r["name"] == name)


def test_gate_accepts_credited_licences_when_the_description_carries_each_credit(tmp_path, monkeypatch):
    credits = ["Antikythera fragment A (Wikimedia Commons, CC BY-SA 4.0), https://commons.wikimedia.org/wiki/File:A.jpg", "Apollo 11 (NASA media; credit NASA), https://images.nasa.gov/details/x",
               "Temple (Pixabay Content License), https://pixabay.com/photos/1/", "Map.jpg (Wikimedia Commons, Public domain)"]
    meta = {"credits": credits, "footage": {"drawn": 0}, "grounded": False, "description": "intro\n\nPicture credits:\n" + "\n".join(credits[:3])}
    rows = {r["name"]: r for r in sc.check_licenses(meta)}
    assert rows["licenses_allowed"]["ok"] and rows["credits_in_description"]["ok"]


def test_gate_blocks_a_video_whose_credit_needing_item_is_missing_from_the_description(tmp_path, monkeypatch):
    credits = ["Fragment (Wikimedia Commons, CC BY-SA 4.0), https://commons.wikimedia.org/wiki/File:A.jpg", "Map.jpg (Wikimedia Commons, Public domain)"]
    meta = {"credits": credits, "footage": {"drawn": 0}, "grounded": False, "description": "intro only"}
    row = credits_row(meta, tmp_path, monkeypatch, "credits_in_description")
    assert not row["ok"] and row["severity"] == "block" and "Fragment" in row["detail"]


def test_gate_does_not_ask_for_a_description_line_for_public_domain_or_cc0(tmp_path, monkeypatch):
    meta = {"credits": ["Map.jpg (Wikimedia Commons, Public domain)", "Vase (The Met, CC0 (Met Open Access))"], "footage": {"drawn": 0}, "grounded": False, "description": "x"}
    assert credits_row(meta, tmp_path, monkeypatch, "credits_in_description")["ok"]


def test_gate_still_refuses_noncommercial_all_rights_and_unknown(tmp_path, monkeypatch):
    meta = {"credits": ["Photo (Flickr, CC BY-NC 2.0)", "Pic (Flickr, All rights reserved)", "Pic2 (some blog)"], "footage": {"drawn": 0}, "grounded": False, "description": "x"}
    assert not credits_row(meta, tmp_path, monkeypatch, "licenses_allowed")["ok"]


def test_ledger_accepts_the_new_licences_and_wants_the_author_or_owner_name_for_credited_ones():
    for lic in ("nasa media", "pixabay content license"):
        assert lic in assetledger.ALLOWED and lic in assetledger.NEEDS_ATTRIBUTION
