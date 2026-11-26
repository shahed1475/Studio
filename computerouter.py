"""Model and compute routing (24 Nov 2026, owner's order: use the models already downloaded across this PC, a VPS and Kaggle where permitted, and free
APIs separately). Three choices are kept apart: WHICH MODEL (task capability, quality, licence, content policy), WHERE IT RUNS (memory fit against live
VRAM/RAM, the environment's switch, quota, privacy, terms) and WHICH API PROVIDER (llm.py routes those; providers_view only reports them).
Adapters: Ollama on this PC (GPU or CPU, real runs), Kaggle (a notebook package is prepared; it is sent only for a task the owner has confirmed the
Kaggle terms allow, otherwise BLOCKED_PENDING_TERMS_REVIEW), VPS (none: deleted 17 Nov 2026). Nothing here calls a paid model."""
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path

import computecompat
import computejobs
import config
import modelinventory

OUTPUTS = config.ROOT / "data" / "compute" / "outputs"
KAGGLE_DIR = config.ROOT / "data" / "compute" / "kaggle"
CAPABILITY = {"text-generation": ("llm", "vision-llm"), "vision": ("vision-llm",), "chat": ("llm", "vision-llm")}
CONTENT_EXCLUDED = re.compile(r"(?i)nsfw|abliterat|heretic|uncensored|unfiltered")  # never for channel work: the studio's content rules (CLAUDE.md E)
SPEED = {("local_gpu", "fits"): 3.0, ("local_gpu", "fits_with_cpu_offload"): 1.6, ("local_cpu", "fits"): 1.0, ("kaggle_gpu", "fits"): 2.0}
SESSION_START_S = {"kaggle_gpu": 300}  # a notebook session must start and load before the first token


def _params_b(m: dict) -> float:
    p = m.get("params")
    if isinstance(p, (int, float)) and p > 0:
        return p / 1e9
    lab = str(m.get("params_label") or m.get("size_label") or "")
    mt = re.match(r"([\d.]+)\s*([BM])", lab, re.I)
    return float(mt.group(1)) / (1000 if mt and mt.group(2).upper() == "M" else 1) if mt else 0.0


NEVER_WORDS = {"research", "nc", "noncommercial", "ccbync", "evaluation"}  # 24 Nov 2026 review: "Qwen RESEARCH LICENSE" passed as "qwen"
GENERIC = {"license", "licence", "agreement", "terms", "of", "use", "community", "the", "and", "version"}


def _lic_words(text: str) -> set:
    """Whole words of a licence name without version numbers or generic words: "Apache License", "apache-2.0" and "Apache 2" all give {"apache"}."""
    return set(re.findall(r"[a-z]+", str(text).lower())) - GENERIC


def licence_ok(m: dict, data_class: str, cfg: dict) -> str:
    """Why the model's licence keeps it from this work ("" when it may be used). Unknown licences are refused for production."""
    lic = str(m.get("license") or "").lower()
    w = _lic_words(lic) | set(re.findall(r"[a-z]+", lic.replace("-", "")))  # "non-commercial" also as "noncommercial", "cc-by-nc" also as "ccbync"
    if w & NEVER_WORDS or {"non", "commercial"} <= w or any(_lic_words(x) <= w for x in cfg.get("licenses_never", []) if _lic_words(x)):
        return f"licence '{m.get('license')}' forbids commercial use (research or non-commercial)"
    if data_class != "production":
        return ""
    if not lic:
        return "licence unknown: not used for production until it is checked"
    if not any(_lic_words(x) and _lic_words(x) <= _lic_words(lic) for x in cfg.get("licenses_ok_for_production", [])):
        return f"licence '{str(m.get('license'))[:40]}' not on the production list in config/compute.json"
    return ""


def kaggle_gate(m: dict, req: dict, env_cfg: dict) -> tuple[str, str]:
    """(status, why) for sending this job to Kaggle: ("", "") when allowed. Never decided by guessing the terms."""
    if req.get("data_class") != "public-test":  # only data marked public may leave this PC; a missing or unknown class counts as production
        return "BLOCKED", f"{req.get('data_class') or 'unmarked'} data never goes to Kaggle (only public-test)"
    if m.get("private", True) and not (m.get("public_twin") or {}).get("verified"):  # 24 Nov 2026: the owner's file may run only through a public twin
        return "BLOCKED", "a private model (the owner's own GGUF or fine-tune) would have to be uploaded to Kaggle"  # its maker's identical file, proven by SHA-256
    if not env_cfg.get("commercial_use_permitted") and req.get("task") not in env_cfg.get("owner_permitted_tasks", []):
        return "BLOCKED_PENDING_TERMS_REVIEW", "Kaggle's terms allow personal, non-commercial use only; the owner has not confirmed this task is permitted"
    if not env_cfg.get("enabled"):
        return "BLOCKED", "the Kaggle worker is switched off in config/compute.json"
    if req.get("needs_hours", 0) > (env_cfg.get("weekly_gpu_hours") or 0):
        return "BLOCKED", "more GPU hours than the weekly quota"
    return "", ""


def route(req: dict, inv: dict | None = None, cfg: dict | None = None, live: dict | None = None) -> dict:
    """The best (model, environment) for `req`, or BLOCKED / BLOCKED_PENDING_TERMS_REVIEW with every candidate's reason.
    req: task, data_class (production | public-test), context, min_params_b, prefer (model ids), max_latency_s, priority, needs_checkpoint."""
    cfg = cfg or modelinventory.load_cfg()
    inv = inv or modelinventory.load()
    live = live if live is not None else {"gpu": computecompat.gpu_status(), "ram": computecompat.ram_status()}
    ctx = int(req.get("context") or cfg.get("default_context", 4096))
    kinds = CAPABILITY.get(req.get("task", "text-generation"), ())
    rejected, options = [], []
    for m in inv.get("models", []):
        if m.get("same_as") or m.get("kind") not in kinds:
            continue
        if req.get("data_class", "production") == "production" and CONTENT_EXCLUDED.search(m["name"]):
            rejected.append((m["id"], "*", "content policy: an uncensored or NSFW model is never used for channel work"))
            continue
        why = licence_ok(m, req.get("data_class", "production"), cfg)
        if why:
            rejected.append((m["id"], "*", why))
            continue
        if _params_b(m) < float(req.get("min_params_b") or 0):
            rejected.append((m["id"], "*", f"{_params_b(m):.1f}B parameters, below the {req.get('min_params_b')}B this task asks for"))
            continue
        changed = modelinventory.still_same(m)
        if changed:
            rejected.append((m["id"], "*", changed))
            continue
        for env, ec in cfg["environments"].items():
            if ec.get("paid"):  # a paid GPU or server is never chosen by the router (the owner's money rule)
                rejected.append((m["id"], env, "paid compute: never used by the router"))
                continue
            v = computecompat.verdict(m, env, ec, live, ctx)
            if v["status"] not in ("fits", "fits_with_cpu_offload"):
                rejected.append((m["id"], env, f"{v['status']}: {v.get('why', '')}"))
                continue
            if env == "kaggle_gpu":
                st, why = kaggle_gate(m, req, ec)
                if st:
                    rejected.append((m["id"], env, f"{st}: {why}"))
                    continue
            elif env == "local_gpu" and (live.get("gpu") or {}).get("util_pct", 0) > 85:
                rejected.append((m["id"], env, "the GPU is busy (over 85% in use)"))
                continue
            speed = SPEED.get((env, v["status"]), 0.5)
            wait = SESSION_START_S.get(env, 0)
            if req.get("max_latency_s") and wait > req["max_latency_s"]:
                rejected.append((m["id"], env, f"a {env} session needs ~{wait} s to start, over the {req['max_latency_s']} s allowed"))
                continue
            pref = 1 if m["id"] in (req.get("prefer") or []) else 0
            options.append({"model": m["id"], "name": m["name"], "environment": env, "verdict": v, "params_b": round(_params_b(m), 2),
                            "score": (pref, min(_params_b(m), float(req.get("max_params_b") or 99)), speed)})
    if options:
        best = max(options, key=lambda o: o["score"])
        return {"status": "ROUTED", **{k: v for k, v in best.items() if k != "score"}, "alternatives": len(options) - 1,
                "rejected": rejected[:60]}
    terms = [r for r in rejected if r[1] == "kaggle_gpu" and "BLOCKED_PENDING_TERMS_REVIEW" in r[2]]
    return {"status": "BLOCKED_PENDING_TERMS_REVIEW" if terms else "BLOCKED",  # only Kaggle could have run it, and its terms are not cleared for this task
            "why": "no model and environment can do this task now", "rejected": rejected[:60]}


# ---- adapters ----
class OllamaAdapter:
    """Runs a job on this PC's Ollama: on the GPU (Ollama offloads what does not fit) or on the CPU only (num_gpu 0). Real requests; no download."""

    def __init__(self, environment: str, url: str, post=None, get=None):
        import requests

        self.environment, self.url = environment, url.rstrip("/")
        self.post = post or (lambda path, body, timeout: requests.post(self.url + path, json=body, timeout=timeout))
        self.get = get or (lambda path: requests.get(self.url + path, timeout=10))

    def run_one(self, model: str, prompt: str, timeout_s: int, ctx: int) -> dict:
        opts = {"num_ctx": ctx, "temperature": 0}
        if self.environment == "local_cpu":
            opts["num_gpu"] = 0
        r = self.post("/api/generate", {"model": model, "prompt": prompt, "stream": False, "options": opts, "keep_alive": "2m"}, timeout_s)
        r.raise_for_status()
        body = r.json()
        placed = {}
        try:
            for p in self.get("/api/ps").json().get("models", []):
                if p.get("name") == model or p.get("model") == model:
                    placed = {"size_gb": round(p.get("size", 0) / 1e9, 2), "vram_gb": round(p.get("size_vram", 0) / 1e9, 2)}
        except Exception:
            pass
        return {"text": body.get("response", ""), "load_s": round(body.get("load_duration", 0) / 1e9, 2), "eval_tokens": body.get("eval_count", 0),
                "tokens_per_s": round(body.get("eval_count", 0) / max(1e-9, body.get("eval_duration", 0) / 1e9), 2), "placement": placed}


def _items(job: dict) -> list[dict]:
    ref = job["input_ref"]
    if ref.startswith("inline:"):
        if computejobs.SECRET.search(ref):
            raise computejobs.JobError("an input contains something that looks like a key or token")
        return [{"id": "0", "prompt": ref[len("inline:"):]}]
    base = (config.ROOT / "data" / "compute" / "inputs").resolve()
    p = (config.ROOT / ref).resolve()
    if not p.is_relative_to(base):  # 24 Nov 2026 review: a prefix test let a sibling folder (studio-x) and settings.json through
        raise computejobs.JobError("an input reference must be a file in data/compute/inputs")
    items = json.loads(p.read_text())
    if not isinstance(items, list) or not all(isinstance(i, dict) and isinstance(i.get("id"), str) and isinstance(i.get("prompt"), str) for i in items):
        raise computejobs.JobError("an input file is a list of {id, prompt} strings")
    if computejobs.SECRET.search(json.dumps(items)):
        raise computejobs.JobError("an input contains something that looks like a key or token")
    return items


def execute(jid: str, adapter=None) -> dict:
    """Run (or resume) a local job item by item: every finished item is checkpointed, so a cut repeats only the item it stopped in."""
    job = computejobs.get(jid)
    if job["status"] in computejobs.FINAL:  # finished, failed or blocked: running it again needs a new submit, never a silent re-run
        return job
    if job["status"] in ("INTERRUPTED",):
        job = computejobs.move(jid, "RECOVERY_PENDING", "resuming from the checkpoint")
    if job["status"] in ("QUEUED", "RECOVERY_PENDING"):
        job = computejobs.move(jid, "PREPARING", "")
    if job["environment"] not in ("local_gpu", "local_cpu"):
        return computejobs.move(jid, "BLOCKED", f"no runner for {job['environment']} in this process")
    cfg = modelinventory.load_cfg()
    adapter = adapter or OllamaAdapter(job["environment"], cfg.get("ollama_url", "http://127.0.0.1:11434"))
    model = job["model"].split(":", 1)[1] if job["model"].startswith("ollama:") else job["model"]
    done = dict((job.get("checkpoint") or {}).get("done") or {})
    items = _items(job)
    if job.get("attempts", 0) > computejobs.MAX_ATTEMPTS:
        return computejobs.move(jid, "FAILED", f"stopped after {computejobs.MAX_ATTEMPTS} attempts")
    job = computejobs.move(jid, "MODEL_LOADING", f"{model} on {job['environment']}", pid=os.getpid(), heartbeat=time.time())
    started = False
    try:
        for it in items:
            if it["id"] in done:
                continue
            got = adapter.run_one(model, it["prompt"], job["timeout_s"], int(job["params"].get("context", 2048)))
            if not got["text"].strip():
                raise RuntimeError("the model returned an empty answer")
            if not started:
                job = computejobs.move(jid, "RUNNING", f"loaded in {got['load_s']} s; placement {got['placement']}")
                started = True
            done[it["id"]] = got
            job = computejobs.checkpoint(jid, {"done": done})
    except computejobs.JobError:  # a bug in the protocol is never dressed up as an interruption
        raise
    except Exception as e:  # a timeout or a lost server is an interruption (resume); anything else (a missing model, an empty answer) is a failure
        import requests

        transient = isinstance(e, (TimeoutError, ConnectionError, requests.Timeout, requests.ConnectionError))
        st = "INTERRUPTED" if transient else "FAILED"
        return computejobs.move(jid, st, f"{type(e).__name__}: {e}"[:300])
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    out = OUTPUTS / f"{jid}.json"
    text = json.dumps({"job": jid, "model": job["model"], "environment": job["environment"], "results": done}, indent=1)
    out.write_text(text)
    if job["status"] == "MODEL_LOADING":
        job = computejobs.move(jid, "RUNNING", "all items were already done")
    return computejobs.move(jid, "COMPLETED", "output verified (every item has text)", output={"file": str(out.relative_to(config.ROOT)),
                            "sha256": hashlib.sha256(text.encode()).hexdigest()[:16], "items": len(done)})


def recover(adapter=None) -> list[dict]:
    """Jobs a cut left mid-way: marked INTERRUPTED, then resumed from their checkpoint (local ones); a Kaggle job is only marked."""
    out = []
    for j in computejobs.interrupted():
        if j["status"] != "INTERRUPTED":
            try:
                j = computejobs.move(j["id"], "INTERRUPTED", "found unfinished after a restart")
            except computejobs.JobError:
                continue
        out.append(execute(j["id"], adapter) if j["environment"] in ("local_gpu", "local_cpu") else j)
    return out


class KaggleAdapter:
    """A Kaggle notebook as a temporary worker. prepare() writes a private kernel package (no credentials: the CLI reads its own); submit() runs it only
    when kaggle_gate allows. The notebook gets a PUBLIC model by name (Hugging Face) and writes results.jsonl item by item, so a session that expires
    is resumed with the finished ids. A notebook is never kept alive as an API server."""

    def __init__(self, env_cfg: dict, run=subprocess.run, owner: str = ""):
        self.cfg, self.run, self.owner = env_cfg, run, owner

    def prepare(self, job: dict, hf_repo: str) -> Path:
        if not re.fullmatch(r"[\w.-]+/[\w.-]+", hf_repo or ""):
            raise computejobs.JobError("a Kaggle job needs a public Hugging Face repo id; private models are never uploaded")
        d = KAGGLE_DIR / job["id"]
        d.mkdir(parents=True, exist_ok=True)
        done = sorted(((job.get("checkpoint") or {}).get("done") or {}).keys())
        (d / "kernel-metadata.json").write_text(json.dumps({"id": f"{self.owner or 'OWNER'}/studio-job-{job['id']}", "title": f"studio job {job['id']}",
                                                            "code_file": "run.py", "language": "python", "kernel_type": "script", "is_private": True,
                                                            "enable_gpu": True, "enable_internet": True}, indent=1))
        (d / "run.py").write_text(KAGGLE_SCRIPT.replace("__REPO__", hf_repo).replace("__DONE__", json.dumps(done))
                                  .replace("__ITEMS__", json.dumps(_items(job))).replace("__CTX__", str(int(job["params"].get("context", 2048)))))
        return d

    def submit(self, job: dict, model: dict, folder: Path) -> dict:
        """The gate reads the JOB's own data class and task (never a request the caller passes), and only the job's own package is pushed."""
        st, why = kaggle_gate(model, {"task": job["task"], "data_class": job.get("data_class")}, self.cfg)
        if Path(folder).resolve() != (KAGGLE_DIR / job["id"]).resolve():
            st, why = st or "BLOCKED", why or "the package folder is not this job's own"
        if st:
            return computejobs.move(job["id"], st, why) if job["status"] == "QUEUED" else job
        acc = ["--accelerator", self.cfg["accelerator"]] if self.cfg.get("accelerator") else []  # Kaggle CLI 2.2.5: T4 x2 is NvidiaTeslaT4
        cap = ["-t", str(int(job.get("timeout_s") or 3600))]  # a finite session: Kaggle stops it at this many seconds
        r = self.run(["kaggle", "kernels", "push", "-p", str(folder), *acc, *cap], capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            return computejobs.move(job["id"], "FAILED", f"kaggle push failed: {(r.stderr or r.stdout)[:200]}")
        return computejobs.move(job["id"], "PREPARING", "pushed to Kaggle; the session starts there")

    def status(self, kernel_ref: str) -> str:
        r = self.run(["kaggle", "kernels", "status", kernel_ref], capture_output=True, text=True, timeout=60)
        s = (r.stdout or "").lower()
        # 24 Nov 2026: a QUEUED session (waiting for a Kaggle GPU, 20+ minutes seen) is not running: it is reported as itself
        return "QUEUED" if "queued" in s else "RUNNING" if "running" in s else "COMPLETED" if "complete" in s else "INTERRUPTED" if "cancel" in s or "error" in s else "UNKNOWN"


KAGGLE_SCRIPT = '''# studio job: generated by computerouter.KaggleAdapter; no credentials inside; results.jsonl is the checkpoint
import json, os, torch
from transformers import AutoModelForCausalLM, AutoTokenizer
ITEMS = __ITEMS__
DONE = set(__DONE__)
out = "/kaggle/working/results.jsonl"
if os.path.exists(out):
    DONE |= {json.loads(l)["id"] for l in open(out)}
tok = AutoTokenizer.from_pretrained("__REPO__")
model = AutoModelForCausalLM.from_pretrained("__REPO__", torch_dtype=torch.float16, device_map="auto")
for it in ITEMS:
    if it["id"] in DONE:
        continue
    ids = tok(it["prompt"], return_tensors="pt", truncation=True, max_length=__CTX__).to(model.device)
    gen = model.generate(**ids, max_new_tokens=256, do_sample=False)
    text = tok.decode(gen[0][ids["input_ids"].shape[1]:], skip_special_tokens=True)
    with open(out, "a") as f:
        f.write(json.dumps({"id": it["id"], "text": text}) + "\\n")
'''


def providers_view() -> dict:
    """Free API providers as llm.py sees them (no keys shown): separate from GPU compute. Paid models are never chosen here."""
    import freeart
    import llm

    cfg = llm.load_config()
    now = dt.datetime.now(dt.timezone.utc)
    return {"paid_models_allowed": llm.paid_allowed(cfg), "free_models_on": bool(cfg.get("free")), "free_review": bool(cfg.get("free_review")),
            "gemini_key_saved": bool(llm.gemini_key()), "owner_provider_on": llm.extra_cfg() is not None,
            "openrouter_refused": bool(llm.openrouter_refused(now, llm.api_key())) if llm.api_key() else None,
            "cloudflare_account_spent_today": freeart.account_exhausted(now), "cloudflare_pictures_used_today": round(freeart.used_today(now.strftime("%Y-%m-%d")), 1),
            "judges_sharing_the_picture_account": llm.picture_sharing_models(),
            "note": "API providers are chosen by llm.py (judges.py for video reviews); this view only reports them"}


def _job_summary(j: dict) -> dict:
    """What the browser may see of a job: no input, no answers, no paths (24 Nov 2026 review)."""
    return {"id": j["id"], "model": j["model"], "environment": j["environment"], "status": j["status"], "attempts": j.get("attempts", 0),
            "history": [h[:2] + [str(h[2])[:120]] for h in (j.get("history") or [])[-3:]], "items_done": len(((j.get("checkpoint") or {}).get("done") or {}))}


def view() -> dict:
    """Everything the dashboard's compute page shows; numbers that are not known stay None with their reason."""
    cfg = modelinventory.load_cfg()
    inv = modelinventory.load()
    live = {"gpu": computecompat.gpu_status(), "ram": computecompat.ram_status()}
    live["gpu"] = {k: v for k, v in live["gpu"].items() if k != "users"} | {"other_users": len(live["gpu"].get("users", []))}
    mx = computecompat.matrix(inv, cfg, {"gpu": computecompat.gpu_status(), "ram": live["ram"]})
    jobs = computejobs.all_jobs(30)
    last_ok = next((j for j in jobs if j["status"] == "COMPLETED"), None)
    return {"inventory_at": inv.get("at"), "models": len(inv.get("models", [])), "matrix": mx["rows"], "context": mx["context"], "live": live,
            "environments": {k: {kk: vv for kk, vv in v.items() if kk not in ("never_send",)} for k, v in cfg["environments"].items()},
            "jobs": [_job_summary(j) for j in jobs], "last_completed": _job_summary(last_ok) if last_ok else None, "interrupted": len(computejobs.interrupted()), "providers": providers_view()}
