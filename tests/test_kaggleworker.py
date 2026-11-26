"""Kaggle remote GPU worker (kaggleworker.py, 24 Nov 2026). Fakes only: no Kaggle session, no GPU hour, no download. The notebook script itself is run on
this PC with a stand-in for huggingface_hub and the test-only echo engine, so its real code paths (report, hash proof, checkpoint, manifest) are exercised."""
import hashlib
import json
import os
import subprocess
import sys

import pytest

import computejobs
import computerouter
import kaggleworker


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(computejobs, "DIR", tmp_path / "jobs")
    monkeypatch.setattr(computerouter, "KAGGLE_DIR", tmp_path / "kaggle")
    monkeypatch.setattr(computerouter.config, "ROOT", tmp_path)
    monkeypatch.setattr(kaggleworker, "TWINS", tmp_path / "twins.json")
    monkeypatch.setattr(kaggleworker, "OUTPUTS", tmp_path / "kaggle_outputs")
    monkeypatch.setattr(kaggleworker.modelinventory, "load_cfg", lambda: {"never_scan": [str(tmp_path / "forbidden")], "licenses_ok_for_production": ["apache-2.0"],
                                                                          "licenses_never": ["cc-by-nc"]})
    (tmp_path / "data" / "compute" / "inputs").mkdir(parents=True)
    (tmp_path / "data" / "compute" / "inputs" / "bench.json").write_text(json.dumps([{"id": "a", "prompt": "one two three"}, {"id": "b", "prompt": "four five"}]))


ENV = {"enabled": True, "commercial_use_permitted": False, "owner_permitted_tasks": ["benchmark"], "weekly_gpu_hours": 30}


def owner_file(tmp_path, data=b"weights" * 100):
    p = tmp_path / "models" / "m.gguf"
    p.parent.mkdir(exist_ok=True)
    p.write_bytes(data)
    return p, hashlib.sha256(data).hexdigest(), len(data)


def hf(sha, size, lic="apache-2.0", name="m.gguf"):
    return lambda repo: {"cardData": {"license": lic}, "siblings": [{"rfilename": name, "lfs": {"sha256": sha, "size": size}}]}


def twin(tmp_path):
    p, sha, size = owner_file(tmp_path)
    return kaggleworker.verify_twin(p, "maker/model-GGUF", "m.gguf", fetch=hf(sha, size))


def job(data_class="public-test", task="benchmark", ref="data/compute/inputs/bench.json"):
    return computejobs.submit("twin:maker/model-GGUF/m.gguf", task, ref, environment="kaggle_gpu", data_class=data_class, timeout_s=1800)


# ---- public twins ----
def test_a_twin_is_kept_only_when_the_published_file_is_the_same_bytes_under_an_allowed_licence(tmp_path):
    p, sha, size = owner_file(tmp_path)
    ok = kaggleworker.verify_twin(p, "maker/model-GGUF", "m.gguf", fetch=hf(sha, size))
    assert ok["verified"] and kaggleworker.twins()[sha]["repo"] == "maker/model-GGUF"
    other = kaggleworker.verify_twin(p, "maker/model-GGUF", "m.gguf", fetch=hf("0" * 64, size))
    assert not other["verified"] and "differ" in other["why"]
    nc = kaggleworker.verify_twin(p, "maker/model-GGUF", "m.gguf", fetch=hf(sha, size, lic="cc-by-nc-4.0"))
    assert not nc["verified"] and "licence" in nc["why"]
    assert not kaggleworker.verify_twin(p, "maker/model-GGUF", "other.gguf", fetch=hf(sha, size))["verified"]
    assert len(kaggleworker.twins()) == 1  # nothing unverified is saved


def test_the_forbidden_folder_is_never_hashed(tmp_path):
    bad = tmp_path / "forbidden" / "m.gguf"
    bad.parent.mkdir()
    bad.write_bytes(b"x")
    with pytest.raises(computejobs.JobError):
        kaggleworker.verify_twin(bad, "maker/m", "m.gguf", fetch=lambda r: pytest.fail("no lookup"))


# ---- the gate ----
def test_the_owners_file_reaches_kaggle_only_as_a_verified_twin_for_a_permitted_personal_task(tmp_path):
    t = twin(tmp_path)
    m = kaggleworker.model_for(t)
    assert computerouter.kaggle_gate(m, {"task": "benchmark", "data_class": "public-test"}, ENV) == ("", "")
    assert computerouter.kaggle_gate({**m, "public_twin": {"verified": False}}, {"task": "benchmark", "data_class": "public-test"}, ENV)[0] == "BLOCKED"
    assert computerouter.kaggle_gate(m, {"task": "benchmark", "data_class": "production"}, ENV)[0] == "BLOCKED"
    assert computerouter.kaggle_gate(m, {"task": "scene-art", "data_class": "public-test"}, ENV)[0] == "BLOCKED_PENDING_TERMS_REVIEW"
    assert computerouter.kaggle_gate(m, {"task": "benchmark", "data_class": "public-test"}, {**ENV, "enabled": False})[0] == "BLOCKED"


# ---- the package ----
def test_the_package_is_private_on_a_t4_with_the_twins_hash_and_no_credential(tmp_path):
    t = twin(tmp_path)
    j = job()
    d = kaggleworker.prepare(j, t, "owner-name", competition="spaceship-titanic")
    meta = json.loads((d / "kernel-metadata.json").read_text())
    script = (d / "run.py").read_text()
    assert meta["is_private"] and meta["enable_gpu"] and meta["machine_shape"] == "NvidiaTeslaT4" and meta["competition_sources"] == ["spaceship-titanic"]
    assert meta["id"] == f"owner-name/studio-job-{j['id']}" and t["sha256"] in script and "maker/model-GGUF" in script
    assert not computejobs.SECRET.search(script + json.dumps(meta))
    with pytest.raises(computejobs.JobError):
        kaggleworker.prepare(j, {**t, "verified": False}, "owner-name")
    with pytest.raises(computejobs.JobError):
        kaggleworker.prepare(j, t, "Owner Name; rm")


def test_a_push_names_the_t4_and_a_time_limit_and_a_job_on_kaggle_is_not_pushed_twice(tmp_path):
    t = twin(tmp_path)
    j = job()
    kaggleworker.prepare(j, t, "owner-name")
    calls = []
    run = lambda cmd, **k: calls.append(cmd) or type("R", (), {"returncode": 0, "stdout": "pushed", "stderr": ""})()
    out = kaggleworker.submit(j, t, "owner-name", ENV, run=run)
    assert out["status"] == "PREPARING" and out["kaggle_ref"] == f"owner-name/studio-job-{j['id']}"
    assert calls[0][:3] == ["kaggle", "kernels", "push"] and "--accelerator" in calls[0] and "NvidiaTeslaT4" in calls[0] and calls[0][calls[0].index("-t") + 1] == "1800"
    kaggleworker.submit(computejobs.get(j["id"]), t, "owner-name", ENV, run=run)
    assert len(calls) == 1  # idempotent: the running job is not pushed again
    blocked = job(data_class="production", ref="data/compute/inputs/bench.json")
    assert kaggleworker.submit(blocked, t, "owner-name", ENV, run=run)["status"] == "BLOCKED" and len(calls) == 1


# ---- the notebook script, run here with stand-ins ----
def run_notebook(tmp_path, package, model_bytes, tag):
    fake = tmp_path / f"fakehf-{tag}" / "huggingface_hub"
    fake.mkdir(parents=True)
    src = tmp_path / f"src-{tag}.bin"
    src.write_bytes(model_bytes)
    (fake / "__init__.py").write_text("import os, shutil\n__version__ = 'fake'\n"
                                      "def hf_hub_download(repo, file, local_dir):\n    os.makedirs(local_dir, exist_ok=True)\n"
                                      f"    p = os.path.join(local_dir, file); shutil.copy({str(src)!r}, p); return p\n")
    w = tmp_path / f"work-{tag}"
    env = {**os.environ, "PYTHONPATH": str(fake.parent), "STUDIO_W": str(w), "STUDIO_MODEL_DIR": str(tmp_path / f"model-{tag}"), "STUDIO_TEST_ENGINE": "echo"}
    r = subprocess.run([sys.executable, str(package / "run.py")], env=env, capture_output=True, text=True, timeout=120)
    return r, w


def test_the_notebook_proves_the_model_runs_every_item_once_and_signs_its_outputs(tmp_path):
    t = twin(tmp_path)
    j = job()
    d = kaggleworker.prepare(j, t, "owner-name")
    r, w = run_notebook(tmp_path, d, b"weights" * 100, "ok")
    assert r.returncode == 0, r.stdout + r.stderr
    rep = json.loads((w / "report.json").read_text())
    rows = [json.loads(l) for l in (w / "results.jsonl").read_text().splitlines()]
    assert rep["finished"] and rep["model_file"]["matches_owner_file"] and [x["id"] for x in rows] == ["a", "b"] and rows[0]["text"] == "eerht owt eno"
    man = json.loads((w / "manifest.json").read_text())
    assert man["files"]["results.jsonl"] == kaggleworker.sha256_file(w / "results.jsonl")
    v = kaggleworker.verify(w, j)
    assert v["ok"], v["problems"]


def test_the_notebook_runs_nothing_when_the_downloaded_file_is_not_the_owners(tmp_path):
    t = twin(tmp_path)
    d = kaggleworker.prepare(job(), t, "owner-name")
    r, w = run_notebook(tmp_path, d, b"something else", "bad")
    rep = json.loads((w / "report.json").read_text())
    assert r.returncode == 1 and not rep["finished"] and not rep["model_file"]["matches_owner_file"] and not (w / "results.jsonl").exists()


def test_a_resumed_notebook_skips_the_answers_already_recovered(tmp_path):
    t = twin(tmp_path)
    j = job()
    computejobs._write({**j, "checkpoint": {"done": {"a": {"new_tokens": 3}}}})
    d = kaggleworker.prepare(computejobs.get(j["id"]), t, "owner-name")
    r, w = run_notebook(tmp_path, d, b"weights" * 100, "resume")
    assert r.returncode == 0 and [json.loads(l)["id"] for l in (w / "results.jsonl").read_text().splitlines()] == ["b"]
    assert kaggleworker.verify(w, computejobs.get(j["id"]))["ok"]  # "a" is accounted for by the checkpoint


# ---- after the session ----
class FakeKaggle:
    """kernels status / output with a prepared output folder; output copies files like the real CLI."""
    def __init__(self, status, files):
        self.status_text, self.files, self.calls = status, files, []

    def __call__(self, cmd, **k):
        self.calls.append(cmd)
        out = ""
        if cmd[1:3] == ["kernels", "status"]:
            out = f'{cmd[3]} has status "{self.status_text}"'
        elif cmd[1:3] == ["kernels", "output"]:
            dest = cmd[cmd.index("-p") + 1]
            for name, data in self.files.items():
                open(os.path.join(dest, name), "wb").write(data)
        elif cmd[1:3] == ["kernels", "push"]:
            out = "pushed"
        return type("R", (), {"returncode": 0, "stdout": out, "stderr": ""})()


def finished_outputs(tmp_path, t, j, tag="ok"):
    d = kaggleworker.prepare(j, t, "owner-name")
    r, w = run_notebook(tmp_path, d, b"weights" * 100, tag)
    assert r.returncode == 0
    return {n: (w / n).read_bytes() for n in ("report.json", "results.jsonl", "manifest.json")}


def pushed(tmp_path, t):
    j = job()
    kaggleworker.prepare(j, t, "owner-name")
    return kaggleworker.submit(j, t, "owner-name", ENV, run=FakeKaggle("", {}))


def test_a_finished_session_is_retrieved_into_a_new_folder_verified_and_completed(tmp_path):
    t = twin(tmp_path)
    j = pushed(tmp_path, t)
    files = finished_outputs(tmp_path, t, j)
    assert kaggleworker.poll(j["id"], run=FakeKaggle("KernelWorkerStatus.RUNNING", {}))["status"] == "MODEL_LOADING"
    done = kaggleworker.poll(j["id"], run=FakeKaggle("KernelWorkerStatus.COMPLETE", files))
    assert done["status"] == "COMPLETED" and set(done["checkpoint"]["done"]) == {"a", "b"} and done["output"]["sha256"]["results.jsonl"]
    assert kaggleworker.poll(j["id"], run=FakeKaggle("KernelWorkerStatus.COMPLETE", files))["status"] == "COMPLETED"  # a finished job is never fetched again
    assert len(list((kaggleworker.OUTPUTS / j["id"]).iterdir())) == 1


def test_a_tampered_output_is_never_completed(tmp_path):
    t = twin(tmp_path)
    j = pushed(tmp_path, t)
    files = finished_outputs(tmp_path, t, j)
    files["results.jsonl"] = files["results.jsonl"].replace(b"eerht", b"XXXXX")
    out = kaggleworker.poll(j["id"], run=FakeKaggle("KernelWorkerStatus.COMPLETE", files))
    assert out["status"] == "FAILED" and "manifest" in out["history"][-1][2]


def test_an_expired_session_keeps_what_it_finished_and_recovery_runs_only_the_rest(tmp_path):
    t = twin(tmp_path)
    j = pushed(tmp_path, t)
    files = finished_outputs(tmp_path, t, j)
    first = files["results.jsonl"].splitlines(keepends=True)[0]
    partial = {"results.jsonl": first, "report.json": files["report.json"]}  # cut before the manifest was written
    out = kaggleworker.poll(j["id"], run=FakeKaggle("KernelWorkerStatus.CANCEL_ACKNOWLEDGED", partial))
    assert out["status"] == "INTERRUPTED" and set(out["checkpoint"]["done"]) == {"a"}
    fk = FakeKaggle("", {})
    back = kaggleworker.recover(j["id"], t, "owner-name", ENV, run=fk)
    assert back["status"] == "PREPARING" and any(c[1:3] == ["kernels", "push"] for c in fk.calls)
    assert '["a"]' in (computerouter.KAGGLE_DIR / j["id"] / "run.py").read_text()  # the new package skips the recovered answer
    assert len(list((kaggleworker.OUTPUTS / j["id"]).iterdir())) == 1  # the partial retrieval stays where it was


def test_the_account_check_prints_no_credential():
    calls = []

    def run(cmd, **k):
        calls.append(cmd)
        outs = {"--version": "Kaggle CLI 2.2.5", "quota": '[{"resource": "GPU", "used": "1h"}]', "competitions": '[{"ref": "titanic"}]', "kernels": "[]"}
        return type("R", (), {"returncode": 0, "stdout": next(v for k_, v in outs.items() if k_ in cmd), "stderr": ""})()
    out = kaggleworker.check(run=run)
    assert out["auth"] and out["competitions"] == ["titanic"] and not any("print-access-token" in c or "config" in c for c in calls)


def test_a_production_request_is_never_handed_an_earlier_public_test_job():
    """24 Nov 2026: the job id left out the data class, so a production request got the public-test job (and its label) back."""
    a = computejobs.submit("twin:x/y", "benchmark", "inline:hi", environment="kaggle_gpu", data_class="public-test")
    b = computejobs.submit("twin:x/y", "benchmark", "inline:hi", environment="kaggle_gpu", data_class="production")
    assert a["id"] != b["id"] and computejobs.get(b["id"])["data_class"] == "production"


def test_a_loaded_model_is_recorded_as_loaded_and_a_report_without_that_stage_is_not_verified(tmp_path):
    """24 Nov 2026, first real Kaggle run: stage(name, **engine) crashed on the engine's own "name" key right after a successful load, so the report said
    load_failed while the answers came from the loaded model. The stage is now recorded, and verify() requires it."""
    t = twin(tmp_path)
    j = job()
    d = kaggleworker.prepare(j, t, "owner-name")
    r, w = run_notebook(tmp_path, d, b"weights" * 100, "stage")
    rep = json.loads((w / "report.json").read_text())
    assert r.returncode == 0 and [s["stage"] for s in rep["stages"]].count("model_loaded") == 1 and not rep["errors"]
    rep["stages"] = [s for s in rep["stages"] if s["stage"] != "model_loaded"]
    (w / "report.json").write_text(json.dumps(rep))
    man = json.loads((w / "manifest.json").read_text())
    man["files"]["report.json"] = kaggleworker.sha256_file(w / "report.json")
    (w / "manifest.json").write_text(json.dumps(man))
    assert "the report has no model_loaded stage" in kaggleworker.verify(w, j)["problems"]


def test_a_session_waiting_for_a_kaggle_gpu_is_not_recorded_as_running(tmp_path):
    """24 Nov 2026: a pushed session sat in KernelWorkerStatus.QUEUED for 20+ minutes; the status reader used to call that RUNNING."""
    t = twin(tmp_path)
    j = pushed(tmp_path, t)
    assert computerouter.KaggleAdapter({}, run=FakeKaggle("KernelWorkerStatus.QUEUED", {})).status("me/k") == "QUEUED"
    assert kaggleworker.poll(j["id"], run=FakeKaggle("KernelWorkerStatus.QUEUED", {}))["status"] == "PREPARING"


def test_a_session_cancelled_at_its_cap_after_finishing_is_completed_and_never_recovered(tmp_path):
    """25 Nov 2026, real test J: Kaggle reported CANCEL_ACKNOWLEDGED for a 150 s capped session whose notebook had already finished and signed all 5 answers;
    it was treated as interrupted and a recovery session spent ~2.6 GPU minutes skipping all 5."""
    t = twin(tmp_path)
    j = pushed(tmp_path, t)
    files = finished_outputs(tmp_path, t, j)
    out = kaggleworker.poll(j["id"], run=FakeKaggle("KernelWorkerStatus.CANCEL_ACKNOWLEDGED", files))
    assert out["status"] == "COMPLETED" and "time cap" in out["history"][-1][2] and set(out["checkpoint"]["done"]) == {"a", "b"}


def test_recovery_never_pushes_a_session_when_every_item_is_recovered(tmp_path):
    t = twin(tmp_path)
    j = pushed(tmp_path, t)
    computejobs.move(j["id"], "INTERRUPTED", "test", checkpoint={"done": {"a": {}, "b": {}}})
    fk = FakeKaggle("", {})
    with pytest.raises(computejobs.JobError):
        kaggleworker.recover(j["id"], t, "owner-name", ENV, run=fk)
    assert not any(c[1:3] == ["kernels", "push"] for c in fk.calls) and computejobs.get(j["id"])["status"] == "INTERRUPTED"
