"""Read-only inventory of the models already on this PC (24 Nov 2026, owner's order: "discover my existing models"). Never copies, moves or
downloads a model: Ollama is asked through its API (/api/tags, /api/show); GGUF and safetensors files are read only in their metadata headers; a
fingerprint is the size, the change time and a SHA-256 of the first megabyte (a full hash of a 5 GB file is a separate, explicit step).
`python run.py compute inventory` writes data/compute/models.json (not in git: it holds paths)."""
import datetime as dt
import hashlib
import json
import os
import re
import struct
from pathlib import Path

import config

CFG_FILE = config.ROOT / "config" / "compute.json"
OUT = config.ROOT / "data" / "compute" / "models.json"
HEAD = 1 << 20
MIN_BYTES = 50 * 1000 * 1000  # smaller files are tokenizers, configs and LoRA bits, not models


def load_cfg() -> dict:
    return json.loads(CFG_FILE.read_text())


def _forbidden(path: Path, cfg: dict) -> bool:
    p = str(path.resolve())
    return any(p == str(Path(f).expanduser()) or p.startswith(str(Path(f).expanduser()) + os.sep) for f in cfg.get("never_scan", []))


def fingerprint(path: Path) -> dict:
    st = path.stat()
    with open(path, "rb") as f:
        head = hashlib.sha256(f.read(HEAD)).hexdigest()[:16]
    return {"bytes": st.st_size, "mtime": int(st.st_mtime), "head_sha256": head}


# ---- GGUF metadata (https://github.com/ggml-org/ggml/blob/master/docs/gguf.md): header, then key/value pairs; tensors are never read ----
_SCALAR = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f", 7: "<?", 10: "<Q", 11: "<q", 12: "<d"}
GGUF_FILE_TYPES = {0: "F32", 1: "F16", 2: "Q4_0", 3: "Q4_1", 7: "Q8_0", 8: "Q5_0", 9: "Q5_1", 10: "Q2_K", 11: "Q3_K_S", 12: "Q3_K_M", 13: "Q3_K_L",
                   14: "Q4_K_S", 15: "Q4_K_M", 16: "Q5_K_S", 17: "Q5_K_M", 18: "Q6_K", 32: "BF16"}


def _read(f, fmt):
    n = struct.calcsize(fmt)
    b = f.read(n)
    if len(b) != n:
        raise ValueError("truncated GGUF header")
    return struct.unpack(fmt, b)[0]


def _string(f, keep=True):
    n = _read(f, "<Q")
    if n > 1 << 24:
        raise ValueError("implausible string length in GGUF header")
    if not keep:
        f.seek(n, 1)
        return None
    return f.read(n).decode("utf-8", "replace")


def _value(f, t, keep=True):
    if t in _SCALAR:
        return _read(f, _SCALAR[t])
    if t == 8:
        return _string(f, keep)
    if t == 9:
        et, n = _read(f, "<I"), _read(f, "<Q")
        if et == 8:
            for _ in range(n):
                _string(f, keep=False)
        elif et in _SCALAR:
            f.seek(struct.calcsize(_SCALAR[et]) * n, 1)
        else:
            raise ValueError("nested GGUF arrays are not expected in metadata")
        return f"<array of {n}>"
    raise ValueError(f"unknown GGUF value type {t}")


def gguf_meta(path: Path) -> dict:
    """The metadata keys of a GGUF file (arrays are skipped, not read)."""
    with open(path, "rb") as f:
        if f.read(4) != b"GGUF":
            raise ValueError("not a GGUF file")
        version = _read(f, "<I")
        _read(f, "<Q")  # tensor count
        kv = _read(f, "<Q")
        out = {"gguf_version": version}
        for _ in range(kv):
            key = _string(f)
            t = _read(f, "<I")
            out[key] = _value(f, t, keep=t != 9)
        return out


def _from_gguf(path: Path) -> dict:
    m = gguf_meta(path)
    arch = str(m.get("general.architecture", ""))
    a = lambda k: m.get(f"{arch}.{k}")
    num = lambda v: v if isinstance(v, int) and not isinstance(v, bool) and v > 0 else None  # a per-layer array is not one number
    heads = num(a("attention.head_count"))
    emb = num(a("embedding_length"))
    return {"format": "gguf", "architecture": arch, "name": m.get("general.name") or path.stem,
            "size_label": m.get("general.size_label"), "quantization": GGUF_FILE_TYPES.get(m.get("general.file_type"), m.get("general.file_type")),
            "context_length": a("context_length"), "layers": a("block_count"), "kv_heads": a("attention.head_count_kv") or heads,
            "head_dim": a("attention.key_length") or (emb // heads if emb and heads else None), "license": m.get("general.license"),
            "base_model": m.get("general.base_model.0.repo_url") or m.get("general.base_model.0.name")}


# ---- safetensors: an 8-byte length and a JSON header that lists every tensor's dtype and shape ----
DTYPE_BYTES = {"F64": 8, "F32": 4, "F16": 2, "BF16": 2, "F8_E4M3": 1, "F8_E5M2": 1, "I8": 1, "U8": 1, "I32": 4, "I64": 8, "I16": 2, "BOOL": 1}


def safetensors_header(path: Path) -> dict:
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        if n > 100 * 1000 * 1000:
            raise ValueError("implausible safetensors header")
        return json.loads(f.read(n))


def _params(headers: list[dict]) -> tuple[int, str]:
    total, dtypes = 0, {}
    for h in headers:
        if not isinstance(h, dict):
            raise ValueError("a safetensors header must be an object")
        for k, t in h.items():
            if k == "__metadata__" or not isinstance(t, dict):
                continue
            n = 1
            for d in t.get("shape", []) if isinstance(t.get("shape"), list) else []:
                n *= d if isinstance(d, int) else 0
            total += n
            dtypes[t.get("dtype")] = dtypes.get(t.get("dtype"), 0) + n
    return total, (max(dtypes, key=dtypes.get) if dtypes else "")


KIND_WORDS = [("video", ("wan2", "wan22", "ltxv", "ltx-video", "hunyuanvideo", "infinitetalk")), ("vae", ("vae",)),
              ("text-encoder", ("t5xxl", "umt5", "t5-v1_1", "text_encoder", "clip_l", "clip_g")),
              ("image", ("flux", "z_image", "z-image", "qwen-image", "realistic_vision", "sdxl", "stable-diffusion", "diffusion_pytorch_model", "checkpoints/")),
              ("tts", ("chatterbox", "kokoro", "tts")), ("depth", ("depth",))]


def kind_of(path: Path, arch: str = "") -> str:
    p = str(path).lower()
    folder = path if path.is_dir() else path.parent
    if "adapter_model" in path.name.lower() or (folder / "adapter_config.json").exists() or re.search(r"[/\\]checkpoint-\d+", p):
        return "lora-adapter"  # a fine-tuning adapter or a training checkpoint: not a model that runs on its own
    for kind, words in KIND_WORDS:
        if any(w in p for w in words):
            return kind
    if arch and any(w in arch.lower() for w in ("vl", "clip")):
        return "vision-llm"
    return "llm"


def _license_from_readme(folder: Path) -> str | None:
    r = folder / "README.md"
    if not r.exists():
        return None
    m = re.search(r"^license:\s*([^\n]+)", r.read_text(errors="replace")[:4000], re.M)
    return m.group(1).strip().strip("'\"") if m else None


def _public_cache(p: Path) -> bool:
    """A model kept in a Hugging Face download cache came from a public repo; anything else on the disk is treated as the owner's own."""
    return "/.cache/huggingface/" in str(p) or "/voice-lab/hf/" in str(p)


def scan_files(cfg: dict | None = None) -> list[dict]:
    """Model files under the configured roots, a sharded Hugging Face folder counted once. Never the forbidden folder."""
    cfg = cfg or load_cfg()
    found, seen_dirs = [], set()
    for root in cfg.get("model_roots", []):
        r = Path(root).expanduser()
        if not r.exists() or _forbidden(r, cfg):
            continue
        for dirpath, dirnames, files in os.walk(r):
            d = Path(dirpath)
            if _forbidden(d, cfg):
                dirnames[:] = []
                continue
            dirnames[:] = [x for x in dirnames if x not in ("node_modules", ".git")]
            big = [d / f for f in files if f.lower().endswith((".gguf", ".safetensors", ".onnx", ".bin", ".ckpt")) and (d / f).is_file()
                   and not (d / f).is_symlink() and (d / f).stat().st_size >= MIN_BYTES]
            if not big:
                continue
            shards = [p for p in big if p.suffix == ".safetensors"]
            if (d / "config.json").exists() and shards and d not in seen_dirs:  # one Hugging Face model in this folder
                seen_dirs.add(d)
                found.append(_hf_folder(d, shards))
                big = [p for p in big if p not in shards]
            for p in big:
                found.append(_single(p))
    return found


def _hf_folder(d: Path, shards: list[Path]) -> dict:
    try:
        c = json.loads((d / "config.json").read_text())
    except (OSError, ValueError):
        c = {}
    try:
        params, dtype = _params([safetensors_header(s) for s in shards])
    except Exception:  # a truncated or malformed shard: size only
        params, dtype = 0, ""
    arch = (c.get("architectures") or [c.get("model_type", "")])[0]
    heads = c.get("num_attention_heads")
    return {"id": "file:" + str(d), "source": "files", "path": str(d), "format": "safetensors (Hugging Face folder)", "architecture": arch,
            "name": d.name, "params": params or None, "dtype": dtype, "quantization": dtype, "bytes": sum(s.stat().st_size for s in shards),
            "files": len(shards), "context_length": c.get("max_position_embeddings"), "layers": c.get("num_hidden_layers"),
            "kv_heads": c.get("num_key_value_heads") or heads, "head_dim": c.get("head_dim") or ((c.get("hidden_size") // heads) if c.get("hidden_size") and heads else None),
            "license": _license_from_readme(d), "kind": kind_of(d, arch), "engines": ["transformers"], "fingerprint": fingerprint(shards[0]),
            "private": not _public_cache(d)}


def _single(p: Path) -> dict:
    rec = {"id": "file:" + str(p), "source": "files", "path": str(p), "name": p.stem, "bytes": p.stat().st_size, "files": 1, "fingerprint": fingerprint(p)}
    try:
        if p.suffix.lower() == ".gguf":
            g = _from_gguf(p)
            rec.update(g)
            rec["kind"] = kind_of(p, g.get("architecture", ""))
            rec["engines"] = ["ollama", "llama.cpp"] if rec["kind"] in ("llm", "vision-llm") else ["stable-diffusion.cpp", "comfyui"]
        elif p.suffix.lower() == ".safetensors":
            params, dtype = _params([safetensors_header(p)])
            rec.update({"format": "safetensors", "params": params or None, "dtype": dtype, "quantization": dtype, "kind": kind_of(p)})
            rec["engines"] = ["comfyui"] if rec["kind"] in ("image", "video", "vae", "text-encoder") else ["transformers"]
        else:
            rec.update({"format": p.suffix.lstrip(".").lower(), "kind": kind_of(p), "engines": ["onnxruntime"] if p.suffix.lower() == ".onnx" else []})
    except Exception as e:  # any unreadable header is one entry with an error, never a crash of the whole inventory
        rec.update({"format": p.suffix.lstrip(".").lower(), "error": f"header not readable: {type(e).__name__}: {e}"[:160], "kind": kind_of(p)})
    rec.setdefault("license", None)
    rec["private"] = not _public_cache(p)  # a file the owner made or copied in: never uploaded anywhere
    return rec


def ollama_models(url: str, get=None) -> list[dict]:
    """Every model Ollama serves, with what /api/show says (architecture, layers, KV heads, context, licence's first line). [] when Ollama is down."""
    import requests

    get = get or (lambda path, body=None: (requests.post if body else requests.get)(url + path, json=body, timeout=10).json())
    try:
        tags = get("/api/tags").get("models", [])
    except Exception:
        return []
    out = []
    for t in tags:
        det = t.get("details") or {}
        rec = {"id": "ollama:" + t["name"], "source": "ollama", "name": t["name"], "format": det.get("format", "gguf"), "architecture": det.get("family"),
               "params_label": det.get("parameter_size"), "quantization": det.get("quantization_level"), "bytes": t.get("size"), "files": 1,
               "fingerprint": {"digest": (t.get("digest") or "")[:16]}, "served_by": "ollama api (local)", "engines": ["ollama"], "path": "ollama store",
               "private": t["name"] not in set(load_cfg().get("public_ollama_models", []))}  # private unless the owner lists it as public (review)
        try:
            s = get("/api/show", {"model": t["name"]})
            info = s.get("model_info") or {}
            arch = info.get("general.architecture") or det.get("family") or ""
            a = lambda k: info.get(f"{arch}.{k}")
            heads = a("attention.head_count")
            rec.update({"architecture": arch, "context_length": a("context_length"), "layers": a("block_count"), "kv_heads": a("attention.head_count_kv") or heads,
                        "head_dim": a("attention.key_length") or ((a("embedding_length") // heads) if a("embedding_length") and heads else None),
                        "params": info.get("general.parameter_count"), "license": (str(s.get("license") or "").strip().splitlines() or [None])[0],
                        "kind": "vision-llm" if "vl" in arch.lower() or "projector_info" in s else "llm"})
        except Exception as e:
            rec["error"] = f"/api/show failed: {e}"[:160]
            rec["kind"] = "llm"
        out.append(rec)
    return out


def build(cfg: dict | None = None, ollama=None, files=None) -> dict:
    cfg = cfg or load_cfg()
    models = (ollama if ollama is not None else ollama_models(cfg.get("ollama_url", "http://127.0.0.1:11434"))) + \
             (files if files is not None else scan_files(cfg))
    digests: dict = {}
    for m in models:  # Ollama names that point at the same blob (argon-planner and argon-planner-next) are one model under two names
        dg = (m.get("fingerprint") or {}).get("digest")
        if dg:
            if dg in digests:
                m["same_as"] = digests[dg]
            else:
                digests[dg] = m["id"]
    return {"at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "models": models}


def save(inv: dict) -> Path:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(inv, indent=1, default=str))
    tmp.replace(OUT)
    return OUT


def load() -> dict:
    try:
        return json.loads(OUT.read_text())
    except (OSError, ValueError):
        return {"at": None, "models": []}


def still_same(m: dict) -> str:
    """"" when a file model is still the file the inventory saw; otherwise why not (changed, half-written, gone). Ollama models are checked by Ollama."""
    if m.get("source") != "files":
        return ""
    p = Path(m["path"])
    first = p if p.is_file() else next(iter(sorted(p.glob("*.safetensors"))), None)
    if first is None or not first.exists():
        return "the model's file is gone"
    now = fingerprint(first)
    was = m.get("fingerprint") or {}
    if now.get("head_sha256") != was.get("head_sha256") or (p.is_file() and now.get("bytes") != was.get("bytes")):
        return "the model's file changed since the inventory (a half-finished download or an edit): run the inventory again"
    return ""
