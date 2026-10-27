import json
from pathlib import Path

import config
import pytest
import trainset

SRC = ("Mami Wata is a water spirit venerated in West, Central and Southern Africa and the African diaspora. " * 3 + "Scholars trace her image to a German chromolithograph of a snake charmer. " * 8
       + "Her worship involves offerings of sweet food, perfume and mirrors, and priests are often called to the role through illness or dreams. " * 6)
TOPICS = ["her river shrines", "the snake she carries", "traders on the coast", "a chromolithograph from Hamburg", "mirrors and sweet perfume", "priests called by dreams",
          "Liberian village tales", "the golden comb legend", "doctors who study belief", "carvers of ivory spoons", "the Atlantic world", "what scholars still dispute"]
LINES = [f"Line {i} tells about {t} and how storytellers kept it alive through many generations along the long warm coast." for i, t in enumerate(TOPICS)]


def video(root, slug, model="meta-llama/llama-3.3-70b-instruct", claims=("VERIFIED",) * 5, **kw):
    d = root / slug
    d.mkdir(parents=True)
    meta = {"approved": True, "hold": False, "review": {"verdict": "pass"}, "format": "doc", "topic": slug, "title": "Who Was Mami Wata? The Name Is Two English Words",
            "description": "Lead sentence.\n\nMore.", "tags": ["mami wata"], "thumb_hook": "THE GOLDEN COMB", "lines": [{"text": t} for t in LINES], "script_model": model,
            "sources": ["Wikipedia: Mami Wata (CC BY-SA 4.0), retold in our own words"], "grounded": True, **kw}
    (d / "meta.json").write_text(json.dumps(meta))
    (d / "claims.json").write_text(json.dumps([{"verification_status": c} for c in claims]))
    return d, meta


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path / "out")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    (tmp_path / "out").mkdir()
    return tmp_path / "out"


def src_of(meta):
    return SRC


def test_a_claude_written_video_is_never_used_unless_the_owner_names_the_model(world):
    d, m = video(world, "a", model="anthropic/claude-sonnet-5.5")
    ok, why = trainset.eligible(d, m)
    assert not ok and "Anthropic" in why
    assert trainset.eligible(d, m, allow=("anthropic/claude-sonnet-5.5",))[0] is True


def test_a_video_whose_writer_was_not_recorded_is_left_out(world):
    d, m = video(world, "a", model="")
    assert trainset.eligible(d, m) == (False, "the writer model was not recorded for this video")


def test_only_passed_approved_not_held_videos_with_a_clean_ledger_are_eligible(world):
    cases = {"held": dict(hold=True), "unapproved": dict(approved=False), "failed": dict(review={"verdict": "fail"}), "facts": dict(facts_open=True), "short-script": dict(lines=[{"text": "x"}])}
    for name, kw in cases.items():
        d, m = video(world, name, **kw)
        assert trainset.eligible(d, m)[0] is False, name
    d, m = video(world, "conflict", claims=("VERIFIED", "CONFLICTING"))
    assert "conflicting" in trainset.eligible(d, m)[1]
    d, m = video(world, "loose", claims=("VERIFIED", "UNVERIFIED", "UNVERIFIED"))
    assert "unverified" in trainset.eligible(d, m)[1]
    d, m = video(world, "clean")
    assert trainset.eligible(d, m) == (True, "")


def test_a_script_example_carries_its_source_text_licence_and_provenance(world):
    d, m = video(world, "a")
    script, pack = trainset.examples(d, m, src_of)
    assert script["task"] == "script" and script["input"]["source"].startswith("Mami Wata is") and script["output"].count("\n") == 11
    assert "CC BY-SA" in script["meta"]["license"] and script["meta"]["script_model"] and script["meta"]["claims"] == {"VERIFIED": 5}
    assert pack["task"] == "packaging" and json.loads(pack["output"])["thumb_hook"] == "THE GOLDEN COMB" and script["id"] != pack["id"]


def test_the_checker_rejects_a_script_with_no_source_a_copied_script_secrets_and_markup(world):
    d, m = video(world, "a")
    good, _ = trainset.examples(d, m, src_of)
    assert trainset.check(good) == []
    nosrc, _ = trainset.examples(d, m, lambda meta: "")
    assert any("no source text" in w for w in trainset.check(nosrc))
    copied = {**good, "output": " ".join(SRC.split()[:200])}
    assert any("copied" in w for w in trainset.check(copied))
    assert any("key or token" in w for w in trainset.check({**good, "output": good["output"] + " sk-abcdefghijklmnopqrstuv"}))
    assert any("email" in w for w in trainset.check({**good, "output": good["output"] + " write to me@example.com"}))
    assert any("markup" in w for w in trainset.check({**good, "output": good["output"] + " see https://example.com"}))
    assert trainset.check({"task": "script"}) == ["bad shape"] and trainset.check("not a dict") == ["bad shape"]


def test_the_checker_judges_packaging_too():
    bad = {"id": "x", "task": "packaging", "input": {}, "meta": {"slug": "s"}, "output": json.dumps({"title": "short", "tags": []})}
    assert trainset.check(bad) and trainset.check({**bad, "output": "not json"}) == ["packaging output is not JSON"]


def test_duplicates_are_dropped_exact_and_near_and_the_first_one_stays(world):
    d, m = video(world, "a")
    a, _ = trainset.examples(d, m, src_of)
    exact = {**a, "id": "other"}
    near = {**a, "id": "near", "output": a["output"].replace("Line 3 tells about", "Line three speaks of").replace("Line 4 tells about", "Line four speaks of")}
    kept, rejected = trainset.check_set([a, exact, near])
    assert [k["id"] for k in kept] == [a["id"]] and [r["rejected"][0] for r in rejected] == ["exact duplicate", "near duplicate"]


def test_one_video_is_never_on_both_sides_of_the_split(world):
    items = [{"meta": {"slug": f"v{i}"}, "task": t, "id": f"{i}{t}"} for i in range(80) for t in ("script", "packaging")]  # two examples per video
    train, valid = trainset.split(items)
    assert valid and not ({e["meta"]["slug"] for e in train} & {e["meta"]["slug"] for e in valid})


def test_build_writes_the_files_and_an_honest_report_and_says_how_far_from_training(world, tmp_path):
    video(world, "ok-one")
    video(world, "claude-one", model="anthropic/claude-sonnet-5.5")
    video(world, "unrecorded", model="")
    rep = trainset.build(out=tmp_path / "ts", source=src_of)
    assert rep["examples_kept"] == {"script": 1, "packaging": 1} and rep["ready_to_train"] == {"script": False, "packaging": False}
    assert set(rep["videos_skipped"]) == {"claude-one", "unrecorded"} and "Anthropic" in rep["videos_skipped"]["claude-one"]
    folder = Path(rep["dir"])
    assert {p.name for p in folder.iterdir()} == {"train.jsonl", "valid.jsonl", "rejected.jsonl", "report.json"}
    rows = [json.loads(l) for f in ("train.jsonl", "valid.jsonl") for l in (folder / f).read_text().splitlines()]
    assert len(rows) == 2 and all("sk-" not in json.dumps(r) for r in rows)
