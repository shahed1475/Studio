"""Draw pictures with FLUX.1 schnell on Cloudflare Workers AI for a video made in a Claude Code session (1 Nov 2026).
Usage: PYTHONPATH=. python tools/cloudflare_batch.py jobs.json [--cap 9000]   (a list of {"id", "prompt", "steps"?, "seed"?}).
Free: Cloudflare gives every account 10,000 Neurons a day (reset 00:00 UTC) and, on the free Workers plan, stops with an error instead of billing (developers.cloudflare.com/workers-ai/platform/pricing,
read 1 Nov 2026). Price list for this model: 4.80 Neurons per 512x512 tile and 9.60 per step, so a 1024x1024 picture of 4 steps is about 57.6 Neurons (about 170 pictures a day: an estimate, the
size the API returns is not documented and must be checked on the first picture). The run keeps its own counter in data/cloudflare_usage.json and stops at `--cap` (default 9,000, a margin).
Settings come from .env, never from chat or git: CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN (a token with the Workers AI permission). The token travels only in a header.
Writes cache/cc/c-<hash>.jpg and prints "DONE <id> <path> <neurons>"."""
import base64
import datetime as dt
import hashlib
import json
import math
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

import config

MODEL = "@cf/black-forest-labs/flux-1-schnell"
KLEIN_MODEL = "@cf/black-forest-labs/flux-2-klein-4b"  # Apache-2.0 on Hugging Face; real sizes; checked 1 Nov 2026: 1280x720 in 11 s, a natural face, 5 fingers a hand
KLEIN_TILE = 26.05  # Neurons per 512x512 output tile (pricing page, 1 Nov 2026); the 9B and dev versions are non-commercial and are never used
TILE, STEP = 4.8, 9.6  # Neurons per 512x512 tile and per step
DAILY_FREE, DEFAULT_CAP = 10_000, 9_000
SIDE = 1024  # the assumed output side: unverified until the first real picture is measured
USAGE = Path(config.ROOT) / "data" / "cloudflare_usage.json"


def neurons(job: dict) -> float:
    if job.get("model") == "klein":
        return math.ceil(job["width"] / 512) * math.ceil(job["height"] / 512) * KLEIN_TILE
    tiles = math.ceil(job.get("width", SIDE) / 512) * math.ceil(job.get("height", SIDE) / 512)
    return tiles * TILE + job.get("steps", 4) * STEP


def path_for(job: dict) -> Path:
    if job.get("model") == "klein":
        key = json.dumps([job["prompt"], job["width"], job["height"], job.get("seed", 1), KLEIN_MODEL], sort_keys=True)
    else:
        key = json.dumps([job["prompt"], job.get("steps", 4), job.get("seed", 1), MODEL], sort_keys=True)
    d = Path(config.CACHE) / "cc"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"c-{hashlib.sha256(key.encode()).hexdigest()[:16]}.jpg"


def _multipart(payload: dict) -> tuple[bytes, str]:
    import uuid

    b = uuid.uuid4().hex
    body = b"".join(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in payload.items()) + f"--{b}--\r\n".encode()
    return body, f"multipart/form-data; boundary={b}"


def _fetch(url: str, headers: dict, payload: dict, multipart: bool = False) -> tuple[int, bytes]:
    body, ctype = _multipart(payload) if multipart else (json.dumps(payload).encode(), "application/json")
    req = urllib.request.Request(url, data=body, headers={**headers, "Content-Type": ctype}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=240) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _settings() -> tuple[str, str]:
    acc, tok = os.environ.get("CLOUDFLARE_ACCOUNT_ID", ""), os.environ.get("CLOUDFLARE_API_TOKEN", "")
    missing = [n for n, v in (("CLOUDFLARE_ACCOUNT_ID", acc), ("CLOUDFLARE_API_TOKEN", tok)) if not v]
    if missing:
        raise RuntimeError(f"{' and '.join(missing)} not set: add to .env (the owner's own Cloudflare account)")
    return acc, tok


def draw(job: dict, fetch=None) -> Path:
    out = path_for(job)
    if out.exists():
        return out
    acc, tok = _settings()
    klein = job.get("model") == "klein"
    if klein:
        payload, model, extra = {"prompt": job["prompt"], "width": job["width"], "height": job["height"]}, KLEIN_MODEL, {"multipart": True}
    else:
        payload, model, extra = {"prompt": job["prompt"], "steps": job.get("steps", 4)}, MODEL, {}  # no seed: the API answers 400 "Additional or unevaluated properties /seed" (checked live 1 Nov 2026)
    status, body = (fetch or _fetch)(f"https://api.cloudflare.com/client/v4/accounts/{acc}/ai/run/{model}", {"Authorization": f"Bearer {tok}"}, payload, **extra)
    try:
        data = json.loads(body)
        img = base64.b64decode(data["result"]["image"]) if status == 200 and data.get("success") else b""
    except (ValueError, KeyError, TypeError):
        img = b""
    if status != 200 or img[:2] not in (b"\xff\xd8", b"\x89P"):
        raise RuntimeError(f"Cloudflare answered {status}: " + body[:200].decode(errors="ignore").replace(tok, "***"))
    part = Path(str(out) + ".part")
    part.write_bytes(img)
    part.rename(out)
    return out


def _used(today: str) -> float:
    try:
        d = json.loads(USAGE.read_text())
        return float(d["neurons"]) if d.get("date") == today else 0.0
    except (OSError, ValueError, KeyError):
        return 0.0


def _save(today: str, n: float) -> None:
    USAGE.parent.mkdir(parents=True, exist_ok=True)
    USAGE.write_text(json.dumps({"date": today, "neurons": round(n, 2)}))


def run(jobs: list[dict], cap: float = DEFAULT_CAP, fetch=None, today: str | None = None) -> list[dict]:
    """In order. A cached picture is free; a request that would pass the day's cap is not sent."""
    today = today or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    used, out = _used(today), []
    for j in jobs:
        cost = neurons(j)
        if path_for(j).exists():
            out.append({"id": j["id"], "status": "DONE", "cost": 0.0, "path": str(path_for(j))})
        elif used + cost > cap + 1e-9:
            out.append({"id": j["id"], "status": "CAP"})
        else:
            try:
                p = draw(j, fetch)
                used += cost
                _save(today, used)
                out.append({"id": j["id"], "status": "DONE", "cost": cost, "path": str(p)})
            except RuntimeError as e:
                out.append({"id": j["id"], "status": "FAIL", "error": str(e)})
    return out


if __name__ == "__main__":
    cap = float(sys.argv[sys.argv.index("--cap") + 1]) if "--cap" in sys.argv else DEFAULT_CAP
    res = run(json.loads(Path(sys.argv[1]).read_text()), cap)
    for r in res:
        print(r["status"], r["id"], r.get("path", ""), r.get("cost", ""), r.get("error", ""), flush=True)
    print(f"used today: {_used(dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d')):.0f} of {DAILY_FREE} free Neurons")
