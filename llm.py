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
            "free": False, "free_daily_limit": 900, "local_fallback": False}  # free: try OpenRouter free models first; local_fallback: ask the local Ollama model when no cloud model answers (slow, off by default)
MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9/._:+-]{1,99}$")
UNKNOWN_PRICE = (10.0, 30.0)  # per million tokens: deliberately high, so an unknown model cannot slip past the cap

# Tokens per finished item, by role: (input, output). Estimates from our prompts; the dashboard shows real spend next to them.
TOKENS = {
    "doc": {"script": (13000, 3000), "review": (2000, 100), "cheap": (1700, 450)},
    "short": {"script": (700, 450), "review": (700, 100), "cheap": (1100, 330)},
    "weekly": {"script": (3000, 800), "cheap": (1200, 400)},  # news digest, trend and channel ideas
}


class ModelUnavailable(RuntimeError):
    """No cloud model could answer. The job stops cleanly and is tried again later; the slow local model is not used unless switched on."""


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
        elif k == "local_fallback":
            if not isinstance(v, bool):
                raise ValueError("the local fallback must be on or off")
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

    saved = json.loads(SETTINGS_FILE.read_text()).get("openrouter_key", "") if SETTINGS_FILE.exists() else ""
    return saved or os.getenv("OPENROUTER_API_KEY", "")  # a key saved in the dashboard wins over the one in .env


def anthropic_key() -> str:
    """A direct Anthropic key (for model ids that start with claude-), from ANTHROPIC_API_KEY or settings.json."""
    import os

    env = os.getenv("ANTHROPIC_API_KEY")
    if env:
        return env
    return json.loads(SETTINGS_FILE.read_text()).get("anthropic_key", "") if SETTINGS_FILE.exists() else ""


def is_claude(model: str) -> bool:
    """Ids like claude-sonnet-5-5 go straight to Anthropic; ids like anthropic/claude-sonnet-4.5 stay on OpenRouter."""
    return model.startswith("claude-")


def key_for(model: str) -> str:
    return anthropic_key() if is_claude(model) else api_key()


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
    prices = model_prices()
    # direct Anthropic ids use dashes (claude-sonnet-4-5), OpenRouter's list uses dots (anthropic/claude-sonnet-4.5)
    pin, pout = prices.get(model) or prices.get("anthropic/" + re.sub(r"(\d)-(\d)", r"\1.\2", model)) or UNKNOWN_PRICE
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


def _post_anthropic(payload: dict, key: str) -> dict:
    """Anthropic's Messages API, with the answer reshaped like an OpenRouter reply so the rest of this module is unchanged."""
    prompt = payload["messages"][0]["content"]
    if payload.get("response_format"):
        prompt += "\n\nReply with one JSON object and nothing else."
    r = requests.post("https://api.anthropic.com/v1/messages", timeout=240,
                      headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                      json={"model": payload["model"], "max_tokens": payload["max_tokens"], "temperature": payload.get("temperature", 0.7),
                            "messages": [{"role": "user", "content": prompt}]})
    r.raise_for_status()
    b = r.json()
    u = b.get("usage") or {}
    text = "".join(c.get("text", "") for c in b.get("content", []) if c.get("type") == "text")
    return {"choices": [{"message": {"content": text}}], "usage": {"prompt_tokens": u.get("input_tokens", 0), "completion_tokens": u.get("output_tokens", 0)}}


def _post(payload: dict, key: str) -> dict:
    if is_claude(payload["model"]):
        return _post_anthropic(payload, key)
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


CHEAP_SHARE = 0.4  # small jobs (titles, tags, picture checks) may use at most this share of the free requests; the rest is for scripts and fact-checks
_last_free: dict[str, str] = {}  # the free model that last answered each role (the reviewer must differ from the writer)


ROUNDS = 3  # passes over the free models; a busy provider (429) usually frees up within a minute or two


def _free_chat(prompt: str, role: str, cfg: dict, key: str, now: dt.datetime) -> dict | None:
    """Try the free models in turn, waiting and trying again when they are all busy. None means: nothing answered."""
    freemodels.refresh(now)
    for rnd in range(ROUNDS):
        models = freemodels.choose(role, now, avoid=_last_free.get("script") if role == "review" else None, n=4)
        if not models:
            break
        for mid in models:
            for json_mode in (True, False):
                if freemodels.remaining(now, key, cfg["free_daily_limit"]) <= 0:
                    _note(now, f"{role}: today's free request allowance is used up")
                    return None
                if role == "cheap" and freemodels.requests_today(now, "cheap") >= int(cfg["free_daily_limit"] * CHEAP_SHARE):
                    return None  # keep the rest of the free requests for scripts and fact-checks
                freemodels.count_request(now, role)  # failed requests count against the limit too
                try:
                    body = _post(_payload(mid, prompt, cfg["max_output_tokens"], json_mode), key)
                except Exception as e:
                    code = getattr(getattr(e, "response", None), "status_code", None)
                    if json_mode and isinstance(e, requests.HTTPError) and code == 400:
                        continue
                    freemodels.record(mid, False, now, status=code)
                    _note(now, f"{role}: free model {mid}: {type(e).__name__}{f' {code}' if code else ''}")
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
        if rnd < ROUNDS - 1:
            time.sleep(20 * (rnd + 1))  # everyone was busy: wait, then ask again
    return None


def chat(prompt: str, role: str = "cheap", fallback=None, now: dt.datetime | None = None) -> dict:
    """JSON from the model assigned to this role, or from the local fallback when that is not possible."""
    now = now or _now()
    cfg, key = load_config(), api_key()
    model = cfg["models"].get(role, "")
    if model and is_claude(model):
        key = anthropic_key()
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
    if cfg["free"] and api_key():
        key = api_key()
        got = _free_chat(prompt, role, cfg, key, now)
        if got is not None:
            return got
    if fallback is None or not cfg.get("local_fallback"):
        raise ModelUnavailable(f"no cloud model answered the {role} job; it will be tried again later")
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
    cfg = load_config()
    model = cfg["models"].get(role, "")
    key = key_for(model) if model else api_key()
    if not key:
        return {"ok": False, "error": "no Anthropic key saved yet" if is_claude(model) else "no OpenRouter key saved yet"}
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
