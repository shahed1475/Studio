"""ccbuild.py (1 Nov 2026): the rules that refuse a bad spec, and the pieces that need no network."""
import copy
import json
from pathlib import Path

import pytest
from PIL import Image

import ccbuild

BASE = Path(__file__).resolve().parent.parent / "docs" / "studio" / "flannan"
SPEC = json.loads((BASE / "short.json").read_text()) if (BASE / "short.json").exists() else None
# Only the tests that read the real Flannan spec need it. It was never committed (it lives in the workshop folder), so those tests skip here;
# the same validator rules are also checked below against a small spec written for the tests (FIXTURE), which runs everywhere.
needs_spec = pytest.mark.skipif(SPEC is None, reason="the Flannan spec is not in this checkout")


def errors(spec):
    return ccbuild.validate(spec, BASE)[0]


@needs_spec
def test_the_real_spec_passes():
    assert errors(SPEC) == []


@needs_spec
def test_a_forbidden_footage_key_is_refused():
    s = copy.deepcopy(SPEC)
    s["footage"] = "x"
    assert any("footage" in e for e in errors(s))


@needs_spec
def test_last_line_must_say_subscribe_not_follow():
    s = copy.deepcopy(SPEC)
    s["lines"][-1]["text"] = "Follow for the next true story."
    assert any("subscribe" in e for e in errors(s))


@needs_spec
def test_first_line_must_be_a_short_question():
    s = copy.deepcopy(SPEC)
    s["lines"][0]["text"] = "Three keepers vanished."
    assert any("line 1" in e for e in errors(s))


@needs_spec
def test_a_yes_no_hook_is_only_a_warning():
    s = copy.deepcopy(SPEC)
    s["lines"][0]["text"] = "Did three keepers really vanish?"
    assert errors(s) == [] and any("yes/no" in w for w in ccbuild.validate(s, BASE)[1])


@needs_spec
def test_a_verified_claim_needs_its_passage_in_the_saved_source():
    s = copy.deepcopy(SPEC)
    s["claims"][0]["passage"] = "a sentence the page never contained"
    assert any("not in the saved source text" in e for e in errors(s))


@needs_spec
def test_conflicting_or_unverified_claims_stop_the_build():
    s = copy.deepcopy(SPEC)
    s["claims"][0]["status"] = "UNVERIFIED"
    assert any("UNVERIFIED" in e for e in errors(s))


@needs_spec
def test_two_sources_are_the_minimum():
    s = copy.deepcopy(SPEC)
    s["sources"] = s["sources"][:1]
    assert any("two sources" in e for e in errors(s))


@needs_spec
def test_too_many_words_is_refused():
    s = copy.deepcopy(SPEC)
    s["lines"][3]["text"] = " ".join(["word"] * 80)
    assert any("too long" in e for e in errors(s))


def test_fit_makes_a_9_16_picture_and_flip_mirrors_it(tmp_path):
    src = tmp_path / "a.png"
    im = Image.new("RGB", (512, 896), (0, 0, 0))
    im.paste((255, 255, 255), (0, 0, 100, 896))
    im.save(src)
    a, b = ccbuild.fit(src, tmp_path / "o1.png"), ccbuild.fit(src, tmp_path / "o2.png", flip=True)
    A, B = Image.open(a), Image.open(b)
    assert A.size == (1080, 1920) and A.getpixel((10, 900))[0] > 200 and B.getpixel((10, 900))[0] < 50 and B.getpixel((1070, 900))[0] > 200


@needs_spec
def test_the_ledger_carries_the_passage_and_the_source():
    srcs = {s["id"]: s for s in SPEC["sources"]}
    rows = ccbuild.ledger(SPEC, srcs)
    assert len(rows) == len(SPEC["claims"]) and all(r["evidence_excerpt"] and r["source_url"].startswith("https://") for r in rows)


def test_a_pollinations_job_resolves_to_its_own_cache_file(tmp_path, monkeypatch):
    import config
    import tools.pollinations_batch as pb

    monkeypatch.setattr(config, "CACHE", tmp_path / "cache")
    job = {"id": "s1", "prompt": "p", "width": 1080, "height": 1920, "seed": 1, "provider": "pollinations"}
    assert ccbuild.resolve("s1", {"s1": job}) == pb.path_for(job)


def test_a_cloudflare_job_resolves_to_its_own_cache_file(tmp_path, monkeypatch):
    import config
    import tools.cloudflare_batch as cb

    monkeypatch.setattr(config, "CACHE", tmp_path / "cache")
    job = {"id": "s1", "prompt": "p", "steps": 4, "seed": 1, "provider": "cloudflare"}
    assert ccbuild.resolve("s1", {"s1": job}) == cb.path_for(job)


def test_pictures_are_read_from_every_pictures_file_beside_the_spec(tmp_path):
    (tmp_path / "pictures.json").write_text(json.dumps([{"id": "a"}]))
    (tmp_path / "pictures_local.json").write_text(json.dumps([{"id": "b"}]))
    assert set(ccbuild.load_jobs(tmp_path)) == {"a", "b"}


def test_a_local_flux_job_resolves_to_its_own_cache_file(tmp_path, monkeypatch):
    import config
    import tools.flux_batch as fb

    monkeypatch.setattr(config, "CACHE", tmp_path / "cache")
    job = {"id": "s1", "prompt": "p", "width": 512, "height": 896, "seed": 1, "model": "flux"}
    assert ccbuild.resolve("s1", {"s1": job}) == fb.path_for(job)


def test_a_fitted_picture_is_kept_where_the_studio_may_give_it_camera_motion(tmp_path, monkeypatch):
    """A Short's pictures are the studio's own free drawings: they are fitted into cache/cc, which animate.own_picture accepts, not into the video's folder (a first build had 0 motion clips)."""
    import animate
    import config

    monkeypatch.setattr(config, "CACHE", tmp_path / "cache")
    src = tmp_path / "a.png"
    Image.new("RGB", (64, 64), (10, 20, 30)).save(src)
    p = ccbuild.fitted(src)
    assert p.exists() and p.parent == tmp_path / "cache" / "cc" and p.name.startswith("fit-") and animate.own_picture(p)
    assert Image.open(p).size == ccbuild.SIZE and ccbuild.fitted(src) == p and ccbuild.fitted(src, flip=True) != p


def test_every_verified_claim_leaves_a_checked_source_entry_the_gate_can_read():
    spec = {"sources": [{"id": "a", "title": "Page A", "url": "https://example.org/a", "file": "src/a.txt"}],
            "claims": [{"text": "x", "source": "a", "passage": "It happened in 1742.", "status": "VERIFIED"},
                       {"text": "y", "source": "a", "passage": "Not proven.", "status": "UNVERIFIED"}]}
    out = ccbuild.claim_sources(spec)
    assert out == [{"title": "Page A", "url": "https://example.org/a", "passage": "It happened in 1742.", "passage_checked": True}]
    import ledger

    rows = ledger.build({"sources": out, "lines": [{"text": "A book of 1742 says so."}]}, "")
    assert rows[0]["verification_status"] == "VERIFIED" and rows[0]["source_url"] == "https://example.org/a"


def test_a_spec_without_photos_says_every_picture_is_ai_generated():
    assert ccbuild.pictures_line({}) == "Pictures: AI-generated illustrations, not photographs of the real place. Voice: synthetic."


def test_a_spec_with_photos_lists_each_credit_and_says_the_rest_is_ai_art():
    line = ccbuild.pictures_line({"photo_credits": ["Golden Kappa statue by A Person, CC BY 2.0, https://commons.wikimedia.org/wiki/File:X.jpg"]})
    assert "Golden Kappa statue by A Person, CC BY 2.0" in line
    assert line.startswith("Real photographs (free licence):")
    assert "Other pictures: AI-generated illustrations" in line


# ---- the same rules against a spec written for these tests (no workshop file needed) ----
PASSAGE_A = "The keeper wrote that the lamp was out on the night of the storm."
PASSAGE_B = "The relief boat found the gate shut and the table set."


@pytest.fixture
def fixture_spec(tmp_path):
    """A complete, valid Short spec with placeholder text, its two saved source pages beside it."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.txt").write_text(f"Page A.\n{PASSAGE_A}\nMore text.")
    (tmp_path / "src" / "b.txt").write_text(f"Page B.\n{PASSAGE_B}")
    lines = [{"text": "Where did the three keepers go?", "picture": "p1"}] + \
            [{"text": f"Placeholder story line number {i} for the test.", "picture": f"p{i}"} for i in range(2, 8)] + \
            [{"text": "Subscribe for the next true story.", "picture": "p8"}]
    spec = {"title": "A test Short", "lines": lines, "credits": ["Pictures: AI-generated illustrations"],
            "sources": [{"id": "a", "title": "Page A", "url": "https://example.org/a", "read": "2026-11-20", "file": "src/a.txt"},
                        {"id": "b", "title": "Page B", "url": "https://example.org/b", "read": "2026-11-20", "file": "src/b.txt"}],
            "claims": [{"text": "The lamp was out.", "source": "a", "passage": PASSAGE_A, "status": "VERIFIED"},
                       {"text": "The table was set.", "source": "b", "passage": PASSAGE_B, "status": "VERIFIED"}]}
    return spec, tmp_path


def test_the_fixture_spec_passes(fixture_spec):
    spec, base = fixture_spec
    assert ccbuild.validate(spec, base) == ([], [])


@pytest.mark.parametrize("change, expected", [
    (lambda s: s.update(footage="x"), "footage"),
    (lambda s: s["lines"][-1].update(text="Follow for the next true story."), "subscribe"),
    (lambda s: s["lines"][0].update(text="Three keepers vanished."), "line 1"),
    (lambda s: s["claims"][0].update(passage="a sentence the page never contained"), "not in the saved source text"),
    (lambda s: s["claims"][0].update(status="UNVERIFIED"), "UNVERIFIED"),
    (lambda s: s["claims"][1].update(status="CONFLICTING"), "CONFLICTING"),
    (lambda s: s.update(sources=s["sources"][:1]), "two sources"),
    (lambda s: s["lines"][3].update(text=" ".join(["word"] * 150)), "too long"),
    (lambda s: s["sources"][1].update(url="http://example.org/b"), "https address"),
    (lambda s: s["sources"][1].update(file="src/missing.txt"), "no saved text"),
    (lambda s: s.update(claims=[]), "claim ledger is empty"),
    (lambda s: s.update(lines=s["lines"][:5]), "6 to 14 lines"),
], ids=["footage", "follow", "hook", "passage", "unverified", "conflicting", "sources", "words", "http", "no-text", "no-claims", "few-lines"])
def test_each_rule_refuses_a_broken_fixture_spec(fixture_spec, change, expected):
    spec, base = fixture_spec
    s = copy.deepcopy(spec)
    change(s)
    assert any(expected in e for e in ccbuild.validate(s, base)[0]), ccbuild.validate(s, base)[0]


def test_a_yes_no_hook_in_the_fixture_is_only_a_warning(fixture_spec):
    spec, base = fixture_spec
    s = copy.deepcopy(spec)
    s["lines"][0]["text"] = "Did three keepers really vanish?"
    errs, warns = ccbuild.validate(s, base)
    assert errs == [] and any("yes/no" in w for w in warns)


def test_the_fixture_ledger_carries_the_passage_and_the_source(fixture_spec):
    spec, _ = fixture_spec
    rows = ccbuild.ledger(spec, {s["id"]: s for s in spec["sources"]})
    assert len(rows) == 2 and all(r["evidence_excerpt"] and r["source_url"].startswith("https://") for r in rows)
