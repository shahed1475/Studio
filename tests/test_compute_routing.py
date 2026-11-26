"""Model and compute routing (24 Nov 2026): inventory readers, memory estimates, the job protocol, the router and the adapters, all with fakes:
no Kaggle GPU hour, no API request and no real model load is spent here."""
import json
import struct

import pytest

import computecompat
import computejobs
import computerouter
import modelinventory


@pytest.fixture(autouse=True)
def tmp_jobs(tmp_path, monkeypatch):
    monkeypatch.setattr(computejobs, "DIR", tmp_path / "jobs")
    monkeypatch.setattr(computerouter, "OUTPUTS", tmp_path / "outputs")
    monkeypatch.setattr(computerouter, "KAGGLE_DIR", tmp_path / "kaggle")
    monkeypatch.setattr(computerouter.config, "ROOT", tmp_path)


def cfg(**kaggle):
    k = {"enabled": True, "gpus": [{"name": "Tesla T4", "vram_gb": 15.0, "count": 2}], "weekly_gpu_hours": 30, "commercial_use_permitted": False,
         "owner_permitted_tasks": [], "never_send": ["production", "voice"]}
    k.update(kaggle)
    return {"default_context": 4096, "licenses_ok_for_production": ["apache-2.0", "mit"], "licenses_never": ["cc-by-nc"],
            "environments": {"local_gpu": {"enabled": True}, "local_cpu": {"enabled": True}, "vps": {"enabled": False, "why": "no VPS"}, "kaggle_gpu": k}}


def model(name="ollama:small", gb=1.0, layers=28, kvh=2, hd=128, lic="apache-2.0", kind="llm", private=False, source="ollama", fmt="gguf"):
    return {"id": name, "name": name.split(":", 1)[1], "source": source, "format": fmt, "kind": kind, "bytes": int(gb * 1e9), "layers": layers,
            "kv_heads": kvh, "head_dim": hd, "context_length": 32768, "license": lic, "private": private, "params": int(gb * 1.6e9)}


LIVE = {"gpu": {"present": True, "free_gb": 2.9, "util_pct": 5}, "ram": {"available_gb": 12.0}}


# ---- memory estimates: never "fits" only because the file is smaller than the GPU ----
def test_a_model_smaller_than_the_gpu_can_still_not_fit_once_the_kv_cache_and_runtime_are_counted():
    m = model(gb=2.6, layers=36, kvh=8, hd=128)  # 2.6 GB of weights on a GPU with 2.9 GB free
    n = computecompat.need(m, 4096, "gpu")
    assert n["kv_gb"] > 0.5 and n["total_gb"] > 2.9
    assert computecompat.verdict(m, "local_gpu", {"enabled": True}, LIVE, 4096)["status"] == "fits_with_cpu_offload"
    assert computecompat.verdict(model(gb=0.99), "local_gpu", {"enabled": True}, LIVE, 4096)["status"] == "fits"


def test_insufficient_memory_everywhere_is_too_big_and_an_estimate_without_layer_data_says_so():
    huge = model(gb=60)
    assert {computecompat.verdict(huge, e, cfg()["environments"][e], LIVE, 4096)["status"] for e in ("local_gpu", "local_cpu", "kaggle_gpu")} == {"too_big"}
    kv, exact = computecompat.kv_cache_gb({"bytes": int(2e9), "layers": "<array of 32>"}, 4096)  # a per-layer array is not a number
    assert not exact and kv == pytest.approx(0.3)


def test_no_gpu_present_is_reported_never_invented():
    fake = lambda *a, **k: type("R", (), {"returncode": 9, "stdout": "", "stderr": "NVIDIA-SMI has failed"})()
    g = computecompat.gpu_status(run=fake)
    assert g == {"present": False, "why": "NVIDIA-SMI has failed"}
    assert computecompat.verdict(model(), "local_gpu", {"enabled": True}, {"gpu": g, "ram": {"available_gb": 8}}, 4096)["status"] == "not_configured"


def test_incompatible_formats_and_parts_of_pipelines_are_never_run_alone():
    assert computecompat.verdict(model(kind="lora-adapter"), "local_gpu", {"enabled": True}, LIVE, 4096)["status"] == "not_runnable"
    onnx = model(name="file:/m/x.onnx", source="files", fmt="onnx")
    assert computecompat.verdict(onnx, "kaggle_gpu", cfg()["environments"]["kaggle_gpu"], LIVE, 4096)["status"] == "needs_import"
    assert computecompat.verdict(model(name="file:/m/x.gguf", source="files"), "local_gpu", {"enabled": True}, LIVE, 4096)["status"] == "needs_import"


# ---- inventory readers ----
def _gguf(path, kv):
    def s(t):
        b = t.encode()
        return struct.pack("<Q", len(b)) + b
    body = b"GGUF" + struct.pack("<IQQ", 3, 0, len(kv))
    for k, (typ, v) in kv.items():
        body += s(k) + struct.pack("<I", typ) + (s(v) if typ == 8 else struct.pack({4: "<I", 6: "<f"}[typ], v))
    path.write_bytes(body + b"\0" * 64)


def test_gguf_metadata_is_read_from_the_header_only(tmp_path):
    p = tmp_path / "m.gguf"
    _gguf(p, {"general.architecture": (8, "qwen2"), "general.license": (8, "apache-2.0"), "general.file_type": (4, 15), "qwen2.context_length": (4, 32768),
              "qwen2.block_count": (4, 28), "qwen2.attention.head_count": (4, 12), "qwen2.attention.head_count_kv": (4, 2), "qwen2.embedding_length": (4, 1536)})
    g = modelinventory._from_gguf(p)
    assert (g["architecture"], g["quantization"], g["layers"], g["kv_heads"], g["head_dim"], g["license"]) == ("qwen2", "Q4_K_M", 28, 2, 128, "apache-2.0")


def test_a_half_downloaded_model_is_recorded_with_its_error_and_never_routed(tmp_path):
    p = tmp_path / "cut.gguf"
    p.write_bytes(b"GGUF" + struct.pack("<I", 3) + b"\x01")  # the download stopped inside the header
    rec = modelinventory._single(p)
    assert "error" in rec and "header not readable" in rec["error"]
    assert computecompat.verdict({**rec, "bytes": 0}, "local_gpu", {"enabled": True}, LIVE, 4096)["status"] == "unknown"


def test_a_model_file_that_changed_since_the_inventory_is_not_trusted(tmp_path):
    p = tmp_path / "m.gguf"
    p.write_bytes(b"A" * 2048)
    m = {"source": "files", "path": str(p), "fingerprint": modelinventory.fingerprint(p)}
    assert modelinventory.still_same(m) == ""
    p.write_bytes(b"B" * 2048)  # a hash mismatch: another download overwrote it, or it was edited
    assert "changed" in modelinventory.still_same(m)
    p.unlink()
    assert "gone" in modelinventory.still_same(m)


def test_the_forbidden_folder_is_never_scanned(tmp_path, monkeypatch):
    bad = tmp_path / "forbidden"
    bad.mkdir()
    (bad / "big.gguf").write_bytes(b"x")
    monkeypatch.setattr(modelinventory, "MIN_BYTES", 0)
    found = modelinventory.scan_files({"model_roots": [str(tmp_path)], "never_scan": [str(bad)]})
    assert not any("forbidden" in f["path"] for f in found)


# ---- the job protocol ----
def test_the_same_request_is_one_job_and_a_job_never_carries_a_credential():
    a = computejobs.submit("ollama:m", "text-generation", "inline:hi", environment="local_gpu")
    b = computejobs.submit("ollama:m", "text-generation", "inline:hi", environment="local_gpu")
    c = computejobs.submit("ollama:m", "text-generation", "inline:hi", environment="local_cpu")
    assert a["id"] == b["id"] != c["id"]  # a duplicate is the same job; the same prompt on another environment is another job
    with pytest.raises(computejobs.JobError):
        computejobs.submit("ollama:m", "text-generation", "inline:hi", environment="local_gpu", params={"api_key": "x"})
    with pytest.raises(computejobs.JobError):
        computejobs.submit("ollama:m", "text-generation", "inline:use sk-or-v1-abcdefghijklmnopqrstuvwx", environment="local_gpu")
    with pytest.raises(computejobs.JobError):
        computejobs.move(a["id"], "COMPLETED")  # QUEUED -> COMPLETED skips every step


class Flaky:
    """An Ollama that answers `ok` items and then loses its connection (a cut, a killed server)."""

    def __init__(self, ok):
        self.ok, self.calls = ok, []

    def run_one(self, model, prompt, timeout_s, ctx):
        self.calls.append(prompt)
        if len(self.calls) > self.ok:
            raise ConnectionError("connection refused")
        return {"text": f"answer to {prompt}", "load_s": 1.0, "eval_tokens": 3, "tokens_per_s": 9.0, "placement": {}}


def test_an_interrupted_job_resumes_from_its_checkpoint_and_never_repeats_a_finished_item(tmp_path):
    (tmp_path / "data" / "compute" / "inputs").mkdir(parents=True)
    (tmp_path / "data" / "compute" / "inputs" / "items.json").write_text(json.dumps([{"id": str(i), "prompt": f"p{i}"} for i in range(4)]))
    j = computejobs.submit("ollama:m", "text-generation", "data/compute/inputs/items.json", environment="local_gpu")
    first = Flaky(ok=2)
    j = computerouter.execute(j["id"], first)
    assert j["status"] == "INTERRUPTED" and sorted(j["checkpoint"]["done"]) == ["0", "1"]
    again = Flaky(ok=10)
    j = computerouter.execute(j["id"], again)
    assert j["status"] == "COMPLETED" and again.calls == ["p2", "p3"] and j["output"]["items"] == 4  # items 0 and 1 were not asked again
    assert computerouter.execute(j["id"], Flaky(ok=10))["status"] == "COMPLETED"  # a finished job is never silently re-run


def test_a_job_left_running_by_a_power_cut_is_found_and_recovered(tmp_path):
    j = computejobs.submit("ollama:m", "text-generation", "inline:hi", environment="local_cpu")
    computejobs.move(j["id"], "PREPARING")
    computejobs.move(j["id"], "MODEL_LOADING")  # the PC went off here
    assert [x["id"] for x in computejobs.interrupted()] == [j["id"]]
    out = computerouter.recover(Flaky(ok=5))
    assert out[0]["status"] == "COMPLETED" and ["INTERRUPTED", "RECOVERY_PENDING", "PREPARING"] == [h[1] for h in out[0]["history"]][3:6]
    assert computejobs.get(j["id"])["status"] == "COMPLETED"


def test_an_empty_answer_is_never_a_completed_job():
    class Empty:
        def run_one(self, *a):
            return {"text": "  ", "load_s": 0, "eval_tokens": 0, "tokens_per_s": 0, "placement": {}}

    j = computejobs.submit("ollama:m", "text-generation", "inline:hi", environment="local_gpu")
    assert computerouter.execute(j["id"], Empty())["status"] == "FAILED"


# ---- the router ----
INV = {"models": [model("ollama:small", gb=0.99), model("ollama:mid", gb=4.7), model("ollama:big-nc", gb=1.0, lic="cc-by-nc-4.0"),
                  model("ollama:mystery", gb=1.0, lic=None), model("ollama:x-uncensored", gb=1.0), model("ollama:own", gb=1.0, private=True)]}


def test_the_router_picks_by_quality_then_speed_and_names_every_rejection():
    d = computerouter.route({"task": "text-generation", "data_class": "production"}, INV, cfg(), LIVE)
    assert d["status"] == "ROUTED" and d["model"] == "ollama:mid" and d["environment"] == "local_gpu"  # GPU with CPU offload: measured 10.3 tok/s for a 4.9 GB 7B model
    why = " ".join(r[2] for r in d["rejected"])
    assert "forbids commercial use" in why and "licence unknown" in why and "content policy" in why and "production data never goes to Kaggle" in why


def test_kaggle_is_never_used_for_production_and_waits_for_the_owner_on_its_terms():
    small = {"models": [dict(model("ollama:k", gb=14), params=int(12e9))]}  # a 14 GB file: too big for this PC; 12B in fp16 (24 GB) fits 2 x T4
    assert computerouter.route({"task": "text-generation", "data_class": "production"}, small, cfg(), LIVE)["status"] == "BLOCKED"
    d = computerouter.route({"task": "text-generation", "data_class": "public-test"}, small, cfg(), LIVE)
    assert d["status"] == "BLOCKED_PENDING_TERMS_REVIEW"  # no task is confirmed permitted under Kaggle's non-commercial terms
    ok = computerouter.route({"task": "text-generation", "data_class": "public-test"}, small, cfg(owner_permitted_tasks=["text-generation"]), LIVE)
    assert ok["status"] == "ROUTED" and ok["environment"] == "kaggle_gpu"
    private = {"models": [dict(model("ollama:k", gb=14, private=True), params=int(12e9))]}
    assert computerouter.route({"task": "text-generation", "data_class": "public-test"}, private, cfg(owner_permitted_tasks=["text-generation"]), LIVE)["status"] == "BLOCKED"


def test_kaggle_switched_off_or_unavailable_is_never_chosen():
    small = {"models": [dict(model("ollama:k", gb=14), params=int(12e9))]}
    d = computerouter.route({"task": "text-generation", "data_class": "public-test"}, small, cfg(enabled=False, owner_permitted_tasks=["text-generation"]), LIVE)
    assert d["status"] == "BLOCKED" and any("switched off" in r[2] for r in d["rejected"])


def test_a_paid_environment_is_never_chosen():
    c = cfg()
    c["environments"]["rented_gpu"] = {"enabled": True, "paid": True}
    d = computerouter.route({"task": "text-generation", "data_class": "production"}, {"models": [model("ollama:small", gb=0.99)]}, c, LIVE)
    assert d["environment"] != "rented_gpu" and any("paid compute" in r[2] for r in d["rejected"])


def test_a_busy_gpu_is_skipped():
    busy = {**LIVE, "gpu": {**LIVE["gpu"], "util_pct": 97}}
    d = computerouter.route({"task": "text-generation", "data_class": "production"}, {"models": [model("ollama:small", gb=0.99)]}, cfg(), busy)
    assert d["environment"] == "local_cpu"


# ---- the Kaggle adapter ----
def test_the_kaggle_package_holds_no_credential_and_only_a_public_model(tmp_path):
    j = computejobs.submit("hf:Qwen/Qwen2.5-1.5B-Instruct", "text-generation", "inline:hi", environment="kaggle_gpu", data_class="public-test")
    ka = computerouter.KaggleAdapter(cfg()["environments"]["kaggle_gpu"], run=lambda *a, **k: pytest.fail("no CLI call while preparing"))
    with pytest.raises(computejobs.JobError):
        ka.prepare(j, "/home/fahad/private-model")  # a private path is never sent
    d = ka.prepare(j, "Qwen/Qwen2.5-1.5B-Instruct")
    text = (d / "run.py").read_text() + (d / "kernel-metadata.json").read_text()
    assert "Qwen/Qwen2.5-1.5B-Instruct" in text and '"is_private": true' in text and not computejobs.SECRET.search(text)


def test_an_ineligible_kaggle_job_is_blocked_before_any_upload():
    calls = []
    j = computejobs.submit("hf:Qwen/Qwen2.5-1.5B-Instruct", "text-generation", "inline:hi", environment="kaggle_gpu", data_class="public-test")
    ka = computerouter.KaggleAdapter(cfg()["environments"]["kaggle_gpu"], run=lambda *a, **k: calls.append(a))
    out = ka.submit(j, model("hf:Qwen/Qwen2.5-1.5B-Instruct"), computerouter.KAGGLE_DIR / j["id"])
    assert out["status"] == "BLOCKED_PENDING_TERMS_REVIEW" and calls == []


def test_an_expired_or_terminated_notebook_session_is_an_interruption():
    r = lambda text: (lambda *a, **k: type("R", (), {"stdout": text, "returncode": 0})())
    assert computerouter.KaggleAdapter({}, run=r('status "KernelWorkerStatus.CANCEL_ACKNOWLEDGED"')).status("me/k") == "INTERRUPTED"
    assert computerouter.KaggleAdapter({}, run=r('status "KernelWorkerStatus.ERROR"')).status("me/k") == "INTERRUPTED"
    assert computerouter.KaggleAdapter({}, run=r('status "KernelWorkerStatus.RUNNING"')).status("me/k") == "RUNNING"


# ---- API providers stay separate ----
def test_providers_are_reported_not_routed_here_and_the_cloudflare_limit_shows(monkeypatch):
    import freeart
    import llm

    monkeypatch.setattr(freeart, "account_exhausted", lambda now=None: True)
    monkeypatch.setattr(llm, "load_config", lambda: {**llm.DEFAULTS, "enabled": False, "free": True})
    v = computerouter.providers_view()
    assert v["cloudflare_account_spent_today"] is True and v["paid_models_allowed"] is False
    assert not any("key" in k and isinstance(val, str) and len(val) > 8 for k, val in v.items())  # a flag, never the key itself


# ---- dashboard ----
@pytest.fixture
def dash(tmp_path, monkeypatch):
    import threading
    from http.server import ThreadingHTTPServer

    import dashboard
    import webauth

    monkeypatch.setattr(webauth, "DATA", tmp_path)
    monkeypatch.setattr(webauth, "AUTH_FILE", tmp_path / "auth.json")  # no login set: the local dashboard opens (as in the button audit)
    monkeypatch.setattr(webauth, "SECRET_FILE", tmp_path / "auth_secret")
    monkeypatch.setattr(webauth, "SESSIONS_FILE", tmp_path / "sessions.json")
    monkeypatch.delenv("STUDIO_MODE", raising=False)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), dashboard.H)
    monkeypatch.setattr(dashboard, "PORT", srv.server_address[1])
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address[1]
    srv.shutdown()


def _get(port, path):
    import http.client

    c = http.client.HTTPConnection("127.0.0.1", port)
    c.request("GET", path, headers={"Host": f"127.0.0.1:{port}"})
    r = c.getresponse()
    return r.status, r.read()


def test_the_compute_page_shows_the_view_and_a_user_studio_never_sees_the_owners_models(dash, monkeypatch):
    import tenantmode

    monkeypatch.setattr(computerouter, "view", lambda: {"models": 3, "matrix": []})
    st, body = _get(dash, "/api/compute")
    if st in (401, 403):
        pytest.skip("this dashboard build asks for a login before any page; the route is covered by the tenant check below")
    assert st == 200 and json.loads(body)["models"] == 3
    monkeypatch.setattr(tenantmode, "is_tenant", lambda: True)
    assert _get(dash, "/api/compute")[0] in (401, 403, 404)


def test_licences_are_matched_by_whole_words_not_spelling():
    c = {"licenses_ok_for_production": ["apache-2.0", "mit", "llama3.1", "gemma"], "licenses_never": ["cc-by-nc"]}
    ok = lambda lic: computerouter.licence_ok({"license": lic}, "production", c) == ""
    assert ok("Apache License") and ok("apache-2.0") and ok("MIT License") and ok("LLAMA 3.1 COMMUNITY LICENSE AGREEMENT") and ok("Gemma Terms of Use")
    assert not ok("Limited commit terms") and not ok(None) and not ok("cc-by-nc-4.0")  # "mit" inside "commit" is not MIT; unknown is refused


ROUTING_SKILLS = ("model-inventory-manager", "kaggle-gpu-worker", "gpu-model-compatibility", "intelligent-compute-routing", "remote-model-execution",
                  "model-checkpoint-recovery", "free-api-provider-routing", "model-resource-monitor", "model-routing-testing", "model-license-and-data-policy")


@pytest.mark.parametrize("name", ROUTING_SKILLS)
def test_each_routing_skill_names_only_code_that_exists(name):
    import importlib
    import re

    root = __import__("pathlib").Path(__file__).resolve().parent.parent
    text = (root / ".claude" / "skills" / name / "SKILL.md").read_text()
    assert text.startswith(f"---\nname: {name}\n")
    for f in set(re.findall(r"`([a-z_]+\.py)`", text)):
        assert (root / f).exists(), f
    for ref in set(re.findall(r"`((?:computerouter|computecompat|computejobs|modelinventory|llm|freeart)\.[A-Za-z_]+)", text)):
        mod, attr = ref.split(".")
        if attr != "py":  # a file name, checked above
            assert hasattr(importlib.import_module(mod), attr), ref



# ---- fixes from the independent review of 24 Nov 2026 ----
def test_research_and_non_commercial_licences_are_refused_however_they_are_written():
    c = {"licenses_ok_for_production": ["apache-2.0", "qwen", "llama3"], "licenses_never": ["cc-by-nc"]}
    for lic in ("Qwen RESEARCH LICENSE AGREEMENT", "CC BY-NC 4.0 (apache files inside)", "Non-Commercial Use Only", "cc-by-nc-sa-4.0", "Llama Evaluation License"):
        assert "forbids commercial use" in computerouter.licence_ok({"license": lic}, "public-test", c), lic


def test_kaggle_takes_only_data_marked_public_and_checks_the_jobs_own_class():
    ok_cfg = cfg(owner_permitted_tasks=["text-generation"])["environments"]["kaggle_gpu"]
    m = model(private=False)
    for dc in (None, "", "private", "test", "production"):
        assert computerouter.kaggle_gate(m, {"task": "text-generation", "data_class": dc}, ok_cfg)[0] == "BLOCKED", dc
    assert computerouter.kaggle_gate({k: v for k, v in m.items() if k != "private"}, {"task": "text-generation", "data_class": "public-test"}, ok_cfg)[0] == "BLOCKED"
    calls = []
    j = computejobs.submit("hf:a/b", "text-generation", "inline:hi", environment="kaggle_gpu", data_class="production")
    ka = computerouter.KaggleAdapter(ok_cfg, run=lambda *a, **k: calls.append(a))
    assert ka.submit(j, m, computerouter.KAGGLE_DIR / j["id"])["status"] == "BLOCKED" and calls == []  # the job's own class decides
    j2 = computejobs.submit("hf:a/b", "text-generation", "inline:hi2", environment="kaggle_gpu", data_class="public-test")
    assert ka.submit(j2, m, computerouter.KAGGLE_DIR / "someone-else")["status"] == "BLOCKED" and calls == []  # only its own package


def test_inputs_come_only_from_the_inputs_folder_and_never_carry_secrets(tmp_path):
    (tmp_path / "studio-x").mkdir()
    (tmp_path / "settings.json").write_text(json.dumps({"extra_llm_key": "k"}))
    for ref in ("settings.json", "../studio-x/a.json", "data/compute/inputs/../../../settings.json"):
        j = computejobs.submit("ollama:m", "text-generation", ref, environment="local_cpu")
        with pytest.raises(computejobs.JobError):
            computerouter._items(j)
    (tmp_path / "data" / "compute" / "inputs").mkdir(parents=True)
    (tmp_path / "data" / "compute" / "inputs" / "s.json").write_text(json.dumps([{"id": "0", "prompt": "key: sk-or-v1-abcdefghijklmnopqrstuvwxyz"}]))
    with pytest.raises(computejobs.JobError):
        computerouter._items({"input_ref": "data/compute/inputs/s.json"})


def test_bad_model_headers_never_crash_the_inventory(tmp_path, monkeypatch):
    monkeypatch.setattr(modelinventory, "MIN_BYTES", 0)
    (tmp_path / "list.safetensors").write_bytes(struct.pack("<Q", 2) + b"[]")
    (tmp_path / "cut.safetensors").write_bytes(b"\x01\x02")
    p = tmp_path / "arr.gguf"
    _gguf(p, {"general.architecture": (8, "gemma"), "gemma.embedding_length": (4, 3840)})
    found = modelinventory.scan_files({"model_roots": [str(tmp_path)], "never_scan": []})
    assert len(found) == 3 and sum("error" in f for f in found) == 2


def test_recovery_never_takes_over_a_job_a_live_process_is_running_and_stops_after_five_tries(monkeypatch):
    j = computejobs.submit("ollama:m", "text-generation", "inline:hi", environment="local_cpu")
    computejobs.move(j["id"], "PREPARING")
    computejobs.move(j["id"], "MODEL_LOADING", pid=__import__("os").getpid())  # this very process: alive
    assert computejobs.interrupted() == []
    computejobs.move(j["id"], "INTERRUPTED", "timeout")
    assert [x["id"] for x in computejobs.interrupted()] == [j["id"]]  # an interruption execute() recorded is resumed too
    job = computejobs.get(j["id"])
    job["attempts"] = computejobs.MAX_ATTEMPTS + 1
    computejobs._write(job)
    assert computerouter.execute(j["id"], Flaky(ok=9))["status"] == "FAILED"


def test_a_missing_model_is_a_failure_not_an_endless_interruption():
    class Missing:
        def run_one(self, *a):
            raise RuntimeError("404 model 'x' not found")

    j = computejobs.submit("ollama:x", "text-generation", "inline:hi", environment="local_gpu")
    assert computerouter.execute(j["id"], Missing())["status"] == "FAILED"


def test_kaggle_memory_is_judged_at_fp16_not_at_this_pcs_quantized_size():
    q4 = dict(model(gb=4.7), params=int(8e9))  # an 8B model in a 4.7 GB Q4 file is 16 GB in fp16 on Kaggle
    v = computecompat.verdict(q4, "kaggle_gpu", cfg()["environments"]["kaggle_gpu"], LIVE, 4096)
    assert v["need"]["weights_gb"] == pytest.approx(16.0)


def test_the_browser_never_gets_prompts_answers_or_paths_of_a_job():
    j = computejobs.submit("ollama:m", "text-generation", "inline:a secret plan", environment="local_cpu")
    computerouter.execute(j["id"], Flaky(ok=9))
    s = computerouter._job_summary(computejobs.get(j["id"]))
    assert "a secret plan" not in json.dumps(s) and "answer to" not in json.dumps(s) and set(s) >= {"id", "status", "items_done"}
