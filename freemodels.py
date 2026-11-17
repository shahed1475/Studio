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
EXTRA_BUSY_SECONDS = 60  # the owner's own provider pools free tiers whose limits are per minute: a 429 there is short (17 Nov 2026: ten minutes parked every model and a script was lost)
MAX_RETRY_AFTER = 300  # a Retry-After header is believed up to this many seconds
RESERVE = 5  # of the count OpenRouter reports, always left unused, so a failed attempt cannot push the account over its limit
QUOTA_TTL = 60  # seconds the daily-quota answer is reused
MAX_FAILS = 3
SLOW_SECONDS = 90  # an answer that took longer than this counts as slow
NEUTRAL_SECONDS = 45  # a model with no timing yet ranks as if it took this long (it is not punished and not favoured)
KEEP_SECONDS = 9  # timings kept per model and role: the median of the last nine
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


def choose(role: str, now: dt.datetime, avoid=None, n: int = 3) -> list[str]:
    """`avoid` is one model ID or a set of them: they are never chosen."""
    skip = {avoid} if isinstance(avoid, str) else set(avoid or ())
    d = _load()
    health = d.get("health", {})
    need = MIN_CTX.get(role, DEFAULT_MIN_CTX)
    out = []
    for m in d.get("models", []):
        h = health.get(m["id"], {})
        cooling = h.get("fails", 0) >= MAX_FAILS and now - _parse(h["last_fail"]) < COOLDOWN
        busy = bool(h.get("busy_until")) and now < _parse(h["busy_until"])
        if m["context"] >= need and m["id"] not in skip and not cooling and not busy:
            out.append(m)
    # the model that answered valid JSON most often for this role goes first, then the faster one (stable otherwise: the roster score decides)
    out.sort(key=lambda m: (-round(_reliability(health.get(m["id"], {}), role), 2), _median(health.get(m["id"], {}), role) or NEUTRAL_SECONDS))
    return [m["id"] for m in out][:n]


def _reliability(h: dict, role: str) -> float:
    """(answers + 1) / (answers + failures + 2) for this role: 0.5 for a model never tried, so a new model is neither punished nor favoured.
    A 429 is not a failure here (it only makes the model busy). Answers recorded without a role (older files) count for every role."""
    rs = (h.get("roles") or {}).get(role) or {}
    ok, bad = rs.get("ok", 0), rs.get("bad", 0)
    if ok + bad == 0:
        ok = h.get("ok", 0)
    return (ok + 1) / (ok + bad + 2)


def _median(h: dict, role: str) -> float | None:
    secs = sorted(((h.get("roles") or {}).get(role) or {}).get("secs", []))
    if not secs:
        return None
    mid = len(secs) // 2
    return secs[mid] if len(secs) % 2 else round((secs[mid - 1] + secs[mid]) / 2, 1)


def reliability(model: str, role: str) -> float:
    return _reliability(_load().get("health", {}).get(model, {}), role)


def median_seconds(model: str, role: str) -> float | None:
    return _median(_load().get("health", {}).get(model, {}), role)


def failure_report() -> dict:
    """What was measured, per model and role: {model: {role: {ok, bad, json_bad, slow, finish: {reason: n}, median_s}}}.
    `finish` says how the failed answers ended ("length" means the reply was cut off by the output limit)."""
    out: dict = {}
    for mid, h in _load().get("health", {}).items():
        for role, rs in (h.get("roles") or {}).items():
            out.setdefault(mid, {})[role] = {"ok": rs.get("ok", 0), "bad": rs.get("bad", 0), "json_bad": rs.get("json_bad", 0), "slow": rs.get("slow", 0),
                                             "finish": dict(rs.get("finish", {})), "median_s": _median(h, role)}
    return out


def roster_ids() -> list[str]:
    return [m["id"] for m in _load().get("models", [])]


def soonest_free(ids: list[str], now: dt.datetime) -> int | None:
    """Seconds until the first of these models stops being busy (a 429, not a run of failures); None when none of them is only busy."""
    import math

    health, waits = _load().get("health", {}), []
    for mid in ids:
        h = health.get(mid, {})
        if h.get("fails", 0) >= MAX_FAILS and h.get("last_fail") and now - _parse(h["last_fail"]) < COOLDOWN:
            continue  # cooling after real failures: not a short wait
        if h.get("busy_until") and now < _parse(h["busy_until"]):
            waits.append((_parse(h["busy_until"]) - now).total_seconds())
    return math.ceil(min(waits)) if waits else None


def available(model: str, now: dt.datetime) -> bool:
    """False while a model is cooling down after repeated failures or busy after a 429. A model never seen before is available."""
    h = _load().get("health", {}).get(model, {})
    if h.get("fails", 0) >= MAX_FAILS and h.get("last_fail") and now - _parse(h["last_fail"]) < COOLDOWN:
        return False
    return not (h.get("busy_until") and now < _parse(h["busy_until"]))


def record(model: str, ok: bool, now: dt.datetime, status: int | None = None, retry_after: int | None = None,
           role: str | None = None, seconds: float | None = None, reason: str | None = None, finish: str | None = None) -> None:
    """One answer or failure. `role` and `seconds` feed the per-role ranking; `reason` "json" marks a reply that was not JSON and `finish` is the
    reply's finish_reason ("length" = cut off by the output limit). A 429 only makes the model busy: it is not counted as a failure."""
    d = _load()
    h = d.setdefault("health", {}).setdefault(model, {"fails": 0})
    rs = h.setdefault("roles", {}).setdefault(role, {}) if role else None
    if rs is not None and seconds is not None and status != 429:
        rs["secs"] = (rs.get("secs", []) + [round(float(seconds), 1)])[-KEEP_SECONDS:]
        if seconds > SLOW_SECONDS:
            rs["slow"] = rs.get("slow", 0) + 1
    if ok:
        h["fails"] = 0
        h["ok"] = h.get("ok", 0) + 1
        h.pop("busy_until", None)
        if rs is not None:
            rs["ok"] = rs.get("ok", 0) + 1
    elif status == 429:
        if retry_after:
            secs = min(max(int(retry_after), 1), MAX_RETRY_AFTER)  # the provider said how long
        else:
            secs = EXTRA_BUSY_SECONDS if model.startswith("extra:") else int(BUSY_COOLDOWN.total_seconds())  # skip it for ten minutes; no long penalty
        h["busy_until"] = _ts(now + dt.timedelta(seconds=secs))
    else:
        h["fails"] += 1
        h["last_fail"] = _ts(now)
        if rs is not None:
            rs["bad"] = rs.get("bad", 0) + 1
            if reason == "json":
                rs["json_bad"] = rs.get("json_bad", 0) + 1
            if finish:
                fin = rs.setdefault("finish", {})
                fin[finish] = fin.get(finish, 0) + 1
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
