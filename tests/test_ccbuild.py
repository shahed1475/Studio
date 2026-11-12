"""ccbuild.py (1 Nov 2026): the rules that refuse a bad spec, and the pieces that need no network."""
import copy
import json
from pathlib import Path

import pytest
from PIL import Image

import ccbuild

BASE = Path(__file__).resolve().parent.parent / "docs" / "studio" / "flannan"
SPEC = json.loads((BASE / "short.json").read_text()) if (BASE / "short.json").exists() else None
pytestmark = pytest.mark.skipif(SPEC is None, reason="the Flannan spec is not in this checkout")


def errors(spec):
    return ccbuild.validate(spec, BASE)[0]


def test_the_real_spec_passes():
    assert errors(SPEC) == []


def test_a_forbidden_footage_key_is_refused():
    s = copy.deepcopy(SPEC)
    s["footage"] = "x"
    assert any("footage" in e for e in errors(s))


def test_last_line_must_say_subscribe_not_follow():
    s = copy.deepcopy(SPEC)
    s["lines"][-1]["text"] = "Follow for the next true story."
    assert any("subscribe" in e for e in errors(s))


def test_first_line_must_be_a_short_question():
    s = copy.deepcopy(SPEC)
    s["lines"][0]["text"] = "Three keepers vanished."
    assert any("line 1" in e for e in errors(s))


def test_a_yes_no_hook_is_only_a_warning():
    s = copy.deepcopy(SPEC)
    s["lines"][0]["text"] = "Did three keepers really vanish?"
    assert errors(s) == [] and any("yes/no" in w for w in ccbuild.validate(s, BASE)[1])


def test_a_verified_claim_needs_its_passage_in_the_saved_source():
    s = copy.deepcopy(SPEC)
    s["claims"][0]["passage"] = "a sentence the page never contained"
    assert any("not in the saved source text" in e for e in errors(s))


def test_conflicting_or_unverified_claims_stop_the_build():
    s = copy.deepcopy(SPEC)
    s["claims"][0]["status"] = "UNVERIFIED"
    assert any("UNVERIFIED" in e for e in errors(s))


def test_two_sources_are_the_minimum():
    s = copy.deepcopy(SPEC)
    s["sources"] = s["sources"][:1]
    assert any("two sources" in e for e in errors(s))


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
