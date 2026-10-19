"""Model router: OpenRouter for the jobs where quality matters, the local Ollama model as fallback, a hard daily spend cap.

Roles: script (writing, news summary), review (fact-check, must be a different model), cheap (titles, tags, hooks, ideas).
The API key is read from settings.json or OPENROUTER_API_KEY and is never logged or returned.
"""
import copy
import datetime as dt
import json
import re
import time

import requests

import config
import freemodels

CONFIG_FILE = config.ROOT / "llm.json"
USAGE_FILE = config.ROOT / "data" / "llm_usage.json"
SETTINGS_FILE = config.ROOT / "settings.json"
PRICES_FILE = config.ROOT / "data" / "or_prices.json"
ROLES = ("script", "review", "cheap")
DEFAULTS = {"enabled": False, "models": {"script": "", "review": "", "cheap": ""}, "daily_budget_usd": 1.0, "max_output_tokens": 6000,
            "free": False, "free_daily_limit": 45}  # free: try OpenRouter free models first (50 requests a day without credits)
MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9/._:+-]{1,99}$")
UNKNOWN_PRICE = (10.0, 30.0)  # per million tokens: deliberately high, so an unknown model cannot slip past the cap

# Tokens per finished item, by role: (input, output). Estimates from our prompts; the dashboard shows real spend next to them.
TOKENS = {
    "doc": {"script": (13000, 3000), "review": (2000, 100), "cheap": (1700, 450)},
    "short": {"script": (700, 450), "review": (700, 100), "cheap": (1100, 330)},
    "weekly": {"script": (3000, 800), "cheap": (1200, 400)},  # news digest, trend and channel ideas
}


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def load_config() -> dict:
    cfg = copy.deepcopy(DEFAULTS)
    if CONFIG_FILE.exists():
        raw = json.loads(CONFIG_FILE.read_text())
        cfg.update({k: raw[k] for k in ("enabled", "daily_budget_usd", "max_output_tokens", "free", "free_daily_limit") if k in raw})
        cfg["models"].update({k: v for k, v in raw.get("models", {}).items() if k in ROLES})
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG_FILE.write_text(json.dumps({k: cfg[k] for k in DEFAULTS}, indent=2))


def validate_config(raw: dict) -> dict:
    """A partial update; raises ValueError for anything out of range."""
    out: dict = {}
    for k, v in raw.items():
        if k == "enabled":
            if not isinstance(v, bool):
                raise ValueError("enabled must be on or off")
        elif k == "daily_budget_usd":
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0.05 <= v <= 100:
                raise ValueError("the daily cap must be between 0.05 and 100 dollars")
        elif k == "max_output_tokens":
            if isinstance(v, bool) or not isinstance(v, int) or not 500 <= v <= 16000:
                raise ValueError("max tokens per call must be between 500 and 16000")
        elif k == "free":
            if not isinstance(v, bool):
                raise ValueError("free models must be on or off")
        elif k == "free_daily_limit":
            if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 1000:
                raise ValueError("the free request limit must be between 1 and 1000 a day")
        elif k == "models":
            if not isinstance(v, dict):
                raise ValueError("models must be a set of job names and model IDs")
            for role, mid in v.items():
                if role not in ROLES:
                    raise ValueError(f"unknown job: {role}")
                if mid != "" and not MODEL_ID.match(str(mid)):
                    raise ValueError(f"'{mid}' is not a model ID: copy it from openrouter.ai/models, for example vendor/name")
        else:
            raise ValueError(f"unknown setting: {k}")
        out[k] = v
    models = {**load_config()["models"], **out.get("models", {})}
    if models["script"] and models["script"] == models["review"]:
        raise ValueError("the reviewer model must differ from the writer model, otherwise it only agrees with itself")
    return out


def api_key() -> str:
    import os

    env = os.getenv("OPENROUTER_API_KEY")
    if env:
        return env
    return json.loads(SETTINGS_FILE.read_text()).get("openrouter_key", "") if SETTINGS_FILE.exists() else ""


# ---- usage and spend ----
def _usage() -> dict:
    return json.loads(USAGE_FILE.read_text()) if USAGE_FILE.exists() else {}


def _day(now: dt.datetime) -> str:
    return now.astimezone(dt.timezone.utc).strftime("%Y-%m-%d")


def spent_today(now: dt.datetime | None = None) -> float:
    return float(_usage().get(_day(now or _now()), {}).get("usd", 0.0))


def _save_day(now: dt.datetime, mutate) -> None:
    data = _usage()
    day = data.setdefault(_day(now), {"usd": 0.0, "calls": 0, "by_role": {}, "fallbacks": []})
    mutate(day)
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    USAGE_FILE.write_text(json.dumps(data, indent=2))


def record(now: dt.datetime, role: str, model: str, tin: int, tout: int, usd: float) -> None:
    def add(day):
        day["usd"] = round(day["usd"] + usd, 6)
        day["calls"] += 1
        r = day["by_role"].setdefault(role, {"usd": 0.0, "calls": 0, "tokens_in": 0, "tokens_out": 0, "model": model})
        r.update(usd=round(r["usd"] + usd, 6), calls=r["calls"] + 1, tokens_in=r["tokens_in"] + tin, tokens_out=r["tokens_out"] + tout, model=model)
    _save_day(now, add)


def _note(now: dt.datetime, text: str) -> None:
    _save_day(now, lambda day: day["fallbacks"].append(text[:200]) if len(day["fallbacks"]) < 50 else None)


# ---- prices ----
def model_prices() -> dict:
    """{model id: (input $/Mtok, output $/Mtok)} from OpenRouter's public list, cached for a day."""
    if PRICES_FILE.exists():
        cached = json.loads(PRICES_FILE.read_text())
        if time.time() - cached.get("fetched", 0) < 86400:
            return {k: tuple(v) for k, v in cached["prices"].items()}
    try:
        data = requests.get("https://openrouter.ai/api/v1/models", timeout=30).json()["data"]
        prices = {m["id"]: (float(m["pricing"]["prompt"]) * 1e6, float(m["pricing"]["completion"]) * 1e6) for m in data
                  if m.get("pricing") and m["pricing"].get("prompt") is not None and m["pricing"].get("completion") is not None}
        PRICES_FILE.parent.mkdir(parents=True, exist_ok=True)
        PRICES_FILE.write_text(json.dumps({"fetched": time.time(), "prices": prices}))
        return prices
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return {k: tuple(v) for k, v in json.loads(PRICES_FILE.read_text())["prices"].items()} if PRICES_FILE.exists() else {}


def _usd(model: str, tin: int, tout: int) -> float:
    pin, pout = model_prices().get(model, UNKNOWN_PRICE)
    return (tin * pin + tout * pout) / 1e6


def estimate(prices: dict, docs_per_day: float, shorts_per_day: float, days: int = 30) -> dict:
    """Cost from token estimates and per-role prices {role: (in, out) $/Mtok}."""
    def cost(kind):
        by = {r: (tin * prices[r][0] + tout * prices[r][1]) / 1e6 for r, (tin, tout) in TOKENS[kind].items() if r in prices}
        return sum(by.values()), by
    doc, doc_by = cost("doc")
    short, short_by = cost("short")
    weekly, weekly_by = cost("weekly")
    per_day = docs_per_day * doc + shorts_per_day * short
    by_role = {r: (docs_per_day * doc_by.get(r, 0) + shorts_per_day * short_by.get(r, 0)) * days + weekly_by.get(r, 0) * days / 7 for r in ROLES}
    return {"per_doc_usd": doc, "per_short_usd": short, "weekly_usd": weekly, "per_day_usd": per_day,
            "per_month_usd": per_day * days + weekly * days / 7, "by_role": by_role}


# ---- calls ----
def parse_json(text: str) -> dict:
    text = (text or "").strip()
    for candidate in (text, text[text.find("{"): text.rfind("}") + 1] if "{" in text else ""):
        try:
            value = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("no JSON object in the reply")


def _post(payload: dict, key: str) -> dict:
    r = requests.post("https://openrouter.ai/api/v1/chat/completions", json=payload, timeout=240,
                      headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "X-Title": "Story Studio"})
    r.raise_for_status()
    return r.json()


def _payload(model: str, prompt: str, max_tokens: int, json_mode: bool = True) -> dict:
    p = {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens, "temperature": 0.7, "usage": {"include": True}}
    if json_mode:  # some free models reject JSON mode: they are asked again without it
        p["response_format"] = {"type": "json_object"}
    return p


def _account(now, role, model, body) -> float:
    u = body.get("usage") or {}
    tin, tout = int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0))
    usd = float(u["cost"]) if u.get("cost") is not None else _usd(model, tin, tout)
    record(now, role, model, tin, tout, usd)
    return usd


_last_free: dict[str, str] = {}  # the free model that last answered each role (the reviewer must differ from the writer)


def _free_chat(prompt: str, role: str, cfg: dict, key: str, now: dt.datetime) -> dict | None:
    """Try up to three free models in turn. None means: use the local model."""
    freemodels.refresh(now)
    for mid in freemodels.choose(role, now, avoid=_last_free.get("script") if role == "review" else None):
        for json_mode in (True, False):
            if freemodels.requests_today(now) >= cfg["free_daily_limit"]:
                _note(now, f"{role}: today's free request limit is used, used the local model")
                return None
            freemodels.count_request(now)  # failed requests count against the limit too
            try:
                body = _post(_payload(mid, prompt, cfg["max_output_tokens"], json_mode), key)
            except Exception as e:
                if json_mode and isinstance(e, requests.HTTPError) and getattr(e.response, "status_code", None) == 400:
                    continue
                freemodels.record(mid, False, now)
                _note(now, f"{role}: free model {mid}: {type(e).__name__}")
                break
            u = body.get("usage") or {}
            record(now, role, mid, int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0)), 0.0)
            try:
                out = parse_json(body["choices"][0]["message"]["content"])
            except (ValueError, KeyError, IndexError, TypeError):
                freemodels.record(mid, False, now)
                _note(now, f"{role}: free model {mid} did not return JSON")
                break
            freemodels.record(mid, True, now)
            _last_free[role] = mid
            return out
    return None


def chat(prompt: str, role: str = "cheap", fallback=None, now: dt.datetime | None = None) -> dict:
    """JSON from the model assigned to this role, or from the local fallback when that is not possible."""
    now = now or _now()
    cfg, key = load_config(), api_key()
    model = cfg["models"].get(role, "")
    if cfg["enabled"] and key and model:
        if spent_today(now) >= cfg["daily_budget_usd"]:
            _note(now, f"{role}: the daily cap was reached, used the local model")
        else:
            for _ in range(2):
                try:
                    body = _post(_payload(model, prompt, cfg["max_output_tokens"]), key)
                except Exception as e:  # network, HTTP, auth: never stop the pipeline
                    _note(now, f"{role}: {type(e).__name__}: {e}")
                    break
                _account(now, role, model, body)
                try:
                    return parse_json(body["choices"][0]["message"]["content"])
                except (ValueError, KeyError, IndexError, TypeError):
                    continue
            else:
                _note(now, f"{role}: invalid JSON from {model}, used the local model")
    if cfg["free"] and key:
        got = _free_chat(prompt, role, cfg, key, now)
        if got is not None:
            return got
    if fallback is None:
        raise RuntimeError("no model is available for this job")
    return fallback(prompt)


def decide(question: str, state: str, options: list[str], role: str = "cheap", fallback=None) -> dict:
    """A quick decision with probabilities. One place to plug in a dedicated decision model later."""
    raw = chat(f"{question}\n\nState: {state}\n\nOptions: {json.dumps(options)}\n"
               'Give a probability for every option. Return JSON: {"probs": {"<option>": 0.0}}', role, fallback)
    probs = {o: max(0.0, float((raw.get("probs") or {}).get(o, 0))) for o in options}
    total = sum(probs.values())
    probs = {o: (p / total if total else 1 / len(options)) for o, p in probs.items()}
    choice = max(probs, key=probs.get)
    return {"choice": choice, "probs": probs, "confidence": probs[choice]}


def test_call(role: str) -> dict:
    """One tiny real call, no fallback, so a wrong key or model ID shows its real error."""
    cfg, key = load_config(), api_key()
    model = cfg["models"].get(role, "")
    if not key:
        return {"ok": False, "error": "no OpenRouter key saved yet"}
    if not model:
        return {"ok": False, "error": "no model chosen for this job"}
    start = time.time()
    try:
        body = _post(_payload(model, 'Reply with the JSON {"ok": true}', 50), key)
        usd = _account(_now(), role, model, body)
        parse_json(body["choices"][0]["message"]["content"])
    except Exception as e:
        return {"ok": False, "model": model, "error": f"{type(e).__name__}: {e}"[:300]}
    return {"ok": True, "model": model, "seconds": round(time.time() - start, 1), "usd": usd}
