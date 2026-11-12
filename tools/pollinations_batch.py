"""Draw pictures with Pollinations (gen.pollinations.ai) for a video made in a Claude Code session (1 Nov 2026).
Usage: PYTHONPATH=. python tools/pollinations_batch.py jobs.json [--cap 0.5]   (a list of {"id", "prompt", "width", "height", "seed", "model"?}).
The key is POLLINATIONS_API_KEY from .env (the owner's own, never in chat or git): it travels only in an Authorization header, never in an address, a message or a log.
Only a model with a flat price per picture is used (its price is read from GET /v1/models, which needs no key); a run stops before the request that would pass `--cap` Pollen,
and a picture already in cache/cc costs nothing. Writes cache/cc/p-<hash>.jpg and prints "DONE <id> <path> <cost>" per picture.
Measured 1 Nov 2026: z-image-turbo 1280x704 in 15 s (0.004 Pollen), flux.1.1-pro 1280x704 in 11 s (0.03 Pollen), no logo on the keyed route. The terms of use (commercial use of the
pictures) were NOT verified: a film that uses them stays a held draft until the owner has read pollinations.ai/terms."""
import hashlib
import json
import math
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import config

BASE = "https://gen.pollinations.ai"
DEFAULT_MODEL = "tongyi-mai/z-image-turbo"
KEY_VAR = "POLLINATIONS_API_KEY"


def fit_size(w: int, h: int) -> tuple[int, int]:
    """Sizes rounded up to a multiple of 32 (FLUX 1.1 Pro refuses others: a 1280x720 request got a 400)."""
    return math.ceil(w / 32) * 32, math.ceil(h / 32) * 32


def path_for(job: dict) -> Path:
    w, h = fit_size(job["width"], job["height"])
    key = json.dumps([job["prompt"], w, h, job.get("seed", 1), job.get("model", DEFAULT_MODEL)], sort_keys=True)
    d = Path(config.CACHE) / "cc"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"p-{hashlib.sha256(key.encode()).hexdigest()[:16]}.jpg"


def _fetch(url: str, headers: dict) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=240) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _key() -> str:
    k = os.environ.get(KEY_VAR, "")
    if not k:
        raise RuntimeError(f"{KEY_VAR} is not set: add it to .env (the owner's own key)")
    return k


def draw(job: dict, fetch=None) -> Path:
    out = path_for(job)
    if out.exists():
        return out
    key = _key()
    w, h = fit_size(job["width"], job["height"])
    q = urllib.parse.urlencode({"model": job.get("model", DEFAULT_MODEL), "width": w, "height": h, "seed": job.get("seed", 1)})
    status, body = (fetch or _fetch)(f"{BASE}/image/{urllib.parse.quote(job['prompt'], safe='')}?{q}", {"Authorization": f"Bearer {key}"})
    if status != 200 or body[:2] not in (b"\xff\xd8", b"\x89P"):
        raise RuntimeError(f"Pollinations answered {status}: " + body[:200].decode(errors="ignore").replace(key, "***"))
    part = Path(str(out) + ".part")
    part.write_bytes(body)
    part.rename(out)
    return out


def load_prices(fetch=None) -> dict:
    """Pollen per picture for every image model whose price is one flat number (no key needed for the model list)."""
    status, body = (fetch or _fetch)(f"{BASE}/v1/models", {})
    if status != 200:
        raise RuntimeError(f"model list answered {status}")
    data = json.loads(body)
    out = {}
    for m in data.get("data", data):
        p = m.get("pricing") or {}
        if "image" in json.dumps(m.get("output_modalities", "")).lower() and set(p) <= {"currency", "completionImageTokens"} and "completionImageTokens" in p:
            out[m["id"]] = float(p["completionImageTokens"])
    return out


def run(jobs: list[dict], cap: float, prices: dict | None = None, fetch=None) -> list[dict]:
    """Draw in order. A cached picture is free; a request that would pass the cap is not sent."""
    prices = prices if prices is not None else load_prices()
    for j in jobs:
        if j.get("model", DEFAULT_MODEL) not in prices:
            raise ValueError(f"model {j.get('model', DEFAULT_MODEL)} has no flat per-picture price: not used")
    spent, out = 0.0, []
    for j in jobs:
        price = prices[j.get("model", DEFAULT_MODEL)]
        if path_for(j).exists():
            out.append({"id": j["id"], "status": "DONE", "cost": 0.0, "path": str(path_for(j))})
        elif spent + price > cap + 1e-9:
            out.append({"id": j["id"], "status": "CAP"})
        else:
            try:
                p = draw(j, fetch)
                spent += price
                out.append({"id": j["id"], "status": "DONE", "cost": price, "path": str(p)})
            except RuntimeError as e:
                out.append({"id": j["id"], "status": "FAIL", "error": str(e)})
    return out


if __name__ == "__main__":
    cap = float(sys.argv[sys.argv.index("--cap") + 1]) if "--cap" in sys.argv else 0.5
    res = run(json.loads(Path(sys.argv[1]).read_text()), cap)
    for r in res:
        print(r["status"], r["id"], r.get("path", ""), r.get("cost", ""), r.get("error", ""), flush=True)
    print(f"spent {sum(r.get('cost', 0) for r in res):.3f} Pollen of a {cap} cap")
