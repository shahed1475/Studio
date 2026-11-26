"""Kaggle notebooks as temporary GPU workers for the owner's own downloaded models (24 Nov 2026, owner's order: run my models on Kaggle's GPU, not as an API).

Rules (read with docs/ and reports/KAGGLE_REMOTE_WORKER_2026-11-24.md):
- Kaggle's Terms of Use (22 Jun 2025) allow "internal, personal, non-commercial use"; the AUP bars activity unrelated to ML data science. A job runs only for a
  task the owner listed in config/compute.json kaggle_gpu.owner_permitted_tasks, only with data_class "public-test", and never for a channel asset:
  `commercial_use_permitted` stays false until Kaggle's written permission exists (computerouter.kaggle_gate decides, never this module).
- Nothing private leaves this PC. A model runs on Kaggle only through a PUBLIC TWIN: the same file its maker publishes under a licence on the production list,
  proven identical to the owner's file by SHA-256 and size (`verify_twin`, data/compute/public_twins.json). The notebook downloads the twin itself and refuses to
  run when the hash differs. No model file, script, voice or video is uploaded; the package holds no credential (scanned before every push).
- Finite sessions only: `kaggle kernels push --accelerator NvidiaTeslaT4 -t <seconds>`; one account, no keep-alive, no server, no tunnel.
- Checkpoints: results.jsonl is written item by item; a resumed package skips the finished ids; every retrieval goes to a NEW numbered folder (never overwritten)
  and is verified against the notebook's own manifest of SHA-256 hashes before the job is COMPLETED.
Commands (run.py): compute kaggle-check | kaggle-twin <local file> <hf repo> <file> | kaggle-test [twin] | kaggle-poll <job> | kaggle-recover <job>."""
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import urllib.request
from pathlib import Path

import computejobs
import computerouter
import config
import modelinventory

TWINS = config.ROOT / "data" / "compute" / "public_twins.json"
OUTPUTS = config.ROOT / "data" / "compute" / "kaggle_outputs"
INPUTS = config.ROOT / "data" / "compute" / "inputs"
TASK = "benchmark"  # a personal, non-commercial measurement of an open model; its outputs are numbers and sample answers, never channel material
ACCELERATOR = "NvidiaTeslaT4"  # Kaggle CLI 2.2.5 `kernels push --accelerator`: T4 x2 (the P100 was retired on 15 Sep 2026)
FILES_VERIFIED = ("report.json", "results.jsonl")


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cli(args: list[str], run=subprocess.run, timeout: int = 180):
    """The official Kaggle CLI (the owner's wrapper reads the token itself; it is never passed, printed or logged here)."""
    return run(["kaggle", *args], capture_output=True, text=True, timeout=timeout)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 24), b""):
            h.update(block)
    return h.hexdigest()


# ---- public twins ----
def _hf_model(repo: str) -> dict:
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
        raise computejobs.JobError("a public twin is a Hugging Face repo id like maker/name")
    with urllib.request.urlopen(f"https://huggingface.co/api/models/{repo}?blobs=true", timeout=30) as r:
        return json.loads(r.read())


def twins() -> dict:
    try:
        return json.loads(TWINS.read_text())
    except (OSError, ValueError):
        return {}


def verify_twin(local: str | Path, repo: str, filename: str, fetch=_hf_model) -> dict:
    """Prove the owner's file and the maker's published file are the same bytes. The record is kept only when SHA-256 and size match and the licence is on
    the production list; otherwise the reason is returned and nothing is saved."""
    local = Path(local).expanduser().resolve()
    cfg = modelinventory.load_cfg()
    if any(str(local).startswith(str(Path(p).expanduser())) for p in cfg.get("never_scan", [])):
        raise computejobs.JobError("that folder is never read")
    meta = fetch(repo)
    lic = str((meta.get("cardData") or {}).get("license") or "")
    sib = next((s for s in meta.get("siblings", []) if s.get("rfilename") == filename), None)
    if sib is None or not (sib.get("lfs") or {}).get("sha256"):
        return {"verified": False, "why": f"{filename} is not a published file of {repo} with a SHA-256"}
    got = sha256_file(local)
    size = local.stat().st_size
    ok_lic = computerouter.licence_ok({"license": lic}, "production", cfg)  # the strict check: the licence must be on the production list
    rec = {"verified": got == sib["lfs"]["sha256"] and size == sib["lfs"].get("size") and not ok_lic, "sha256": got, "bytes": size, "repo": repo,
           "file": filename, "licence": lic, "published_sha256": sib["lfs"]["sha256"], "published_bytes": sib["lfs"].get("size"),
           "local": str(local).replace(str(Path.home()), "~"), "checked": _now()}
    if ok_lic:
        rec["why"] = f"licence: {ok_lic}"
    elif not rec["verified"]:
        rec["why"] = "the owner's file and the published file differ (SHA-256 or size)"
    if rec["verified"]:
        all_ = twins()
        all_[got] = rec
        TWINS.parent.mkdir(parents=True, exist_ok=True)
        tmp = TWINS.with_suffix(".tmp")
        tmp.write_text(json.dumps(all_, indent=1))
        os.replace(tmp, TWINS)
    return rec


def model_for(twin: dict) -> dict:
    """The model as the router's gate sees it: the owner's file stays private; only its verified public twin may be fetched by Kaggle."""
    return {"id": f"twin:{twin['repo']}/{twin['file']}", "name": twin["file"], "kind": "llm", "license": twin["licence"], "private": True,
            "public_twin": {"verified": bool(twin.get("verified")), "repo": twin["repo"], "file": twin["file"], "sha256": twin["sha256"]}}


# ---- the notebook package ----
def prepare(job: dict, twin: dict, owner: str, competition: str = "", max_new: int = 160) -> Path:
    """A private script kernel in data/compute/kaggle/<job id>/: kernel-metadata.json and run.py. Refuses an unverified twin and anything that looks like a key."""
    if not twin.get("verified"):
        raise computejobs.JobError("only a verified public twin runs on Kaggle (the owner's file is never uploaded)")
    if not re.fullmatch(r"[a-z0-9-]{3,60}", owner or ""):
        raise computejobs.JobError("set kaggle_gpu.owner (the Kaggle username) in config/compute.json")
    if competition and not re.fullmatch(r"[a-z0-9-]{3,80}", competition):
        raise computejobs.JobError("a competition slug is lowercase letters, digits and hyphens")
    d = computerouter.KAGGLE_DIR / job["id"]
    d.mkdir(parents=True, exist_ok=True)
    done = sorted(((job.get("checkpoint") or {}).get("done") or {}).keys())
    kernel = {"id": f"{owner}/studio-job-{job['id']}", "title": f"studio job {job['id']}", "code_file": "run.py", "language": "python", "kernel_type": "script",
            "is_private": True, "enable_gpu": True, "enable_internet": True, "machine_shape": ACCELERATOR, "dataset_sources": [],
            "competition_sources": [competition] if competition else [], "kernel_sources": [], "model_sources": []}
    script = (TWIN_SCRIPT.replace("__JOB__", job["id"]).replace("__REPO__", twin["repo"]).replace("__FILE__", twin["file"])
              .replace("__SHA__", twin["sha256"]).replace("__SIZE__", str(int(twin["bytes"]))).replace("__ITEMS__", json.dumps(computerouter._items(job)))
              .replace("__DONE__", json.dumps(done)).replace("__MAXNEW__", str(int(max_new))).replace("__COMP__", competition))
    for text in (json.dumps(kernel), script):
        if computejobs.SECRET.search(text):
            raise computejobs.JobError("the package looks like it holds a key or token: not written")
    (d / "kernel-metadata.json").write_text(json.dumps(kernel, indent=1))  # Kaggle's kernel metadata, not a video record
    (d / "run.py").write_text(script)
    return d


def submit(job: dict, twin: dict, owner: str, env_cfg: dict, run=subprocess.run) -> dict:
    """Push the package (computerouter.KaggleAdapter.submit: the gate reads the job's own task and data class). A job already on Kaggle is not pushed twice."""
    if job["status"] in ("PREPARING", "MODEL_LOADING", "RUNNING", "CHECKPOINTED", "COMPLETED"):
        return job
    if job.get("attempts", 0) >= computejobs.MAX_ATTEMPTS:
        return computejobs.move(job["id"], "FAILED", f"stopped after {computejobs.MAX_ATTEMPTS} attempts") if job["status"] != "FAILED" else job
    folder = computerouter.KAGGLE_DIR / job["id"]
    out = computerouter.KaggleAdapter({**env_cfg, "accelerator": ACCELERATOR}, run=run, owner=owner).submit(job, model_for(twin), folder)
    if out["status"] == "PREPARING":  # remember where the session is (the kernel slug is derived from the job id, so a retry pushes a new version, not a new kernel)
        out["kaggle_ref"] = f"{owner}/studio-job-{job['id']}"
        computejobs._write(out)
    return out


# ---- after the session ----
def fetch(job: dict, run=subprocess.run) -> Path:
    """Download the kernel's output into a NEW folder data/compute/kaggle_outputs/<job>/v<n>-<time>/ (an earlier retrieval is never overwritten)."""
    base = OUTPUTS / job["id"]
    base.mkdir(parents=True, exist_ok=True)
    n = 1 + len([p for p in base.iterdir() if p.is_dir()])
    dest = base / f"v{n}-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    dest.mkdir()
    r = _cli(["kernels", "output", job["kaggle_ref"], "-p", str(dest), "-o"], run=run, timeout=600)
    (dest / "_fetch.txt").write_text(f"exit {r.returncode}\n{(r.stdout or '')[-2000:]}\n{(r.stderr or '')[-2000:]}")
    return dest


def verify(dest: Path, job: dict) -> dict:
    """Check the retrieved files against the notebook's own manifest; the model must be the owner's file (hash) and every answer non-empty."""
    out = {"ok": False, "problems": [], "files": {}, "done": {}}
    try:
        manifest = json.loads((dest / "manifest.json").read_text())
    except (OSError, ValueError):
        manifest = None
        out["problems"].append("no manifest.json (the session ended before its last step)")
    for name in FILES_VERIFIED:
        p = dest / name
        if not p.exists():
            out["problems"].append(f"{name} missing")
            continue
        out["files"][name] = sha256_file(p)
        if manifest and manifest.get("files", {}).get(name) != out["files"][name]:
            out["problems"].append(f"{name} does not match the manifest")
    try:
        rep = json.loads((dest / "report.json").read_text())
    except (OSError, ValueError):
        rep = {}
    out["report"] = rep
    for line in (dest / "results.jsonl").read_text().splitlines() if (dest / "results.jsonl").exists() else []:
        try:
            row = json.loads(line)
        except ValueError:
            out["problems"].append("a results line is not JSON (cut mid-write)")
            continue
        if str(row.get("text") or "").strip():
            out["done"][str(row["id"])] = {k: row.get(k) for k in ("new_tokens", "seconds", "tokens_per_s", "engine")}
        else:
            out["problems"].append(f"item {row.get('id')} has an empty answer")
    eng = (rep.get("engine") or {}).get("name")
    if not any(s.get("stage") == "model_loaded" for s in rep.get("stages") or []):
        out["problems"].append("the report has no model_loaded stage")
    if any(r.get("engine") != eng for r in out["done"].values()):
        out["problems"].append("an answer names another engine than the report")
    if not (rep.get("model_file") or {}).get("matches_owner_file"):
        out["problems"].append("the report does not prove the model file was the owner's (SHA-256)")
    want = {i["id"] for i in computerouter._items(job)}
    if not rep.get("finished"):
        out["problems"].append("the notebook did not reach its end")
    missing = want - set(out["done"]) - set(((job.get("checkpoint") or {}).get("done") or {}))
    if missing:
        out["problems"].append(f"items without an answer: {sorted(missing)}")
    out["ok"] = not out["problems"]
    return out


def poll(jid: str, run=subprocess.run) -> dict:
    """One look at a Kaggle job: status, then (finished or interrupted) retrieval and verification. Moves the job only along computejobs.NEXT."""
    job = computejobs.get(jid)
    if job is None or not job.get("kaggle_ref"):
        raise computejobs.JobError("no Kaggle job with that id")
    if job["status"] in computejobs.FINAL or job["status"] in ("INTERRUPTED", "RECOVERY_PENDING"):
        return job
    st = computerouter.KaggleAdapter({}, run=run).status(job["kaggle_ref"])
    if st == "RUNNING":
        return computejobs.move(jid, "MODEL_LOADING", "the Kaggle session is running") if job["status"] == "PREPARING" else job
    if st not in ("COMPLETED", "INTERRUPTED"):  # QUEUED (waiting for a Kaggle GPU) or UNKNOWN: nothing moves
        return job
    dest = fetch(job, run=run)
    v = verify(dest, job)
    rel = str(dest.relative_to(config.ROOT))
    if job["status"] == "PREPARING":
        job = computejobs.move(jid, "MODEL_LOADING", "the session ran on Kaggle")
    if v["ok"]:  # 25 Nov 2026: Kaggle cancelled a capped session (CANCEL_ACKNOWLEDGED) after the notebook had finished and signed every answer; that is
        # a finished job, not an interruption (the needless recovery session cost ~2.6 GPU minutes to skip 5 answers)
        eng = (v["report"].get("engine") or {}).get("name", "?")
        total = {**((job.get("checkpoint") or {}).get("done") or {}), **v["done"]}
        computejobs.move(jid, "RUNNING", f"the report shows the owner's model file loaded ({eng})")
        computejobs.checkpoint(jid, {"done": total, "retrieved": rel})
        how = "" if st == "COMPLETED" else "; Kaggle ended the session at its time cap after the notebook had finished"
        return computejobs.move(jid, "COMPLETED", f"{len(v['done'])} new answers this session, {len(total)} in all, verified{how}",
                                output={"folder": rel, "sha256": v["files"], "gpu": (v["report"].get("environment") or {}).get("gpus"),
                                        "engine": v["report"].get("engine")})
    keep = {**((job.get("checkpoint") or {}).get("done") or {}), **v["done"]}
    if st == "COMPLETED":  # the session finished but its files do not prove the work: never COMPLETED
        return computejobs.move(jid, "FAILED", "retrieved but not verified: " + "; ".join(v["problems"])[:250], checkpoint={"done": keep, "retrieved": rel, "at": _now()})
    return computejobs.move(jid, "INTERRUPTED", f"the Kaggle session ended early; {len(v['done'])} answers recovered; " + "; ".join(v["problems"])[:200],
                            checkpoint={"done": keep, "retrieved": rel, "at": _now()})


def recover(jid: str, twin: dict, owner: str, env_cfg: dict, competition: str = "", run=subprocess.run, timeout_s: int | None = None) -> dict:
    """An interrupted job gets a NEW package that skips the answers already recovered, and is pushed again (never restarted from zero). timeout_s: a session
    that expired at its time cap may be given a longer one (recorded in its history)."""
    job = computejobs.get(jid)
    if job["status"] != "INTERRUPTED":
        return job
    left = {i["id"] for i in computerouter._items(job)} - set(((job.get("checkpoint") or {}).get("done") or {}))
    if not left:  # nothing to run: never push a session (GPU quota) only to skip finished answers
        raise computejobs.JobError("every item is already recovered: nothing to run on Kaggle")
    more = {"timeout_s": int(timeout_s)} if timeout_s and int(timeout_s) > int(job.get("timeout_s") or 0) else {}
    job = computejobs.move(jid, "RECOVERY_PENDING", f"resuming after {len(((job.get('checkpoint') or {}).get('done') or {}))} answers"
                           + (f"; time cap {job.get('timeout_s')} -> {more['timeout_s']} s" if more else ""), **more)
    prepare(job, twin, owner, competition)
    return submit(job, twin, owner, env_cfg, run=run)


def check(run=subprocess.run) -> dict:
    """Read-only account check: CLI version, login (through a quota call), quota, entered competitions, own notebooks. Prints no credential."""
    out = {}
    v = _cli(["--version"], run=run, timeout=30)
    out["cli"] = (v.stdout or "").strip()
    q = _cli(["quota", "--format", "json"], run=run, timeout=60)
    out["auth"] = q.returncode == 0
    try:
        out["quota"] = json.loads(q.stdout)
    except ValueError:
        out["quota"] = (q.stdout or q.stderr or "")[-300:]
    c = _cli(["competitions", "list", "--group", "entered", "--format", "json"], run=run, timeout=60)
    try:
        out["competitions"] = [x.get("ref") for x in json.loads(c.stdout)]
    except ValueError:
        out["competitions"] = (c.stdout or c.stderr or "")[-300:]
    k = _cli(["kernels", "list", "--mine", "--format", "json"], run=run, timeout=60)
    try:
        out["kernels"] = len(json.loads(k.stdout))
    except ValueError:
        out["kernels"] = (k.stdout or k.stderr or "")[-300:]
    return out


TWIN_SCRIPT = r'''# studio job __JOB__: written by kaggleworker.py (Story Studio). No credential inside.
# A personal, non-commercial benchmark of a public open model (Kaggle's terms): its output is numbers and sample answers, never channel material.
import glob, hashlib, json, os, platform, resource, shutil, subprocess, sys, time
JOB, REPO, FILE, SHA, SIZE = "__JOB__", "__REPO__", "__FILE__", "__SHA__", __SIZE__
ITEMS, DONE, MAX_NEW, COMP = __ITEMS__, set(__DONE__), __MAXNEW__, "__COMP__"
W = os.environ.get("STUDIO_W", "/kaggle/working"); os.makedirs(W, exist_ok=True)
MODEL_DIR = os.environ.get("STUDIO_MODEL_DIR", "/tmp/model")  # outside /kaggle/working: the 2.5 GB file is never saved as output
RES, REP = os.path.join(W, "results.jsonl"), os.path.join(W, "report.json")
T0 = time.time()
rep = {"job": JOB, "stages": [], "errors": [], "finished": False}

def save():
    tmp = REP + ".tmp"
    with open(tmp, "w") as f:
        json.dump(rep, f, indent=1)
    os.replace(tmp, REP)

def stage(_stage, **kw):  # 24 Nov 2026: this was stage(name, ...) and the engine's own "name" key crashed it right after a successful load
    rep["stages"].append({"stage": _stage, "t": round(time.time() - T0, 1), **kw}); save()
    print("STAGE", _stage, json.dumps(kw)[:400], flush=True)

def sh(cmd, timeout=120):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout).stdout.strip()
    except Exception as e:
        return "ERR " + repr(e)

def gpu_used():
    return sh("nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits")

def finish(code):
    rep["finished"] = code == 0
    rep["seconds_total"] = round(time.time() - T0, 1)
    rep["peak_ram_gb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6, 2)
    save()
    files = {n: hashlib.sha256(open(os.path.join(W, n), "rb").read()).hexdigest() for n in ("report.json", "results.jsonl") if os.path.exists(os.path.join(W, n))}
    with open(os.path.join(W, "manifest.json"), "w") as f:
        json.dump({"job": JOB, "files": files}, f, indent=1)
    sys.exit(code)

# 1. the machine
mem = {l.split(":")[0]: int(l.split()[1]) for l in open("/proc/meminfo") if l.split(":")[0] in ("MemTotal", "MemAvailable")}
env = {"python": sys.version.split()[0], "platform": platform.platform(), "cpus": os.cpu_count(),
       "nvidia_smi": sh("nvidia-smi --query-gpu=name,memory.total,memory.used,driver_version --format=csv,noheader"),
       "ram_total_gb": round(mem["MemTotal"] / 1e6, 2), "ram_available_gb": round(mem["MemAvailable"] / 1e6, 2),
       "disk_free_gb": round(shutil.disk_usage(W).free / 1e9, 1), "tmp_free_gb": round(shutil.disk_usage("/tmp").free / 1e9, 1)}
try:
    import torch
    env.update(torch=torch.__version__, torch_cuda=torch.version.cuda, cuda_available=torch.cuda.is_available(),
               gpus=[{"name": torch.cuda.get_device_name(i), "vram_gb": round(torch.cuda.get_device_properties(i).total_memory / 1e9, 2)} for i in range(torch.cuda.device_count())])
except Exception as e:
    env["torch_error"] = repr(e)[:300]
for lib in ("transformers", "accelerate", "huggingface_hub"):
    try:
        env[lib] = __import__(lib).__version__
    except Exception as e:
        env[lib] = "missing"
rep["environment"] = env
rep["inputs"] = [{"path": p, "bytes": os.path.getsize(p)} for p in sorted(glob.glob("/kaggle/input/**", recursive=True)) if os.path.isfile(p)][:200]
if COMP:
    cands = [i["path"] for i in rep["inputs"] if i["path"].endswith("/train.csv")]
    if cands:
        with open(cands[0]) as f:
            header = f.readline().strip().split(",")
            rows = sum(1 for _ in f)
        rep["competition_data"] = {"competition": COMP, "file": cands[0], "columns": header[:20], "rows": rows}
    else:
        rep["competition_data"] = {"competition": COMP, "error": "train.csv not found under /kaggle/input"}
stage("environment", gpus=env.get("gpus"), ram_total_gb=env["ram_total_gb"])

# 2. the owner's model, fetched from its maker and proven identical by SHA-256
try:
    from huggingface_hub import hf_hub_download
    t = time.time()
    path = hf_hub_download(REPO, FILE, local_dir=MODEL_DIR)
    got, size = hashlib.sha256(), os.path.getsize(path)
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 24), b""):
            got.update(b)
    got = got.hexdigest()
    rep["model_file"] = {"repo": REPO, "file": FILE, "sha256": got, "bytes": size, "expected_sha256": SHA, "matches_owner_file": got == SHA and size == SIZE,
                         "download_and_hash_s": round(time.time() - t, 1)}
    stage("model_fetched", matches=got == SHA and size == SIZE)
except Exception as e:
    rep["errors"].append("fetch: " + repr(e)[:500]); stage("model_fetch_failed"); finish(1)
if not rep["model_file"]["matches_owner_file"]:
    rep["errors"].append("the downloaded file is not the owner's file: nothing is run"); finish(1)

# 3. load it on the GPU: transformers (reads the GGUF, dequantised to float16), else llama.cpp built here with CUDA
gen = None
def load_transformers():
    r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "gguf>=0.10"], capture_output=True, text=True, timeout=600)
    if r.returncode:
        raise RuntimeError("pip gguf: " + r.stderr[-400:])
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    torch.cuda.reset_peak_memory_stats()
    tok = AutoTokenizer.from_pretrained(MODEL_DIR, gguf_file=FILE)
    model = AutoModelForCausalLM.from_pretrained(MODEL_DIR, gguf_file=FILE, torch_dtype=torch.float16).to("cuda:0").eval()
    pad = tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id
    def g(text):
        ids = tok("<|im_start|>user\n" + text + "<|im_end|>\n<|im_start|>assistant\n", return_tensors="pt").to("cuda:0")
        torch.cuda.synchronize(); t = time.time()
        with torch.no_grad():
            out = model.generate(**ids, max_new_tokens=MAX_NEW, do_sample=False, pad_token_id=pad)
        torch.cuda.synchronize()
        new = out[0][ids["input_ids"].shape[1]:]
        return tok.decode(new, skip_special_tokens=True).strip(), int(new.shape[0]), time.time() - t
    def peak():
        return round(torch.cuda.max_memory_allocated() / 1e9, 2)
    return g, peak, {"name": "transformers-gguf", "dtype": "float16 (dequantised from Q4_K_M)", "device": torch.cuda.get_device_name(0)}

def load_llamacpp():
    envb = dict(os.environ, CMAKE_ARGS="-DGGML_CUDA=on -DCMAKE_CUDA_ARCHITECTURES=75", FORCE_CMAKE="1")
    r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-cache-dir", "llama-cpp-python"], env=envb, capture_output=True, text=True, timeout=2400)
    if r.returncode:
        raise RuntimeError("pip llama-cpp-python: " + r.stderr[-600:])
    import llama_cpp
    if not llama_cpp.llama_supports_gpu_offload():
        raise RuntimeError("llama-cpp-python was built without GPU offload")
    llm = llama_cpp.Llama(model_path=os.path.join(MODEL_DIR, FILE), n_gpu_layers=-1, n_ctx=4096, verbose=False)
    def g(text):
        t = time.time()
        r = llm.create_chat_completion(messages=[{"role": "user", "content": text}], max_tokens=MAX_NEW, temperature=0)
        return r["choices"][0]["message"]["content"].strip(), int(r["usage"]["completion_tokens"]), time.time() - t
    return g, (lambda: None), {"name": "llama.cpp (llama-cpp-python, CUDA)", "dtype": "Q4_K_M as stored", "device": "cuda"}

LOADERS = (load_transformers, load_llamacpp)
if os.environ.get("STUDIO_TEST_ENGINE") == "echo":  # the studio's own tests on its PC only (tests/test_kaggleworker.py); never set on Kaggle
    LOADERS = ((lambda: ((lambda text: (text[::-1], len(text.split()), 0.01)), (lambda: 0.0), {"name": "echo (test)", "dtype": "-", "device": "cpu"})),)
for loader in LOADERS:
    t = time.time()
    try:
        gen, peak, engine = loader()  # only the loader itself can fail a load; the bookkeeping below never discards a loaded model
    except Exception as e:
        rep["errors"].append(getattr(loader, "__name__", "loader") + ": " + repr(e)[:700]); stage("load_failed", loader=getattr(loader, "__name__", "loader"))
        continue
    engine["load_s"] = round(time.time() - t, 1)
    engine["gpu_used_after_load_mib"] = gpu_used()
    rep["engine"] = engine
    stage("model_loaded", **engine)
    break
if gen is None:
    finish(1)

# 4. real inference, one item at a time (results.jsonl is the checkpoint)
for it in ITEMS:
    if it["id"] in DONE:
        continue
    try:
        text, n, secs = gen(it["prompt"])
    except Exception as e:
        rep["errors"].append(f"item {it['id']}: " + repr(e)[:400]); stage("item_failed", id=it["id"]); continue
    with open(RES, "a") as f:
        f.write(json.dumps({"id": it["id"], "prompt": it["prompt"], "text": text, "new_tokens": n, "seconds": round(secs, 2),
                            "tokens_per_s": round(n / secs, 2) if secs else None, "engine": rep["engine"]["name"]}) + "\n")
        f.flush(); os.fsync(f.fileno())
    stage("item", id=it["id"], tokens=n, seconds=round(secs, 2))
rep["engine"]["peak_gpu_allocated_gb"] = peak()
rep["engine"]["gpu_used_after_run_mib"] = gpu_used()
if not os.path.exists(RES):
    open(RES, "a").close()
finish(0 if not [e for e in rep["errors"] if e.startswith("item")] else 1)
'''
