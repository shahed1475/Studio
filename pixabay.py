"""Pixabay look-up (key from PIXABAY_API_KEY in the server's .env, or saved in Settings). Reads only: it finds pictures and videos and returns their addresses
and credit lines. Nothing here downloads a file or puts one into a video: Pixabay's own licence (not CC0, not public domain) is not one the studio's licence
check accepts yet, so using it in a video is the owner's separate decision.
Pixabay's API rules: at most 100 requests per 60 seconds, and results are to be cached for 24 hours; this module keeps a 24 hour cache on disk."""
import hashlib
import json
import time
from pathlib import Path

import requests

import config

API = "https://pixabay.com/api/"
VIDEO_API = "https://pixabay.com/api/videos/"
CACHE_HOURS = 24
TIMEOUT = 20


def key() -> str:
    """The key, from the environment/.env, else the dashboard's saved settings. Empty when none is set."""
    if config.PIXABAY_KEY:
        return config.PIXABAY_KEY
    try:
        return str(json.loads((config.ROOT / "settings.json").read_text()).get("pixabay_key", ""))
    except (OSError, ValueError):
        return ""


def _cache_file(url: str, params: dict) -> Path:
    stable = url + json.dumps({k: v for k, v in params.items() if k != "key"}, sort_keys=True)  # the key is never part of a file name
    return config.CACHE / "pixabay" / (hashlib.md5(stable.encode()).hexdigest()[:16] + ".json")


def _get(url: str, params: dict, get=requests.get, now=time.time) -> dict:
    k = key()
    if not k:
        raise RuntimeError("no Pixabay key: add PIXABAY_API_KEY to the server's .env")
    f = _cache_file(url, params)
    if f.exists() and now() - f.stat().st_mtime < CACHE_HOURS * 3600:
        return json.loads(f.read_text())
    r = get(url, params={**params, "key": k}, timeout=TIMEOUT)
    if r.status_code == 429:
        raise RuntimeError("Pixabay says too many requests (limit 100 a minute); try again in a minute")
    if r.status_code in (400, 401, 403):
        raise RuntimeError(f"Pixabay refused the request (HTTP {r.status_code}): the key may be wrong")
    r.raise_for_status()
    reply = r.json()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(reply))
    return reply


def search_images(query: str, per_page: int = 5, get=requests.get) -> list[dict]:
    data = _get(API, {"q": query, "image_type": "photo", "safesearch": "true", "per_page": max(3, per_page)}, get)
    return [{"id": h.get("id"), "page": h.get("pageURL"), "preview": h.get("webformatURL"), "user": h.get("user"), "tags": h.get("tags", ""),
             "credit": f"Image by {h.get('user')} via Pixabay ({h.get('pageURL')})"} for h in data.get("hits", [])][:per_page]


def search_videos(query: str, per_page: int = 5, get=requests.get) -> list[dict]:
    data = _get(VIDEO_API, {"q": query, "safesearch": "true", "per_page": max(3, per_page)}, get)
    out = []
    for h in data.get("hits", [])[:per_page]:
        v = (h.get("videos") or {})
        best = v.get("medium") or v.get("small") or v.get("large") or {}
        out.append({"id": h.get("id"), "page": h.get("pageURL"), "url": best.get("url"), "width": best.get("width"), "height": best.get("height"),
                    "seconds": h.get("duration"), "user": h.get("user"), "credit": f"Video by {h.get('user')} via Pixabay ({h.get('pageURL')})"})
    return out


def selftest(query: str = "pyramids", get=requests.get) -> str:
    """One image search and one video search; says plainly what worked. Never prints the key."""
    if not key():
        return "FAIL: no Pixabay key found (PIXABAY_API_KEY in .env or Settings)"
    lines = []
    for name, fn in (("images", search_images), ("videos", search_videos)):
        try:
            hits = fn(query, 3, get)
            lines.append(f"ok   {name}: {len(hits)} results for '{query}'" + (f", first: {hits[0]['page']}" if hits else ""))
        except Exception as e:  # any failure is reported, never hidden
            lines.append(f"FAIL {name}: {str(e).replace(key(), '***')[:200]}")
    return "\n".join(lines)
