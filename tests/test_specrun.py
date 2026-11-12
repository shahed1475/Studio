import copy
import json
from pathlib import Path

import agentlog
import ccdoc
import config
import llm
import pytest
import risk
import specrun
import test_ccdoc
import tools.cloudflare_batch as cb


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(specrun, "ROOT", tmp_path / "specs")
    monkeypatch.setattr(specrun, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(config, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(risk, "running_jobs", lambda *a: [])
    events = []
    monkeypatch.setattr(agentlog, "event", lambda *a, **k: events.append(a))
    built = []

    def fake_build(spec, base, mix=False):
        with pytest.raises(RuntimeError):
            llm._post({}, "k")  # a model call inside a spec build is blocked
        out = tmp_path / "out" / spec["title"].lower().replace(" ", "-")
        out.mkdir(parents=True, exist_ok=True)
        built.append(spec["title"])
        return out

    monkeypatch.setattr(ccdoc, "build", fake_build)
    drawn = {"cap": False, "calls": 0}

    def fake_run(jobs, *a, **k):
        drawn["calls"] += 1
        if drawn["cap"]:
            return [{"id": j["id"], "status": "CAP"} for j in jobs]
        for j in jobs:
            p = cb.path_for(j)
            p.write_bytes(b"x")
        return [{"id": j["id"], "status": "DONE"} for j in jobs]

    monkeypatch.setattr(cb, "run", fake_run)
    return {"tmp": tmp_path, "events": events, "built": built, "drawn": drawn}


def put(env, name="the-test-film", change=None):
    base = env["tmp"] / "specs" / "inbox" / name
    (base / "src").mkdir(parents=True, exist_ok=True)
    spec = test_ccdoc.make(env["tmp"])
    (base / "src" / "page.txt").write_text(Path(spec["sources"][0]["file"]).read_text())
    for s in spec["sources"]:
        s["file"] = "src/page.txt"
    pics = sorted({l["picture"] for l in spec["lines"]})
    for i, l in enumerate(spec["lines"]):
        l["picture"] = f"p{pics.index(l['picture'])}"
    (base / "pictures.json").write_text(json.dumps([{"id": f"p{i}", "prompt": f"scene {i}"} for i in range(len(pics))]))
    if change:
        change(spec)
    (base / "doc.json").write_text(json.dumps(spec))
    return base


def test_a_good_spec_is_drawn_free_and_built_with_model_calls_blocked_and_logged(env):
    put(env)
    res = specrun.tick(github=False)
    assert res["built"] == ["the-test-film"] and env["built"] == ["A Test Documentary"] and env["drawn"]["calls"] == 1
    assert env["events"][0][0] == "info" and "Spec built" in env["events"][0][1]
    assert specrun.status()["specs"]["the-test-film"]["status"] == "built"


def test_the_same_spec_is_not_built_twice_but_a_changed_one_is(env):
    base = put(env)
    specrun.tick(github=False)
    assert specrun.tick(github=False)["built"] == []
    spec = json.loads((base / "doc.json").read_text())
    spec["title"] = "A Test Documentary Again"
    (base / "doc.json").write_text(json.dumps(spec))
    assert specrun.tick(github=False)["built"] == ["the-test-film"] and env["built"][-1] == "A Test Documentary Again"


def test_a_spec_that_breaks_a_rule_is_rejected_with_its_reasons_and_nothing_is_drawn_or_built(env):
    put(env, change=lambda s: s["sources"][0].update(passage="Beta scored six times"))
    res = specrun.tick(github=False)
    assert res["rejected"] == ["the-test-film"] and env["built"] == [] and env["drawn"]["calls"] == 0
    assert "not in the saved page" in specrun.status()["specs"]["the-test-film"]["reasons"][0] and env["events"][0][0] == "error"


def test_a_source_path_that_leaves_the_spec_folder_is_refused(env):
    put(env, change=lambda s: s["sources"][0].update(file="../../../../etc/passwd"))
    assert specrun.tick(github=False)["rejected"] == ["the-test-film"] and env["built"] == []


def test_when_the_free_allowance_ends_the_build_waits_and_finishes_next_time(env):
    put(env)
    env["drawn"]["cap"] = True
    assert specrun.tick(github=False)["waiting"] == ["the-test-film"] and env["built"] == []
    env["drawn"]["cap"] = False
    assert specrun.tick(github=False)["built"] == ["the-test-film"]


def test_a_render_in_progress_or_a_second_runner_means_nothing_happens(env, monkeypatch):
    put(env)
    monkeypatch.setattr(risk, "running_jobs", lambda *a: ["run.py doc"])
    assert "render" in specrun.tick(github=False)["skipped"] and env["built"] == []


def test_the_model_guard_restores_the_real_functions():
    before = llm._post
    with specrun.no_model():
        with pytest.raises(RuntimeError):
            llm.chat("x")
    assert llm._post is before


def test_only_safe_names_and_files_are_copied_from_the_github_listing(env):
    files = {"a-new-film": [{"type": "file", "name": "doc.json"}, {"type": "file", "name": "evil.sh"}, {"type": "dir", "name": "src"}]}
    served = {
        "contents/specs/inbox?ref=main": [{"type": "dir", "name": "a-new-film"}, {"type": "dir", "name": "../x"}, {"type": "dir", "name": "Bad Name"}, {"type": "file", "name": "readme"}],
        "contents/specs/inbox/a-new-film?ref=main": files["a-new-film"],
        "contents/specs/inbox/a-new-film/src?ref=main": [{"type": "file", "name": "page.txt"}, {"type": "file", "name": "x.exe"}],
    }
    asked = []

    def get(url):
        asked.append(url)
        for k, v in served.items():
            if url.endswith(k):
                return json.dumps(v).encode()
        return b"{}"

    assert specrun.fetch_github(get) == ["a-new-film"]
    got = sorted(p.relative_to(env["tmp"] / "specs" / "gh").as_posix() for p in (env["tmp"] / "specs" / "gh").rglob("*") if p.is_file())
    assert got == ["a-new-film/doc.json", "a-new-film/src/page.txt"]
    assert all(u.startswith(("https://api.github.com/", "https://raw.githubusercontent.com/shahed1475/Studio/main/specs/inbox/a-new-film/")) for u in asked)


def test_the_credit_names_the_model_that_really_drew_the_pictures(env):
    base = put(env)
    spec = json.loads((base / "doc.json").read_text())
    spec["ai_credit"] = "drawn by Z-Image on the owner's PC"
    (base / "doc.json").write_text(json.dumps(spec))
    got = specrun.prepare(base, "doc")
    assert "Cloudflare" in got["ai_credit"] and "AI-generated" in got["ai_credit"] and "Z-Image" not in got["ai_credit"]


def test_a_picture_must_be_a_job_id_never_a_file_path(env):
    put(env, change=lambda s: s["lines"][2].update(picture="/etc/passwd"))
    assert specrun.tick(github=False)["rejected"] == ["the-test-film"] and env["built"] == []
    assert "not an id in pictures.json" in specrun.status()["specs"]["the-test-film"]["reasons"][0]


def test_a_short_slug_can_never_leave_the_output_folder(tmp_path):
    import re
    slug = "../../x/Evil Slug"
    assert re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-") == "x-evil-slug"
