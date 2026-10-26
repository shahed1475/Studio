"""Free OpenRouter models: chosen from OpenRouter's live list, with a cool-down for models that keep failing and a daily request counter.

OpenRouter allows 20 requests a minute on free models and 50 a day until $10 of credit has been bought once (then 1,000 a day).
The list of free models changes often, so nothing here is hard-coded to one model.
"""
import datetime as dt
import json

import requests

import config

FILE = config.ROOT / "data" / "free_models.json"
URL = "https://openrouter.ai/api/v1/models"
TTL = dt.timedelta(hours=24)
COOLDOWN = dt.timedelta(hours=6)
BUSY_COOLDOWN = dt.timedelta(minutes=10)  # a 429 means the provider is busy right now, not that the model is broken
RESERVE = 5  # of the count OpenRouter reports, always left unused, so a failed attempt cannot push the account over its limit
QUOTA_TTL = 60  # seconds the daily-quota answer is reused
MAX_FAILS = 3
DEFAULT_MIN_CTX = 16000
MIN_CTX = {"script": 32000}  # a documentary prompt is long
SKIP = ("image", "audio", "embed", "vision", "guard", "moderation", "safeguard", "tts", "rerank", "lyria", "music", "video")
FAMILIES = ("gemma", "llama", "qwen", "mistral", "deepseek", "nemotron", "gpt-oss", "glm", "kimi")
TS = "%Y-%m-%dT%H:%M:%SZ"


def _ts(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).strftime(TS)


def _parse(s: str) -> dt.datetime:
    return dt.datetime.strptime(s, TS).replace(tzinfo=dt.timezone.utc)


def _load() -> dict:
    try:
        return json.loads(FILE.read_text())
    except (OSError, ValueError):
        return {}


def _save(d: dict) -> None:
    try:
        FILE.parent.mkdir(parents=True, exist_ok=True)
        FILE.write_text(json.dumps(d, indent=1))
    except OSError:
        pass  # a usage and price cache: a lost save costs one more lookup, and a full disk must not make every model call fail


def _free(m: dict) -> bool:
    try:
        p = m["pricing"]
        return float(p["prompt"]) == 0 and float(p["completion"]) == 0
    except (KeyError, TypeError, ValueError):
        return False


def _score(m: dict) -> float:
    params = m.get("supported_parameters") or []
    s = 3.0 if ("response_format" in params or "structured_outputs" in params) else 0.0
    s += min(m.get("context_length") or 0, 200000) / 100000
    return s + (2.0 if any(f in m["id"].lower() for f in FAMILIES) else 0.0)


def refresh(now: dt.datetime, get=requests.get, force: bool = False) -> list[dict]:
    """The free text models, best first. Cached for a day; a network failure keeps the last list."""
    d = _load()
    if not force and d.get("fetched_at") and d.get("models") and now - _parse(d["fetched_at"]) < TTL:
        return d["models"]
    try:
        r = get(URL, timeout=20)
        r.raise_for_status()
        data = r.json()["data"]
    except Exception:
        return d.get("models", [])
    models = []
    for m in data:
        out = (m.get("architecture") or {}).get("output_modalities") or ["text"]
        if not _free(m) or "text" not in out or any(t in m["id"].lower() for t in SKIP) or (m.get("context_length") or 0) < DEFAULT_MIN_CTX:
            continue
        models.append({"id": m["id"], "context": m["context_length"], "score": round(_score(m), 2)})
    models.sort(key=lambda m: (-m["score"], m["id"]))
    d.update(fetched_at=_ts(now), models=models)
    _save(d)
    return models


def choose(role: str, now: dt.datetime, avoid: str | None = None, n: int = 3) -> list[str]:
    d = _load()
    health = d.get("health", {})
    need = MIN_CTX.get(role, DEFAULT_MIN_CTX)
    out = []
    for m in d.get("models", []):
        h = health.get(m["id"], {})
        cooling = h.get("fails", 0) >= MAX_FAILS and now - _parse(h["last_fail"]) < COOLDOWN
        busy = bool(h.get("busy_until")) and now < _parse(h["busy_until"])
        if m["context"] >= need and m["id"] != avoid and not cooling and not busy:
            out.append(m)
    out.sort(key=lambda m: -min(health.get(m["id"], {}).get("ok", 0), 5))  # models that answered well before go first (stable otherwise)
    return [m["id"] for m in out][:n]


def record(model: str, ok: bool, now: dt.datetime, status: int | None = None) -> None:
    d = _load()
    h = d.setdefault("health", {}).setdefault(model, {"fails": 0})
    if ok:
        h["fails"] = 0
        h["ok"] = h.get("ok", 0) + 1
        h.pop("busy_until", None)
    elif status == 429:
        h["busy_until"] = _ts(now + BUSY_COOLDOWN)  # skip it for ten minutes; no long penalty
    else:
        h["fails"] += 1
        h["last_fail"] = _ts(now)
    _save(d)


_quota_cache: dict = {}


def quota(key: str, now_s: float | None = None, get=requests.get) -> dict | None:
    """What OpenRouter itself says about today's free requests: {"used", "limit", "remaining"}. None when it cannot be read.
    Failed attempts count there too, so this is the number to trust, not our own counter."""
    import time

    t = now_s if now_s is not None else time.time()
    if _quota_cache.get("key") == key and t - _quota_cache.get("at", 0) < QUOTA_TTL:
        return _quota_cache["data"]
    try:
        r = get("https://openrouter.ai/api/v1/key", headers={"Authorization": f"Bearer {key}"}, timeout=15)
        r.raise_for_status()
        q = r.json()["data"]["free_model_daily_requests"]
        data = {"used": int(q["used"]), "limit": int(q["limit"]), "remaining": int(q["remaining"])}
    except Exception:
        return None
    _quota_cache.update(key=key, at=t, data=data)
    return data


def remaining(now: dt.datetime, key: str, own_limit: int) -> int:
    """Free requests we may still use today: the smaller of OpenRouter's own count and our own ceiling minus what we counted."""
    ours = own_limit - requests_today(now)
    q = quota(key)
    return min(ours, q["remaining"] - RESERVE) if q else ours


def requests_today(now: dt.datetime, role: str | None = None) -> int:
    d, day = _load(), now.strftime("%Y-%m-%d")
    return d.get("usage", {}).get(day, 0) if role is None else d.get("roles", {}).get(day, {}).get(role, 0)


def count_request(now: dt.datetime, role: str = "") -> None:
    d = _load()
    day = now.strftime("%Y-%m-%d")
    usage = d.setdefault("usage", {})
    usage[day] = usage.get(day, 0) + 1
    d["usage"] = dict(sorted(usage.items())[-7:])
    roles = d.setdefault("roles", {})
    roles.setdefault(day, {})[role] = roles.get(day, {}).get(role, 0) + 1
    d["roles"] = dict(sorted(roles.items())[-7:])
    _save(d)
