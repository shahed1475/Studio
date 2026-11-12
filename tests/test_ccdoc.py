"""ccdoc.py (1 Nov 2026): a documentary spec made in a Claude Code session goes in, a held draft comes out. Every claim needs a passage found in a saved page."""
import copy
import json
from pathlib import Path

import pytest

import ccdoc
import config
import records


def make(tmp_path, n=10):
    page = tmp_path / "page.txt"
    page.write_text("Alpha won in 1990. Beta scored twice in 2001 against Gamma. Delta was born in 1975.")
    pics = []
    for i in range(4):
        p = tmp_path / f"pic{i}.png"
        p.write_bytes(b"x")
        pics.append(str(p))
    lines = [{"chapter": "One" if i < 5 else "Two", "text": "Who did Beta score against?" if i == 0 else ("Subscribe for the next record." if i == n - 1 else f"Beta scored against Gamma in 2001, line {i}. " + "The record says so plainly. " * 9),
              "src": ["s1"] if 0 < i < n - 1 else [], "picture": pics[i % 4]} for i in range(n)]
    srcs = [{"id": "s1", "title": "Page one", "url": "https://example.org/1", "passage": "Beta scored twice in 2001 against Gamma", "file": str(page), "read": "2026-11-01"},
            {"id": "s2", "title": "Page two", "url": "https://example.org/2", "passage": "Alpha won in 1990", "file": str(page), "read": "2026-11-01"}]
    return {"slug": "t-doc", "title": "A Test Documentary", "kind": "person", "description": "About Beta.", "tags": ["beta"], "lines": lines, "sources": srcs}


def test_a_good_spec_has_no_errors(tmp_path):
    assert ccdoc.validate(make(tmp_path))[0] == []


@pytest.mark.parametrize("change,needle", [
    (lambda s: s["sources"][0].update(passage="Beta scored six times"), "not in the saved page"),
    (lambda s: s["sources"].pop(), "two sources"),
    (lambda s: s["lines"][3].update(src=["nope"]), "unknown source"),
    (lambda s: s["lines"][0].update(text="Beta is great."), "question"),
    (lambda s: s["lines"][2].update(text="Beta scored in 1888, line 2. " + "The record says so plainly. " * 9), "UNVERIFIED"),
    (lambda s: s["lines"][1].update(picture=""), "picture"),
    (lambda s: s.update(video="x.mp4"), "third-party"),
])
def test_a_spec_that_breaks_a_rule_is_refused(tmp_path, change, needle):
    s = make(tmp_path)
    change(s)
    assert any(needle in e for e in ccdoc.validate(s)[0])


def test_build_hands_the_producer_chapters_pictures_and_motion_and_leaves_a_held_ledgered_draft(tmp_path, monkeypatch):
    spec = make(tmp_path)
    seen = {}

    def produce(data, folder=None):
        seen["data"] = data
        out = tmp_path / "out" / "t-doc"
        out.mkdir(parents=True)
        (out / "video.mp4").write_bytes(b"x")
        records.create(out, {**data, "approved": False})
        return out

    monkeypatch.setattr(ccdoc.run, "_produce_doc", produce)
    monkeypatch.setattr(config, "OUT", tmp_path / "out")
    folder = ccdoc.build(spec, tmp_path)
    d = seen["data"]
    assert d["format"] == "doc" and d["parallax"] is True and d["graphics"] is True and d["art_style"] == "local"
    assert d["chapters"] == [{"title": "One", "start_line": 0}, {"title": "Two", "start_line": 5}]
    assert len(d["local_pictures"]) == 10 and d["local_pictures"][1].endswith("pic1.png") and d["lines"][0]["text"].endswith("?")
    meta = json.loads((folder / "meta.json").read_text())
    assert meta["hold"] is True and meta["approved"] is False and meta["built_by"] == "ccdoc" and meta["grounded"] is True and meta["look"] == "flux"
    rows = json.loads((folder / "claims.json").read_text())
    assert rows and all(r["verification_status"] == "VERIFIED" for r in rows) and rows[0]["source_url"] == "https://example.org/1"


def test_a_spec_with_errors_never_reaches_the_producer(tmp_path, monkeypatch):
    spec = make(tmp_path)
    spec["lines"][0]["text"] = "Beta is great."
    monkeypatch.setattr(ccdoc.run, "_produce_doc", lambda *a, **k: pytest.fail("must not be called"))
    with pytest.raises(ValueError, match="question"):
        ccdoc.build(spec, tmp_path)


def test_a_flux_picture_job_and_a_z_image_job_each_resolve_to_their_own_cache_file(tmp_path, monkeypatch):
    import tools.flux_batch as fb
    import tools.zimage_batch as zb

    monkeypatch.setattr(config, "CACHE", tmp_path / "cache")
    job = {"id": "s1", "prompt": "p", "width": 768, "height": 448, "seed": 1}
    assert ccdoc.resolve("s1", tmp_path, {"s1": {**job, "model": "flux"}}) == fb.path_for(job)
    assert ccdoc.resolve("s1", tmp_path, {"s1": job}) == zb.path_for(job)


def test_the_mixed_look_swaps_in_the_z_image_version_of_a_scene_only_where_one_exists(tmp_path):
    jobs = {"s1": {"id": "s1"}, "s1z": {"id": "s1z"}, "s2": {"id": "s2"}}
    spec = {"lines": [{"picture": "s1"}, {"picture": "s2"}, {"picture": "s1"}]}
    assert [l["picture"] for l in ccdoc.mixed(spec, jobs)["lines"]] == ["s1z", "s2", "s1z"]
    assert [l["picture"] for l in spec["lines"]] == ["s1", "s2", "s1"]  # the spec itself is not changed


def test_pictures_are_read_from_every_pictures_file_beside_the_spec(tmp_path):
    (tmp_path / "pictures.json").write_text(json.dumps([{"id": "a"}]))
    (tmp_path / "pictures_hero.json").write_text(json.dumps([{"id": "b"}]))
    assert set(ccdoc.load_jobs(tmp_path)) == {"a", "b"}


def test_a_documentary_that_ends_like_an_outro_is_warned_not_refused(tmp_path):
    s = make(tmp_path)
    s["lines"][-1]["text"] = "Thanks for watching, and subscribe."
    errors, warns = ccdoc.validate(s)
    assert errors == [] and any("outro" in w for w in warns)


def test_the_picture_credit_passes_the_studios_own_licence_check():
    import studiochecks

    rows = studiochecks.check_licenses({"credits": [ccdoc.CREDIT], "footage": {}})
    assert [r for r in rows if r["name"] == "licenses_allowed"][0]["ok"]


def test_a_wikipedia_source_puts_its_licence_line_into_the_description(tmp_path, monkeypatch):
    spec = make(tmp_path)
    spec["sources"][0]["url"] = "https://en.wikipedia.org/wiki/Beta"
    spec["sources"][0]["title"] = "Beta - Wikipedia"
    seen = {}

    def produce(data, folder=None):
        seen["d"] = data
        out = tmp_path / "out" / "t-doc"
        out.mkdir(parents=True)
        records.create(out, {**data, "approved": False})
        return out

    monkeypatch.setattr(ccdoc.run, "_produce_doc", produce)
    monkeypatch.setattr(config, "OUT", tmp_path / "out")
    ccdoc.build(spec, tmp_path)
    assert "CC BY-SA" in seen["d"]["description"] and "Wikipedia" in seen["d"]["description"]


def test_build_makes_thumbnails_from_the_named_picture_and_records_them(tmp_path, monkeypatch):
    from PIL import Image

    spec = make(tmp_path)
    big = tmp_path / "thumb_src.png"
    Image.new("RGB", (768, 448), (30, 90, 40)).save(big)
    spec["thumb_picture"], spec["thumb_hooks"] = str(big), ["THE RECORD", "TWO DECADES"]

    def produce(data, folder=None):
        out = tmp_path / "out" / "t-doc"
        out.mkdir(parents=True)
        records.create(out, {**data, "approved": False})
        return out

    monkeypatch.setattr(ccdoc.run, "_produce_doc", produce)
    monkeypatch.setattr(config, "OUT", tmp_path / "out")
    folder = ccdoc.build(spec, tmp_path)
    meta = json.loads((folder / "meta.json").read_text())
    assert meta["thumbnail"].startswith("thumbs/") and (folder / meta["thumbnail"]).exists() and len(meta["thumbnails"]) >= 1 and meta["thumb_hook"]


def test_no_logo_goes_into_the_video_unless_the_spec_asks_for_one(tmp_path, monkeypatch):
    """Owner's order, 1 Nov 2026: do not use any logo in a video. The corner mark and the branded subscribe pop-up are both off by default."""
    seen = []

    def produce(data, folder=None):
        seen.append(data)
        out = tmp_path / "out" / f"t-doc{len(seen)}"
        out.mkdir(parents=True)
        records.create(out, {**data, "approved": False})
        return out

    monkeypatch.setattr(ccdoc.run, "_produce_doc", produce)
    monkeypatch.setattr(config, "OUT", tmp_path / "out")
    ccdoc.build(make(tmp_path), tmp_path)
    assert seen[0]["brand_mark"] is False and seen[0]["subscribe_pop"] is False
    ccdoc.build({**make(tmp_path), "subscribe_pop": True, "brand_mark": True}, tmp_path)
    assert seen[1]["brand_mark"] is True and seen[1]["subscribe_pop"] is True


def test_a_pollinations_job_resolves_to_its_own_cache_file(tmp_path, monkeypatch):
    import tools.pollinations_batch as pb

    monkeypatch.setattr(config, "CACHE", tmp_path / "cache")
    job = {"id": "s1", "prompt": "p", "width": 1280, "height": 720, "seed": 1, "provider": "pollinations"}
    assert ccdoc.resolve("s1", tmp_path, {"s1": job}) == pb.path_for(job)


def test_a_cloudflare_job_resolves_to_its_own_cache_file(tmp_path, monkeypatch):
    import tools.cloudflare_batch as cb

    monkeypatch.setattr(config, "CACHE", tmp_path / "cache")
    job = {"id": "s1", "prompt": "p", "steps": 4, "seed": 1, "provider": "cloudflare"}
    assert ccdoc.resolve("s1", tmp_path, {"s1": job}) == cb.path_for(job)


def test_the_cinematic_grade_is_applied_to_the_studios_own_pictures_only_never_to_an_archive_scan(tmp_path, monkeypatch):
    """Owner, 1 Nov 2026: realistic, film colour grade. Own pictures live in cache/cc and get graded copies; a real archive picture is left exactly as it is."""
    from PIL import Image

    monkeypatch.setattr(config, "CACHE", tmp_path / "cache")
    own = tmp_path / "cache" / "cc" / "c-1.jpg"
    own.parent.mkdir(parents=True)
    Image.new("RGB", (64, 36), (200, 40, 40)).save(own)
    scan = tmp_path / "cache" / "archive" / "page.jpg"
    scan.parent.mkdir(parents=True)
    Image.new("RGB", (64, 36), (200, 40, 40)).save(scan)
    out = ccdoc.grade_pictures([str(own), str(scan)], strength=1.0)
    assert Path(out[0]).name.startswith("grade-") and Path(out[0]).parent == own.parent and out[1] == str(scan)
    assert ccdoc.grade_pictures([str(own)], strength=0) == [str(own)]


def test_the_ai_credit_can_name_the_model_that_really_drew_the_pictures(tmp_path, monkeypatch):
    spec = make(tmp_path)
    spec["ai_credit"] = "AI-generated realistic scenes with invented people, not real photographs (FLUX.2 klein 4B through Cloudflare Workers AI)."
    seen = {}

    def produce(data, folder=None):
        seen["d"] = data
        out = tmp_path / "out" / "t-doc"
        out.mkdir(parents=True)
        records.create(out, {**data, "approved": False})
        return out

    monkeypatch.setattr(ccdoc.run, "_produce_doc", produce)
    monkeypatch.setattr(config, "OUT", tmp_path / "out")
    ccdoc.build(spec, tmp_path)
    assert seen["d"]["local_credits"][0].startswith("AI-generated realistic scenes") and "FLUX.2 klein" in seen["d"]["local_credits"][0] and "Z-Image" not in seen["d"]["local_credits"][0]


def test_a_source_page_is_listed_once_in_the_description_however_many_passages_it_supplies(tmp_path, monkeypatch):
    spec = make(tmp_path)
    spec["sources"] = [*spec["sources"], {**spec["sources"][0], "id": "s3", "passage": "Beta scored twice in 2001"}, {**spec["sources"][0], "id": "s4", "passage": "Beta scored twice"}]
    assert ccdoc.source_lines(spec) == ["Page one: https://example.org/1", "Page two: https://example.org/2"]


def test_a_spec_can_say_how_a_name_is_pronounced_for_this_film_only(tmp_path, monkeypatch):
    """1 Nov 2026: the voice check heard Baresch, Horcicky, Tepenecz and Nahuatl oddly. A film's own `say` list changes only what the voice is given while the producer runs
    (the script, captions and description keep the real spelling) and the shared list is back exactly as it was afterwards."""
    import tts

    before = dict(tts.PRONUNCIATION)
    said = []

    def produce(data, folder=None):
        said.append(tts.spoken("Georg Baresch wrote to Amun."))
        out = tmp_path / "out" / "t-doc"
        out.mkdir(parents=True)
        records.create(out, {**data, "approved": False})
        return out

    monkeypatch.setattr(ccdoc.run, "_produce_doc", produce)
    monkeypatch.setattr(config, "OUT", tmp_path / "out")
    ccdoc.build({**make(tmp_path), "say": {"Baresch": "Bahresh"}}, tmp_path)
    assert said == ["Georg Bahresh wrote to Ahmoon."] and tts.PRONUNCIATION == before


def test_a_respelling_must_stay_one_word_or_the_captions_would_drift(tmp_path):
    spec = {**make(tmp_path), "say": {"Baresch": "Bah resh"}}
    assert any("one word" in e for e in ccdoc.validate(spec, tmp_path)[0])
    assert not any("one word" in e for e in ccdoc.validate({**make(tmp_path), "say": {"Baresch": "Bahresh"}}, tmp_path)[0])
