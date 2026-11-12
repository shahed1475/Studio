"""Free pictures for Autopilot (13 Nov 2026): the owner's free Cloudflare Workers AI account draws the scenes instead of the paid OpenRouter image model.
FLUX.2 klein 4B (Apache-2.0 on Hugging Face, checked by tools/cloudflare_batch.py on 1 Nov 2026: a natural face, five fingers a hand, the size asked for) at 26.05 Neurons per 512x512 tile;
the free plan gives 10,000 Neurons a day (reset 00:00 UTC) and stops with an error instead of billing. A run keeps its own count in data/cloudflare_usage.json (the same file
tools/cloudflare_batch.py uses, so a hand run and Autopilot share one day) and stops at `free_art_cap` (default 9,000). Switch: `free_art` in llm.json (off by default, never in a user studio);
keys CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN come from the server's .env and travel only in a header. Returns a picture and its credit, or None (the caller then
falls back to the paid model if that is on, else to archive pictures). A cached picture costs nothing. Nothing here spends money; every picture is labelled AI-generated."""
import base64
import datetime as dt
import io
import json
import math
import os
import urllib.error
import urllib.request

import config

MODEL = "@cf/black-forest-labs/flux-2-klein-4b"
TILE = 26.05  # Neurons per 512x512 output tile (Cloudflare's price page, read 1 Nov 2026)
DEFAULT_CAP = 9000
USAGE = config.ROOT / "data" / "cloudflare_usage.json"
SIZES = {"film": (1024, 576), "short": (704, 1248), "thumb": (1280, 720)}
CREDIT = "Illustration: AI-generated storybook art (FLUX.2 klein 4B, Apache-2.0, drawn on Cloudflare Workers AI)"
CREDIT_PHOTO = "Images: AI-generated realistic scenes with invented people, not real photographs (FLUX.2 klein 4B, Apache-2.0, drawn on Cloudflare Workers AI)"
PAUSE_MINUTES = 10  # after a busy answer (429, 5xx, network): nothing is sent for a while
_off: dict = {}


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def credit_for(style: str | None) -> str:
    return CREDIT_PHOTO if style == "photo" else CREDIT


def neurons(w: int, h: int) -> float:
    return math.ceil(w / 512) * math.ceil(h / 512) * TILE


def have_keys() -> bool:
    return bool(os.environ.get("CLOUDFLARE_ACCOUNT_ID") and os.environ.get("CLOUDFLARE_API_TOKEN"))


def used_today(today: str | None = None) -> float:
    today = today or _now().strftime("%Y-%m-%d")
    try:
        d = json.loads(USAGE.read_text())
        return float(d["neurons"]) if d.get("date") == today else 0.0
    except (OSError, ValueError, KeyError, TypeError):
        return 0.0


def _save(today: str, n: float) -> None:
    USAGE.parent.mkdir(parents=True, exist_ok=True)
    USAGE.write_text(json.dumps({"date": today, "neurons": round(n, 2)}))


def available(cfg: dict | None = None, now: dt.datetime | None = None) -> bool:
    """On when the owner switched `free_art` on, both keys are set, this is the owner's studio and no pause is running."""
    import llm
    import tenantmode

    now = now or _now()
    cfg = cfg if cfg is not None else llm.load_config()
    if not cfg.get("free_art") or not have_keys() or tenantmode.is_tenant():
        return False
    if _off.get("day") == now.strftime("%Y-%m-%d"):
        return False
    return not (_off.get("until") and now < _off["until"])


MIN_LEFT_TO_START = 1500  # Neurons: below this a new film would be drawn mostly from archive pictures, so Autopilot does not count on the free account today


def usable(cfg: dict | None = None, now: dt.datetime | None = None) -> bool:
    """Free drawing is on AND enough of today's allowance is left to start a video on it."""
    return available(cfg, now) and quota_left(cfg, now) >= MIN_LEFT_TO_START


def quota_left(cfg: dict | None = None, now: dt.datetime | None = None) -> float:
    import llm

    now = now or _now()
    cfg = cfg if cfg is not None else llm.load_config()
    return max(0.0, float(cfg.get("free_art_cap") or DEFAULT_CAP) - used_today(now.strftime("%Y-%m-%d")))


def _fetch(url: str, headers: dict, body: bytes, ctype: str) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, headers={**headers, "Content-Type": ctype}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _multipart(payload: dict) -> tuple[bytes, str]:
    import uuid

    b = uuid.uuid4().hex
    return b"".join(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in payload.items()) + f"--{b}--\r\n".encode(), f"multipart/form-data; boundary={b}"


def draw(prompt: str, kind: str, dest, style: str | None = None, fetch=None, now: dt.datetime | None = None):
    """(dest, credit) after drawing `prompt` to the JPEG file `dest` (kind: film, short or thumb), or None. Never raises: a failure only pauses free drawing."""
    import llm

    now = now or _now()
    if not available(now=now):
        return None
    w, h = SIZES[kind]
    cost = neurons(w, h)
    today = now.strftime("%Y-%m-%d")
    cap = float(llm.load_config().get("free_art_cap") or DEFAULT_CAP)
    used = used_today(today)
    if used + cost > cap + 1e-9:
        return None
    acc, tok = os.environ["CLOUDFLARE_ACCOUNT_ID"], os.environ["CLOUDFLARE_API_TOKEN"]
    body, ctype = _multipart({"prompt": prompt[:1900], "width": w, "height": h})
    try:
        status, raw = (fetch or _fetch)(f"https://api.cloudflare.com/client/v4/accounts/{acc}/ai/run/{MODEL}", {"Authorization": f"Bearer {tok}"}, body, ctype)
        data = json.loads(raw)
        img = base64.b64decode(data["result"]["image"]) if status == 200 and data.get("success") else b""
    except Exception:  # a network error or an unreadable answer: the same as a refusal
        status, img = 0, b""
    if img[:2] not in (b"\xff\xd8", b"\x89P"):
        if status in (401, 403):
            _off["day"] = today  # a wrong key or a missing permission will not mend itself today
        elif status == 429 or status >= 500 or status == 0:
            _off["until"] = now + dt.timedelta(minutes=PAUSE_MINUTES)
        return None
    from PIL import Image

    im = Image.open(io.BytesIO(img)).convert("RGB")
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, "JPEG", quality=92)
    _save(today, used + cost)
    return dest, credit_for(style)
