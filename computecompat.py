"""Can this model run there? (24 Nov 2026.) A memory estimate per model and environment: weights + KV cache + the engine's own overhead, against the
environment's LIVE free memory (nvidia-smi, /proc/meminfo) or its verified spec (Kaggle). A model never "fits" because its file is smaller than the GPU:
the KV cache and the runtime are counted, and an estimate made without the model's layer data says so. Numbers are estimates, not measurements; the
router (computerouter.py) treats a fit as a candidate, and only a real run (`run.py compute smoke`) proves it."""
import subprocess

import modelinventory

GB = 1e9
RUNNABLE = ("llm", "vision-llm")  # adapters, VAEs and text encoders are parts of other pipelines, never run alone here
OLLAMA_FORMATS = ("gguf",)


def gpu_status(run=subprocess.run) -> dict:
    """The local NVIDIA GPU as nvidia-smi reports it now, or {"present": False, "why": ...}. Never invented."""
    try:
        q = run(["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu,compute_cap,driver_version",
                 "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10)
        if q.returncode != 0 or not q.stdout.strip():
            return {"present": False, "why": (q.stderr or "nvidia-smi gave no answer").strip()[:160]}
        name, total, used, free, util, cap, drv = [x.strip() for x in q.stdout.strip().splitlines()[0].split(",")]
        apps = run(["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10)
        users = [{"pid": int(a.split(",")[0]), "process": a.split(",")[1].strip().rsplit("/", 1)[-1][:40], "mib": int(a.split(",")[2])}
                 for a in apps.stdout.strip().splitlines() if a.count(",") >= 2]
        return {"present": True, "name": name, "total_gb": int(total) / 1024, "used_gb": int(used) / 1024, "free_gb": int(free) / 1024,
                "util_pct": int(util), "compute_cap": cap, "driver": drv, "users": users}
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        return {"present": False, "why": f"{type(e).__name__}: {e}"[:160]}


def ram_status(meminfo: str | None = None) -> dict:
    text = meminfo if meminfo is not None else open("/proc/meminfo").read()
    vals = {l.split(":")[0]: int(l.split()[1]) for l in text.splitlines() if l.split()[1:2] and l.split()[1].isdigit()}
    return {"total_gb": vals.get("MemTotal", 0) * 1024 / GB, "available_gb": vals.get("MemAvailable", 0) * 1024 / GB}


def kv_cache_gb(m: dict, ctx: int) -> tuple[float, bool]:
    """(GB, exact?) for keys and values at f16 over `ctx` tokens. Without layer data: 15% of the weights, marked as a guess."""
    num = lambda v: v if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 else None  # a per-layer array (some GGUFs) is not one number
    layers, kvh, hd = num(m.get("layers")), num(m.get("kv_heads")), num(m.get("head_dim"))
    if layers and kvh and hd:
        return 2 * layers * kvh * hd * ctx * 2 / GB, True
    return 0.15 * (m.get("bytes") or 0) / GB, False


def need(m: dict, ctx: int, device: str) -> dict:
    """Memory the model needs on one device at this context: weights, KV cache, engine overhead (CUDA context and compute buffers on a GPU)."""
    w = (m.get("bytes") or 0) / GB
    mc = m.get("context_length")
    use_ctx = min(ctx, mc) if isinstance(mc, int) and mc > 0 else ctx
    kv, exact = kv_cache_gb(m, use_ctx)
    overhead = (0.45 if device == "gpu" else 0.3) + 0.06 * w
    return {"weights_gb": round(w, 2), "kv_gb": round(kv, 2), "overhead_gb": round(overhead, 2), "total_gb": round(w + kv + overhead, 2),
            "context": use_ctx, "kv_exact": exact}


def _engine(m: dict, env: str, env_cfg: dict) -> str:
    """Why the model cannot be loaded there as it is (no conversion), or ""."""
    fmt = str(m.get("format") or "").split(" ")[0]
    if m.get("kind") not in RUNNABLE:
        return f"a {m.get('kind')} is a part of another pipeline, not run alone"
    if env in ("local_gpu", "local_cpu"):
        if m.get("source") == "ollama":
            return ""
        if fmt in OLLAMA_FORMATS:
            return "a GGUF file not imported into Ollama yet (ollama create from it; nothing is downloaded)"
        return f"{fmt} needs PyTorch transformers, which this PC's studio has not installed (convert to GGUF for Ollama)"
    if env == "kaggle_gpu":
        return "" if fmt in ("gguf", "safetensors") else f"{fmt} has no engine in the Kaggle worker"
    return "no engine"


def verdict(m: dict, env: str, env_cfg: dict, live: dict, ctx: int) -> dict:
    """{"status": fits | fits_with_cpu_offload | too_big | not_runnable | needs_import | unknown | not_configured, "why", "need"}."""
    if not env_cfg.get("enabled") and env != "kaggle_gpu":
        return {"status": "not_configured", "why": env_cfg.get("why", "switched off")}
    if not m.get("bytes"):
        return {"status": "unknown", "why": "no size known for this model"}
    why = _engine(m, env, env_cfg)
    if why and m.get("kind") not in RUNNABLE:
        return {"status": "not_runnable", "why": why}
    if env == "local_gpu":
        g = live.get("gpu") or {}
        if not g.get("present"):
            return {"status": "not_configured", "why": g.get("why", "no GPU found")}
        n = need(m, ctx, "gpu")
        ram = (live.get("ram") or {}).get("available_gb", 0)
        if n["total_gb"] <= g["free_gb"] * 0.95:
            st = "fits"
        elif n["weights_gb"] + n["kv_gb"] + 0.5 <= g["free_gb"] * 0.95 + ram * 0.8:
            st = "fits_with_cpu_offload"  # llama.cpp / Ollama keep the layers that do not fit on the CPU: slower, still runs
        else:
            st = "too_big"
        out = {"status": st, "need": n, "have_gb": round(g["free_gb"], 2), "why": f"needs ~{n['total_gb']} GB, {g['free_gb']:.2f} GB of VRAM free now"}
    elif env == "local_cpu":
        r = (live.get("ram") or {}).get("available_gb", 0)
        n = need(m, ctx, "cpu")
        st = "fits" if n["total_gb"] <= r * 0.85 else "too_big"
        out = {"status": st, "need": n, "have_gb": round(r, 2), "why": f"needs ~{n['total_gb']} GB, {r:.1f} GB of RAM available now"}
    elif env == "kaggle_gpu":
        cards = env_cfg.get("gpus") or []
        one = max((c["vram_gb"] for c in cards), default=0)
        total = sum(c["vram_gb"] * c.get("count", 1) for c in cards)
        p = m.get("params")  # the Kaggle worker loads the public Hugging Face model in fp16, not this PC's quantized file (24 Nov 2026 review)
        n = need({**m, "bytes": int(p * 2)} if isinstance(p, (int, float)) and p > 0 else m, ctx, "gpu")
        if n["total_gb"] <= one * 0.95:
            st = "fits"
        elif n["total_gb"] + 0.5 * (sum(c.get("count", 1) for c in cards) - 1) <= total * 0.95:
            st = "fits"  # split across the cards (llama.cpp tensor split, transformers device_map=auto)
        else:
            st = "too_big"
        out = {"status": st, "need": n, "have_gb": total, "why": f"needs ~{n['total_gb']} GB, {total:.0f} GB on {len(cards) and cards[0].get('count', 1)} x {cards[0]['name'] if cards else '?'} (spec, not live)"}
    else:
        return {"status": "not_configured", "why": "unknown environment"}
    if why and out["status"] != "too_big":
        out = {**out, "status": "needs_import", "why": why + "; memory: " + out["why"]}
    return out


def matrix(inv: dict | None = None, cfg: dict | None = None, live: dict | None = None, ctx: int | None = None) -> dict:
    cfg = cfg or modelinventory.load_cfg()
    inv = inv or modelinventory.load()
    live = live if live is not None else {"gpu": gpu_status(), "ram": ram_status()}
    ctx = ctx or cfg.get("default_context", 4096)
    rows = []
    for m in inv.get("models", []):
        if m.get("same_as"):
            continue
        rows.append({"id": m["id"], "name": m["name"], "kind": m.get("kind"), "params": m.get("params") or m.get("params_label"), "quantization": m.get("quantization"),
                     "gb": round((m.get("bytes") or 0) / GB, 2), "license": m.get("license"),
                     "env": {e: verdict(m, e, c, live, ctx) for e, c in cfg["environments"].items()}})
    return {"context": ctx, "live": live, "rows": rows}
