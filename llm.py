"""Model router: OpenRouter for the jobs where quality matters, the local Ollama model as fallback, a hard daily spend cap.

Roles: script (writing, news summary), review (fact-check, must be a different model), cheap (titles, tags, hooks, ideas).
The API key is read from settings.json or OPENROUTER_API_KEY and is never logged or returned.
"""
import contextlib
import contextvars
import copy
import datetime as dt
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

import config
import filelock
import freemodels

CONFIG_FILE = config.ROOT / "llm.json"
USAGE_FILE = config.ROOT / "data" / "llm_usage.json"
SETTINGS_FILE = config.ROOT / "settings.json"
PRICES_FILE = config.ROOT / "data" / "or_prices.json"
ROLES = ("script", "review", "cheap")
DEFAULTS = {"enabled": False, "models": {"script": "", "review": "", "cheap": ""}, "daily_budget_usd": 1.0, "max_output_tokens": 6000,
            "free": False, "free_daily_limit": 900, "free_timeout_s": 120, "local_fallback": False, "ai_art": False, "free_art": False, "free_art_cap": 9000, "free_review": False}  # free: try OpenRouter free models first; local_fallback: ask the local Ollama model when no cloud model answers (slow, off by default)
MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9/._:+-]{1,99}$")
UNKNOWN_PRICE = (10.0, 30.0)  # per million tokens: deliberately high, so an unknown model cannot slip past the cap

# Tokens per finished item, by role: (input, output). Estimates from our prompts; the dashboard shows real spend next to them.
TOKENS = {
    # measured 19-21 Oct 2026 (data/llm_usage.json): the script is an outline plus one request per chapter carrying the source article, the script gate
    # checks and rewrites it, and a documentary is reviewed several times (first review, picture check, final check, every repair)
    "doc": {"script": (50000, 14000), "review": (25000, 5000), "cheap": (4000, 1200)},
    "short": {"script": (700, 450), "review": (700, 100), "cheap": (1100, 330)},
    "weekly": {"script": (3000, 800), "cheap": (1200, 400)},  # news digest, trend and channel ideas
}


class ModelUnavailable(RuntimeError):
    """No cloud model could answer. The job stops cleanly and is tried again later; the slow local model is not used unless switched on."""


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


# ---- OpenRouter key refused (22 Nov 2026) ----
# A 401 from OpenRouter means the key itself is refused, not the model: on 22 Nov 2026 the FreeLLMAPI key had been saved into the OpenRouter field
# (and the .env key's account no longer existed), every one of 26 OpenRouter models answered 401, each 401 was counted against that model's own
# health, the fact-check was retried hourly for a day, and nobody was told the key was the problem. Now one 401 marks the provider refused for
# OR_REFUSED_HOLD seconds (per key, by a short fingerprint, so saving a new key clears it), the OpenRouter models are skipped meanwhile, model health
# is left alone, and the owner gets one alert a day.
OR_REFUSED_HOLD = 1800
_ATTEMPTS: list = []  # (unix time, model, outcome) of the newest free requests, newest last: what a "no judge answered" message names


def _key_fp(key: str) -> str:
    import hashlib

    return hashlib.sha256((key or "").encode()).hexdigest()[:12]


def _or_auth_file():
    return USAGE_FILE.parent / "openrouter_auth.json"  # beside the usage file, so a test that moves one moves both


def openrouter_refused(now: dt.datetime | None = None, key: str | None = None) -> dict | None:
    """The standing refusal of this OpenRouter key ({"at", "until", "status", "said"}), or None when the key is not known to be refused."""
    now = now or _now()
    try:
        rec = json.loads(_or_auth_file().read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(rec, dict) or rec.get("key_fp") != _key_fp(api_key() if key is None else key):
        return None
    try:
        until = dt.datetime.fromisoformat(str(rec.get("until")).replace("Z", "+00:00"))
    except ValueError:
        return None
    return rec if until > now else None


def _openrouter_refused_now(now: dt.datetime, key: str, status, said: str) -> None:
    path = _or_auth_file()
    try:
        old = json.loads(path.read_text())
    except (OSError, ValueError):
        old = {}
    fp, day = _key_fp(key), now.strftime("%Y-%m-%d")
    told = isinstance(old, dict) and old.get("key_fp") == fp and old.get("alerted_day") == day
    rec = {"key_fp": fp, "at": now.isoformat(timespec="seconds"), "until": (now + dt.timedelta(seconds=OR_REFUSED_HOLD)).isoformat(timespec="seconds"),
           "status": status, "said": re.sub(r"\s+", " ", scrub(said).replace(key or "\0", "***"))[:160], "alerted_day": day}
    try:
        filelock.write_atomic(path, json.dumps(rec))
    except OSError:
        pass
    if not told:
        try:
            import agentlog

            agentlog.event("error", "OpenRouter refused the studio's key",
                           f"HTTP {status}: {rec['said'][:100]}. Every OpenRouter model is skipped until a working key is saved in Settings; "
                           "Google (Gemini key) and your own provider are still asked.", notify=True)
        except Exception:
            pass


def _attempt(mid: str, outcome: str) -> None:
    _ATTEMPTS.append((time.time(), mid, outcome))
    del _ATTEMPTS[:-60]


def attempts_since(t0: float) -> str:
    """'model: outcome; ...' for every free model asked since t0 (its newest outcome), for a plain failure message."""
    last: dict = {}
    for t, mid, outcome in _ATTEMPTS:
        if t >= t0:
            last[mid] = outcome
    return "; ".join(f"{m}: {o}" for m, o in last.items())


def load_config() -> dict:
    cfg = copy.deepcopy(DEFAULTS)
    if CONFIG_FILE.exists():
        raw = json.loads(CONFIG_FILE.read_text())
        cfg.update({k: raw[k] for k in DEFAULTS if k != "models" and k in raw})  # every setting, including local_fallback and ai_art
        cfg["models"].update({k: v for k, v in raw.get("models", {}).items() if k in ROLES})
    return cfg


def save_config(cfg: dict) -> None:
    import checkpoint

    checkpoint.write_text_atomic(CONFIG_FILE, json.dumps({k: cfg[k] for k in DEFAULTS}, indent=2))  # a cut mid-save leaves the owner's last settings whole


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
        elif k == "free_art_cap":
            if isinstance(v, bool) or not isinstance(v, int) or not 100 <= v <= 10000:
                raise ValueError("the free picture allowance must be between 100 and 10,000 Neurons a day")
        elif k in ("local_fallback", "ai_art", "free_art", "free_review"):
            if not isinstance(v, bool):
                raise ValueError(f"{k} must be on or off")
        elif k == "free_daily_limit":
            if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 1000:
                raise ValueError("the free request limit must be between 1 and 1000 a day")
        elif k == "free_timeout_s":
            if isinstance(v, bool) or not isinstance(v, int) or not 10 <= v <= 600:
                raise ValueError("a free model's timeout must be between 10 and 600 seconds")
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
    with filelock.locked(USAGE_FILE):  # the worker, the dashboard and a repair run by hand all write this file
        data = _usage()
        day = data.setdefault(_day(now), {"usd": 0.0, "calls": 0, "by_role": {}, "fallbacks": []})
        mutate(day)
        filelock.write_atomic(USAGE_FILE, json.dumps(data, indent=2))


# ---- what each video has cost ----
_video: contextvars.ContextVar = contextvars.ContextVar("video", default=None)


@contextlib.contextmanager
def cost_scope(slug: str):
    """Spend inside this block (writing, drawing, reviewing, repairing) is added to the video's own total. The outermost scope wins, so a review run inside a
    repair is part of the repair."""
    token = _video.set(slug) if slug and _video.get() is None else None
    try:
        yield
    finally:
        if token is not None:
            _video.reset(token)


def charges_to(key):
    """Decorator: everything the function spends is charged to the video named by key(*args, **kwargs)."""
    import functools

    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a, **k):
            with cost_scope(key(*a, **k)):
                return fn(*a, **k)
        return wrapper
    return deco


def merge_cost(src: str, dest: str) -> None:
    """The script of a video is written before its folder exists: its cost is kept under a temporary name and moved here."""
    path = _costs_file()
    with filelock.locked(path):
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            return
        if src in data:
            data[dest] = round(float(data.get(dest, 0.0)) + float(data.pop(src)), 6)
            filelock.write_atomic(path, json.dumps(data, indent=2))


def _costs_file():
    return config.ROOT / "data" / "video_costs.json"


def video_cost(slug: str) -> float:
    try:
        return float(json.loads(_costs_file().read_text()).get(slug, 0.0))
    except (OSError, ValueError):
        return 0.0


def _add_video_cost(slug: str, usd: float) -> None:
    path = _costs_file()
    with filelock.locked(path):
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            data = {}
        data[slug] = round(float(data.get(slug, 0.0)) + usd, 6)
        filelock.write_atomic(path, json.dumps(data, indent=2))


def record(now: dt.datetime, role: str, model: str, tin: int, tout: int, usd: float, cached: int = 0) -> None:
    def add(day):
        day["usd"] = round(day["usd"] + usd, 6)
        day["calls"] += 1
        r = day["by_role"].setdefault(role, {"usd": 0.0, "calls": 0, "tokens_in": 0, "tokens_out": 0, "model": model})
        r.update(usd=round(r["usd"] + usd, 6), calls=r["calls"] + 1, tokens_in=r["tokens_in"] + tin, tokens_out=r["tokens_out"] + tout, model=model)
        if cached:
            r["cached_in"] = r.get("cached_in", 0) + cached  # input tokens read back from the cache at a tenth of the price
    _save_day(now, add)
    if _video.get():
        _add_video_cost(_video.get(), usd)


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


def estimate(prices: dict, docs_per_day: float, shorts_per_day: float, days: int = 30, art: tuple[float, float] = (0.0, 0.0)) -> dict:
    """Cost from token estimates and per-role prices {role: (in, out) $/Mtok}, plus `art` = (documentary, Short) dollars for AI pictures (the biggest
    single cost: 95 pictures, $3.19, on 20 Oct). A first try with no repairs: the real spend shows next to it."""
    def cost(kind):
        by = {r: (tin * prices[r][0] + tout * prices[r][1]) / 1e6 for r, (tin, tout) in TOKENS[kind].items() if r in prices}
        return sum(by.values()), by
    doc, doc_by = cost("doc")
    short, short_by = cost("short")
    weekly, weekly_by = cost("weekly")
    doc, short = doc + art[0], short + art[1]
    per_day = docs_per_day * doc + shorts_per_day * short
    by_role = {r: (docs_per_day * doc_by.get(r, 0) + shorts_per_day * short_by.get(r, 0)) * days + weekly_by.get(r, 0) * days / 7 for r in ROLES}
    return {"per_doc_usd": doc, "per_short_usd": short, "weekly_usd": weekly, "per_day_usd": per_day, "art_per_doc_usd": art[0], "art_per_short_usd": art[1],
            "per_month_usd": per_day * days + weekly * days / 7, "by_role": by_role}


# ---- calls ----
_THINK_BLOCK = re.compile(r"<(think|thinking|reasoning)\b[^>]*>.*?</\1\s*>", re.S | re.I)
_THINK_OPEN = re.compile(r"<(think|thinking|reasoning)\b[^>]*>", re.I)
_THINK_CLOSE = re.compile(r"</(think|thinking|reasoning)\s*>", re.I)


def strip_think(text: str) -> str:
    """A reply with the model's reasoning taken out: every <think>...</think> block (also <thinking> and <reasoning>), everything before a closing tag
    whose opening tag the model left out (DeepSeek R1 style templates open it in the prompt), and everything after an opening tag that is never
    closed (all reasoning, no answer). 22 Nov 2026: parse_json reads the first complete JSON object, so a JSON draft inside a reasoning block
    ("I could answer {"invented_facts": 0} ... no, 8") would have been read as the judge's verdict."""
    t = _THINK_BLOCK.sub(" ", str(text or ""))
    closes = list(_THINK_CLOSE.finditer(t))
    if closes:
        t = t[closes[-1].end():]
    opened = _THINK_OPEN.search(t)
    return t[:opened.start()] if opened else t


def parse_json(text: str) -> dict:
    """The first complete JSON object in the text (handles models that add reasoning before or after the JSON, or wrap it in a code fence).
    20 Nov 2026: a brace counter that ignored strings rejected a reply whose text held a lone brace ("a { in text") once anything surrounded the
    JSON; json's own decoder, tried at each opening brace, reads strings correctly. A reply that is not plain JSON has its reasoning blocks
    removed first (strip_think), so JSON written while thinking is never taken for the answer."""
    text = (text or "").strip()
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except ValueError:
        pass
    text = strip_think(text).strip()
    decoder = json.JSONDecoder()
    at = text.find("{")
    while at != -1:
        try:
            value, _end = decoder.raw_decode(text, at)
            if isinstance(value, dict):
                return value
        except ValueError:
            pass
        at = text.find("{", at + 1)
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


# ---- the owner's own OpenAI-compatible provider (17 Nov 2026): a FreeLLMAPI proxy on this PC, DeepSeek, GLM, anything that speaks /v1/chat/completions ----
# Settings (settings.json, owner-only): extra_llm_on, extra_llm_url, extra_llm_local, extra_llm_key (write-only), extra_llm_models {"script": "a, b", "review": "c"}.
# Its models are asked before the OpenRouter free ones and cost nothing here (calls and tokens are still counted); only public text is ever sent to it.
EXTRA_PREFIX = "extra:"
EXTRA_TIMEOUT = 120
# Google AI Studio directly (22 Nov 2026, the judge cascade's first choice for slot A): only when the owner puts GEMINI_API_KEY in .env. Google's own
# OpenAI-compatible endpoint, read at ai.google.dev/gemini-api/docs/openai on 22 Nov 2026 (Bearer key, /chat/completions). Free-tier limits are per Google
# project, not per key, so a key from the project FreeLLMAPI already uses adds no capacity. Only public text (script, source article) is ever sent.
GEMINI_PREFIX = "gemini:"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
GEMINI_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"  # read-only model list: the Settings key test (geminikey.py) asks only this


def gemini_key() -> str:
    """GEMINI_API_KEY from .env, else the key the owner saved in Settings (settings.json `gemini_api_key`, 22 Nov 2026). Never logged or returned."""
    import os

    env = os.getenv("GEMINI_API_KEY", "").strip()
    if env:
        return env
    try:
        return str(json.loads(SETTINGS_FILE.read_text()).get("gemini_api_key", "")).strip() if SETTINGS_FILE.exists() else ""
    except (OSError, ValueError):
        return ""
_MODEL_NAME = re.compile(r"^[A-Za-z0-9._:/-]{1,80}$")
_url_cache: dict = {}


def extra_url_ok(url: str, local: bool) -> tuple[bool, str]:
    """(ok, why). https to a public host, or plain http to this PC only when the owner ticked the local-box option. Never credentials in the address, never a name that resolves to a private address."""
    import ipaddress
    import socket
    from urllib.parse import urlparse

    u = urlparse(str(url or "").strip())
    if u.scheme not in ("http", "https") or not u.hostname or u.username or u.password:
        return False, "the address must start with https:// (or http:// to this PC) and hold no user name or password"
    if u.scheme == "http":
        if u.hostname in ("127.0.0.1", "localhost", "::1") and local:
            return True, ""
        return False, "plain http is only allowed to this PC, and only with the local-box option ticked"
    try:
        infos = socket.getaddrinfo(u.hostname, u.port or 443, proto=socket.IPPROTO_TCP)
    except OSError:
        return False, "that host name does not resolve"
    for info in infos:
        if not ipaddress.ip_address(info[4][0]).is_global:
            return False, "that address points inside a private network"
    return True, ""


def _extra_models_of(raw) -> list[str]:
    names = [n.strip() for n in str(raw or "").split(",")]
    return [n for n in names if _MODEL_NAME.match(n)][:6]


# A name the provider resolves to a model of its own choosing. Never a judge: on 20 Nov 2026 the proxy's "auto" served the studio's requests with
# poolside/laguna-xs-2.1, nemotron-3-ultra and once gemini-3.6-flash, which was also on the writer list, so "auto" could have judged its own script.
ROUTER_NAMES = frozenset({"auto", "fusion", "router", "default"})


# Model lines and the maker each belongs to (22 Nov 2026), for two rules: a writer never judges its own script under ANY provider's name for it, and the
# two judges of a video come from different families. A name carries a family when one of its parts is a line below ("deepseek-r1-distill-qwen-32b" is both
# DeepSeek and Qwen: it then shares a family with either). A line not listed is its own family.
FAMILY_OF = {"gemini": "google", "gemma": "google", "nemotron": "nvidia", "nemoguard": "nvidia", "cosmos": "nvidia", "llama": "meta", "muse": "meta",
             "qwen": "qwen", "qwq": "qwen", "deepseek": "deepseek", "glm": "zhipu", "mistral": "mistral", "ministral": "mistral", "devstral": "mistral",
             "codestral": "mistral", "magistral": "mistral", "pixtral": "mistral", "voxtral": "mistral", "gpt": "openai", "claude": "anthropic", "kimi": "moonshot",
             "minimax": "minimax", "grok": "xai", "ernie": "baidu", "ling": "inclusionai", "ring": "inclusionai", "lfm": "liquid", "step": "stepfun",
             "phi": "microsoft", "granite": "ibm", "command": "cohere", "aya": "cohere", "hermes": "nous", "laguna": "poolside", "dots": "rednote",
             "hunyuan": "tencent", "mimo": "xiaomi"}
# The owner's FreeLLMAPI glues the maker onto the name ("nvidianemotron-3-ultra-550b-a55b", "minimaxaiminimax-m3.1-flash", "deepseek-aideepseek-v4.1-flash")
# or joins it with a hyphen ("google-gemma-3-27b"); OpenRouter puts it in front of a slash. Seen in the proxy's own model list on 22 Nov 2026.
VENDORS = {"deepseek-ai": "deepseek", "minimaxai": "minimax", "moonshotai": "moonshot", "mistralai": "mistral", "meta-llama": "meta", "stepfun-ai": "stepfun",
           "inclusionai": "inclusionai", "zhipuai": "zhipu", "z-ai": "zhipu", "nvidia": "nvidia", "google": "google", "openai": "openai", "meta": "meta",
           "poolside": "poolside", "xiaomi": "xiaomi", "tencent": "tencent", "baidu": "baidu", "microsoft": "microsoft", "ibm": "ibm", "qwen": "qwen",
           "mistral": "mistral", "anthropic": "anthropic", "x-ai": "xai", "liquid": "liquid", "minimax": "minimax", "deepseek": "deepseek"}
_LINES = sorted(FAMILY_OF, key=len, reverse=True)
_QUALIFIER = re.compile(r"-(?:it|instruct|preview|exp|experimental|latest|fp8|fp4|fast|a\d+(?:\.\d+)?b|\d{4})$")


def _bare(mid) -> str:
    """The id without the studio's provider prefixes (extra:, gemini:), the OpenRouter alias mark (~), the vendor path and the :free style tag, lower case."""
    m = str(mid or "").strip().lower()
    for p in (EXTRA_PREFIX, GEMINI_PREFIX):
        if m.startswith(p):
            m = m[len(p):]
    return m.lstrip("~").rsplit("/", 1)[-1].split(":", 1)[0]


def _unglue(name: str) -> tuple[str, str]:
    """(maker, name) when a maker's name is glued or hyphenated onto a model line ("nvidianemotron-..." -> ("nvidia", "nemotron-...")); ("", name) otherwise."""
    for v in sorted(VENDORS, key=len, reverse=True):
        if not name.startswith(v):
            continue
        rest = name[len(v):]
        rest = rest[1:] if rest.startswith("-") else rest
        if rest and any(rest.startswith(k) for k in _LINES):
            return v, rest
    return "", name


def model_identity(mid) -> str:
    """The model behind an id, for the rule that a writer never judges its own script: no `extra:`/`gemini:` prefix, no vendor path, no `:free` tag, no
    maker glued on by the owner's proxy, no packaging words (-it, -instruct, -preview, -fp8, the MoE "-a55b", a "-2506" date), lower case.
    extra:gemini-3.6-flash, google/gemini-3.6-flash and gemini-3.6-flash:free are one model; so are nvidia/nemotron-3-ultra-550b-a55b:free,
    extra:nvidianemotron-3-ultra-550b-a55b and extra:nemotron-3-ultra-550b (22 Nov 2026: compared as typed, they looked like three models).
    Calling two names one model when they are not only removes a judge; the opposite would let a writer judge itself, so the rule leans this way."""
    m = _unglue(_bare(mid))[1]
    m = re.sub(r"^(" + "|".join(map(re.escape, _LINES)) + r")(?=\d)", r"\1-", m)  # qwen3.8-27b and qwen-3.8-27b
    while _QUALIFIER.search(m):
        m = _QUALIFIER.sub("", m)
    return m


def model_family(mid) -> frozenset:
    """The makers whose model line this id belongs to (see FAMILY_OF): {"google"} for any Gemini or Gemma, {"deepseek", "qwen"} for a DeepSeek distil of Qwen.
    A line the table does not know is its own family (its first word), so two unknown models of different names count as different families."""
    raw = str(mid or "").strip().lower()
    for p in (EXTRA_PREFIX, GEMINI_PREFIX):
        if raw.startswith(p):
            raw = raw[len(p):]
    out = set()
    if "/" in raw:
        out.add(VENDORS.get(raw.lstrip("~").rsplit("/", 1)[0].rsplit("/", 1)[-1], ""))
    vendor, name = _unglue(_bare(mid))
    out.add(VENDORS.get(vendor, ""))
    for part in re.split(r"[^a-z0-9]+", name):
        word = re.match(r"[a-z]+", part)
        if word and word.group() in FAMILY_OF:
            out.add(FAMILY_OF[word.group()])
    out.discard("")
    if not out:
        first = re.match(r"[a-z]+", name)
        out.add(first.group() if first else name)
    return frozenset(out)


def same_family(a, b) -> bool:
    return bool(model_family(a) & model_family(b))


ROUTER_IDS = frozenset(ROUTER_NAMES | {"free", "free-router", "auto-route", "kilo-auto", "bazaarlink-auto", "logfare-auto"})


def is_router(mid) -> bool:
    """A name that lets the provider pick the model (openrouter/free, the owner's "auto"): its family is unknown until it has answered."""
    ident = model_identity(mid)
    return ident in ROUTER_IDS or str(mid).lower().startswith("openrouter/") or "auto" in ident.split("-")


def answer_family(mid) -> frozenset | None:
    """The makers behind one judge's answer: the id asked and the model the provider said answered. None when a router answered without saying which
    model it used: then nobody can show that a second judge is of another family, so the pair is not independent."""
    served = _served.get(mid or "", "")
    if is_router(mid) and (not served or is_router(served)):
        return None
    return model_family(mid) | (model_family(served) if served else frozenset())


def judge_names_problem(script, review) -> str:
    """Why a judge list breaks the writer-is-never-the-judge rule ("" when it does not): a router name, or a model that is also on the writer list."""
    writers = {model_identity(n) for n in script}
    for n in review:
        if str(n).lower() in ROUTER_NAMES:
            return f'the judge "{n}" lets the provider choose the model, and it could choose the writer: name a model instead'
        if model_identity(n) in writers:
            return f'"{n}" is on both lists: a judge must be a different model from every script model'
    return ""


def extra_cfg() -> dict | None:
    """The provider's settings when it is on, has a key and an address the rules accept; None otherwise. Not in a user studio."""
    try:
        import tenantmode

        if tenantmode.is_tenant():
            return None
    except Exception:
        pass
    try:
        s = json.loads(SETTINGS_FILE.read_text()) if SETTINGS_FILE.exists() else {}
    except (OSError, ValueError):
        return None
    if not s.get("extra_llm_on") or not s.get("extra_llm_key") or not s.get("extra_llm_url"):
        return None
    url, local = str(s["extra_llm_url"]).strip(), bool(s.get("extra_llm_local"))
    hit = _url_cache.get((url, local))
    if not hit or time.monotonic() - hit[0] > 300:
        hit = (time.monotonic(), extra_url_ok(url, local)[0])
        _url_cache[(url, local)] = hit
    if not hit[1]:
        return None
    models = s.get("extra_llm_models") or {}
    return {"url": url.rstrip("/"), "key": s["extra_llm_key"], "script": _extra_models_of(models.get("script")), "review": _extra_models_of(models.get("review"))}


def extra_models(role: str) -> list[str]:
    """Model ids (prefixed `extra:`) the owner's provider offers for this role; small jobs use the writer list. A judge is never a router name or a
    model that is also on the writer list: refused when the settings are saved, and dropped here too in case the settings file was edited by hand."""
    cfg = extra_cfg()
    if not cfg:
        return []
    if role != "review":
        return [EXTRA_PREFIX + m for m in cfg["script"]]
    writers = {model_identity(n) for n in cfg["script"]}
    return [EXTRA_PREFIX + m for m in cfg["review"] if m.lower() not in ROUTER_NAMES and model_identity(m) not in writers]


# The provider's own word on its models (GET /models). A FreeLLMAPI proxy marks a model whose free quota is used up "exhausted": on 20 Nov 2026 both
# Gemini models were exhausted until Google's 08:00 UTC reset (Retry-After 12796 s), yet the studio asked them again every five minutes because a
# 429 is believed for at most MAX_RETRY_AFTER. Reading the list costs one local request a minute and no model quota.
CATALOG_TTL = 60
UNUSABLE = frozenset({"exhausted", "needsKey", "unavailable"})
_catalog: dict = {}


def _catalog_get(url: str, key: str):
    return requests.get(url + "/models", headers={"Authorization": f"Bearer {key}"}, timeout=5, allow_redirects=False)


def extra_catalog() -> dict | None:
    """{model id: status} from the provider's model list, kept CATALOG_TTL seconds: "ready", "exhausted", "needsKey", "unavailable", or None when the
    provider gives no status for a model. None for the whole list when it cannot be read: each request then finds out for itself, as before."""
    cfg = extra_cfg()
    if not cfg:
        return None
    hit = _catalog.get(cfg["url"])
    if hit and time.monotonic() - hit[0] < CATALOG_TTL:
        return hit[1]
    out = None
    try:
        r = _catalog_get(cfg["url"], cfg["key"])
        r.raise_for_status()
        out = {}
        for m in (r.json() or {}).get("data") or []:
            if isinstance(m, dict) and m.get("id"):
                st = m.get("execution_status")
                out[str(m["id"])] = "unavailable" if m.get("available") is False and st in (None, "ready") else (str(st) if st else None)
    except Exception:
        out = None
    _catalog[cfg["url"]] = (time.monotonic(), out)
    return out


def extra_status(mid: str) -> str | None:
    """The provider's status for one of its models (with or without the `extra:` prefix); None when unknown."""
    cat = extra_catalog() or {}
    return cat.get(mid[len(EXTRA_PREFIX):] if mid.startswith(EXTRA_PREFIX) else mid)


def extra_error(e) -> str:
    """A provider failure in plain words: the provider's own message, quota used up or only rate limited, and when to try again. The key is scrubbed out."""
    r = getattr(e, "response", None)
    code = getattr(r, "status_code", None)
    msg = ""
    if r is not None:
        try:
            j = r.json()
            err = j.get("error") if isinstance(j, dict) else None
            msg = str((err.get("message") if isinstance(err, dict) else err) or j.get("message") or "")
        except Exception:
            msg = str(getattr(r, "text", "") or "")[:200]
    if not code:
        return scrub(f"{type(e).__name__}: {e}")[:300]
    text = f"HTTP {code}: {msg or 'no message'}"
    if code == 429:
        kind = "quota used up" if re.search(r"exhaust|quota|per day|daily", msg, re.I) else "rate limited"
        text = f"{kind} (HTTP 429): {msg or 'no message'}"
        ra = str((getattr(r, "headers", None) or {}).get("Retry-After") or "")
        if ra.isdigit():
            text += f" Try again after {(_now() + dt.timedelta(seconds=int(ra))):%H:%M} UTC."
    return scrub(text)[:300]


FREE_WAIT_LIMIT = 150  # seconds a call will wait for a busy model to come back before it gives up
_extra_last: dict = {}


def _pace_extra(mid: str) -> None:
    """A pooled free provider allows only so many requests a minute per model: keep a gap (settings `extra_llm_gap_s`, default 6 seconds, 0 = off) between calls to the same one."""
    try:
        gap = float((json.loads(SETTINGS_FILE.read_text()) if SETTINGS_FILE.exists() else {}).get("extra_llm_gap_s", 6))
    except (OSError, ValueError, TypeError):
        gap = 6.0
    if gap > 0:
        wait = gap - (time.monotonic() - _extra_last.get(mid, -1e9))
        if wait > 0:
            time.sleep(wait)
    _extra_last[mid] = time.monotonic()


def scrub(text) -> str:
    """Error text with the provider's key (and the OpenRouter key) taken out, before it is shown or stored anywhere."""
    t = str(text)
    try:
        s = json.loads(SETTINGS_FILE.read_text()) if SETTINGS_FILE.exists() else {}
    except (OSError, ValueError):
        s = {}
    for secret in (s.get("extra_llm_key"), s.get("openrouter_key"), gemini_key()):
        if secret:
            t = t.replace(secret, "***")
    return t


def _bounded_post(url: str, *, timeout: float, **kw):
    """requests.post with a TOTAL time limit. requests' own timeout only limits the gap between two received bytes, and OpenRouter keeps a slow request alive by
    sending whitespace, so a free judge once held a request for 600.8 s against a 120 s limit and a documentary's fact-check stalled (20 Nov 2026). The answer is
    read in pieces and dropped (requests.Timeout) once the limit has passed. An error answer is read the same way, so its status and text reach the caller."""
    r = requests.post(url, timeout=timeout, stream=True, **kw)
    read = getattr(r, "iter_content", None)
    if read is None:  # a stand-in answer (tests): nothing to stream
        return r
    deadline = time.monotonic() + float(timeout)
    buf = bytearray()
    try:
        for chunk in read(16384):
            buf += chunk
            if time.monotonic() > deadline:
                raise requests.Timeout(f"no complete answer within {float(timeout):.0f} s")
    finally:
        r.close()
    r._content, r._content_consumed = bytes(buf), True
    return r


def _post_extra(payload: dict) -> dict:
    cfg = extra_cfg()
    if not cfg:
        raise RuntimeError("the extra model provider is off, has no key, or its address is refused")
    timeout = min(EXTRA_TIMEOUT, float(payload.get("_extra_timeout_s") or EXTRA_TIMEOUT))  # a judge with a deadline asks for less (judges.py)
    body = {k: v for k, v in payload.items() if k != "usage" and not k.startswith("_")}  # `usage` is an OpenRouter field; _names are the studio's own
    body["model"] = payload["model"][len(EXTRA_PREFIX):]
    r = _bounded_post(cfg["url"] + "/chat/completions", json=body, timeout=timeout, allow_redirects=False,
                      headers={"Authorization": f"Bearer {cfg['key']}", "Content-Type": "application/json"})
    r.raise_for_status()
    return r.json()


def _post_gemini(payload: dict, timeout: float) -> dict:
    """Google AI Studio's OpenAI-compatible chat endpoint with GEMINI_API_KEY. No OpenRouter fields (usage, reasoning), no redirects."""
    key = gemini_key()
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set in .env")
    body = {k: v for k, v in payload.items() if k not in ("usage", "reasoning") and not k.startswith("_")}
    body["model"] = payload["model"][len(GEMINI_PREFIX):]
    return _gemini_chat(key, body, timeout)


def gemini_models() -> list[str]:
    """The Gemini models the judges may ask directly (config/judges.json, ids with the gemini: prefix), in the configured order."""
    return _judge_ids(GEMINI_PREFIX)


def judge_extra_models() -> list[str]:
    """The owner's provider models the judge cascade names (config/judges.json, ids with the extra: prefix), for the script fact-check too: on 23 Nov 2026
    the fact-check could ask only the Settings review list (Gemini, down at Google, and Nemotron), so with the one-family rule it could never get a second
    family, while the cascade's GLM (Zhipu) and Qwen judges were answering. Never a router, never a model on the provider's writer list; none without the provider."""
    cfg = extra_cfg()
    if not cfg:
        return []
    writers = {model_identity(n) for n in cfg["script"]}
    return [m for m in _judge_ids(EXTRA_PREFIX) if not is_router(m) and model_identity(m) not in writers]


def picture_sharing_models() -> list[str]:
    """Judges whose provider spends the free picture allowance (config/judges.json `shares_picture_allowance`): asked after every other judge."""
    try:
        return list(json.loads((config.ROOT / "config" / "judges.json").read_text()).get("shares_picture_allowance") or [])
    except (OSError, ValueError):
        return []


def _judge_ids(prefix: str) -> list[str]:
    """Every id with this prefix in config/judges.json, in the configured order, once each."""
    try:
        cfg = json.loads((config.ROOT / "config" / "judges.json").read_text())
    except (OSError, ValueError):
        return []
    found: list[str] = []

    def walk(v):
        if isinstance(v, str) and v.startswith(prefix):
            found.append(v)
        elif isinstance(v, (list, tuple)):
            for x in v:
                walk(x)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
    walk(cfg)
    return list(dict.fromkeys(found))


_GEMINI_AUTH = {}  # key prefix -> the header style Google accepted ("bearer" or "goog"); remembered for this process only


def _gemini_auth(key: str, style: str) -> dict:
    return {"Authorization": f"Bearer {key}"} if style == "bearer" else {"x-goog-api-key": key}


def _gemini_chat(key: str, body: dict, timeout: float) -> dict:
    """One chat request to Google's OpenAI-compatible endpoint. 22 Nov 2026: AI Studio now issues keys starting 'AQ.' and developers report that some are
    refused (401) with the OpenAI-style Bearer header; Google's own `x-goog-api-key` header is tried once on a 401 or 403, and the style that worked is kept."""
    kind = "aq" if key.startswith("AQ.") else "aiza"
    # Bearer first for both kinds: the owner's AQ. key answered with Bearer and was refused with x-goog-api-key ("Missing or invalid Authorization
    # header", HTTP 400, measured 22 Nov 2026), so a 400 that names the Authorization header counts as an auth refusal like 401 and 403
    styles = [_GEMINI_AUTH[kind]] if kind in _GEMINI_AUTH else ["bearer", "goog"]
    r = None
    for style in styles:
        r = _bounded_post(GEMINI_URL + "/chat/completions", json=body, timeout=timeout, allow_redirects=False,
                          headers={**_gemini_auth(key, style), "Content-Type": "application/json"})
        code = getattr(r, "status_code", 0)
        auth_refused = code in (401, 403) or (code == 400 and "authorization" in str(getattr(r, "text", "")).lower())
        if not auth_refused:
            _GEMINI_AUTH[kind] = style
            break
    r.raise_for_status()
    return r.json()


def gemini_ping(key: str, model: str, timeout: float = 30) -> str:
    """The Settings test: one tiny question through the same path the judges use. Its answer text; raises on failure (callers scrub the message)."""
    body = {"model": model, "messages": [{"role": "user", "content": "Reply with the single word: pong"}], "max_tokens": 20}
    out = _gemini_chat(key, body, timeout)
    return str(((out.get("choices") or [{}])[0].get("message") or {}).get("content", ""))[:40]


def extra_ping(model: str) -> str:
    """One tiny question to a provider model for the Settings test button: its answer text. Raises on failure (callers scrub the message with `scrub`)."""
    body = _post(_payload(model, "Reply with the single word: pong", 50, json_mode=False, role="cheap"), "")
    return str(((body.get("choices") or [{}])[0].get("message") or {}).get("content", ""))[:80]


def _post(payload: dict, key: str) -> dict:
    timeout = payload.pop("_timeout_s", None) or 240  # the free path puts a free model's limit here (`free_timeout_s`); it is never sent to the provider
    if payload["model"].startswith(EXTRA_PREFIX):
        if timeout < EXTRA_TIMEOUT:
            payload["_extra_timeout_s"] = timeout
        return _post_extra(payload)
    if payload["model"].startswith(GEMINI_PREFIX):
        return _post_gemini(payload, timeout)
    if is_claude(payload["model"]):
        return _post_anthropic(payload, key)
    r = _bounded_post("https://openrouter.ai/api/v1/chat/completions", json=payload, timeout=timeout,
                      headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "X-Title": "Story Studio"})
    r.raise_for_status()
    return r.json()


# A judge must give the same verdict for the same text: with 0.7 the same script scored 5/10, 3/10 and 4/10 on 20-21 Oct 2026 and videos flipped
# between pass and fail without any change. The writer keeps some freedom; small helper jobs a little.
TEMPERATURE = {"review": 0.0, "cheap": 0.3, "script": 0.7}


# Prompt caching (OpenRouter, Anthropic models): the part of a prompt that repeats from call to call (the source article, the standing rules) is read back at a
# tenth of the input price, written once at 1.25 times, and lives 5 minutes (checked 28 Oct 2026 against openrouter.ai/docs/guides/best-practices/prompt-caching).
# A caller marks the boundary with `cached(stable, rest)`: the invisible CACHE_MARK sits between the two parts, so every function that passes a prompt along
# keeps its signature. Below CACHE_MIN_CHARS (about 600 tokens, over the 512 of the Claude 5.5 models) or for a model that is not anthropic/, it is only removed.
CACHE_MARK = "\u2063"
CACHE_MIN_CHARS = 2400


def cached(stable: str, rest: str) -> str:
    """A prompt whose first part (`stable`) is the same on every call of a series: it is sent as a cache block."""
    return stable.replace(CACHE_MARK, "") + CACHE_MARK + rest.replace(CACHE_MARK, "")


def _content(model: str, prompt: str):
    stable, mark, rest = prompt.partition(CACHE_MARK)
    if not mark:
        return prompt
    if model.startswith("anthropic/") and len(stable) >= CACHE_MIN_CHARS and rest.strip():
        return [{"type": "text", "text": stable, "cache_control": {"type": "ephemeral"}}, {"type": "text", "text": rest}]
    return stable + rest


def _payload(model: str, prompt: str, max_tokens: int, json_mode: bool = True, role: str = "script") -> dict:
    p = {"model": model, "messages": [{"role": "user", "content": _content(model, prompt)}], "max_tokens": max_tokens, "temperature": TEMPERATURE.get(role, 0.7), "usage": {"include": True}}
    if json_mode:  # some free models reject JSON mode: they are asked again without it
        p["response_format"] = {"type": "json_object"}
    return p


def _account(now, role, model, body) -> float:
    u = body.get("usage") or {}
    tin, tout = int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0))
    usd = float(u["cost"]) if u.get("cost") is not None else _usd(model, tin, tout)
    record(now, role, model, tin, tout, usd, cached=int((u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0))
    return usd


CHEAP_SHARE = 0.4  # small jobs (titles, tags, picture checks) may use at most this share of the free requests; the rest is for scripts and fact-checks
_last_free: dict[str, str] = {}  # the free model that last answered each role (the reviewer must differ from the writer)
_served: dict[str, str] = {}  # the model the owner's provider said answered each of its ids last (the reply's "model" field; "auto" is a different model each time)
_WRITERS: set = set()  # every model that wrote script text in this process since begin_script(), and what the provider served it as


def begin_script() -> None:
    """A new script starts: forget the writers of the previous one."""
    _WRITERS.clear()


def writers() -> list[str]:
    """The models that wrote the current script (ids, and the model the provider served them as). The video's record keeps them (`script_writers`)
    so a judge in a later process avoids them too: `_last_free` lives only as long as the process that wrote the script (20 Nov 2026)."""
    return sorted(_WRITERS)


def _answered(role: str, mid: str) -> None:
    _last_free[role] = mid
    if role == "script":
        _WRITERS.add(mid)
        if _served.get(mid):
            _WRITERS.add(_served[mid])


REVIEW_RESERVE_USD = 0.50  # the quality gate may spend this much past the daily cap, so a reached cap never leaves videos unreviewed


ROUNDS = 3  # passes over the free models; a busy provider (429) usually frees up within a minute or two
FREE_TIMEOUT = 120  # seconds a free model gets to answer (llm.json `free_timeout_s`; the paid models keep 240)
FREE_MAX_TOKENS = 16000  # the ceiling llm.validate_config sets: a cut-off free reply is asked again once, with up to this much room
RACE_ROLES = ("script", "review")  # the jobs where a wrong or missing answer costs the most: two models are asked at once


REASONING_BUDGET = {"script": 1024, "review": 3000, "cheap": 512}  # thinking tokens a free OpenRouter model may spend before it answers (20 Nov 2026: measured on
# nvidia/nemotron-3.5-super-vl:free with a 6-line writing job: default and effort "low" both spent all 6,000 output tokens thinking and returned no JSON; a 1,024
# budget answered with 6 valid lines in 9.7 s, thinking off in 1.6 s. Writers and judges were cut off this way all morning and a documentary could not be written)


class _NoAllowance(Exception):
    """Today's free requests (or the cheap share of them) are used up: no round of waiting will help."""


def _fail_kind(e, code, said: str) -> str:
    """What a failed request means for the judge cascade: busy (429), quota (429 saying the day's or the account's free requests are used up),
    down (502/503/504), timeout, unreachable (no connection at all), refused (other 4xx), error."""
    if code == 429:
        return "quota" if re.search(r"per.?day|daily|quota|exhaust|free-models-per-day|credits", said) else "busy"
    if code in (502, 503, 504):
        return "down"
    if isinstance(e, requests.ConnectionError) and not isinstance(e, requests.Timeout):
        return "unreachable"
    if isinstance(e, requests.Timeout):
        return "timeout"
    return "refused" if code and 400 <= code < 500 else "error"


def _reset_after(e) -> int | None:
    """Seconds until the provider says its limit resets (OpenRouter's X-RateLimit-Reset, epoch milliseconds), capped at a day; None when it does not say."""
    try:
        ms = int(float(((getattr(getattr(e, "response", None), "headers", None) or {}).get("X-RateLimit-Reset"))))
    except (TypeError, ValueError):
        return None
    left = ms / 1000 - time.time()
    return int(min(left, 86400)) if left > 0 else None


def _ask_free(mid: str, prompt: str, role: str, cfg: dict, key: str, now: dt.datetime, *, deadline: float | None = None, once: bool = False,
              why: dict | None = None, cap: int | None = None, think: int | None = None) -> dict | None:
    """One free model asked once (JSON mode, then plain when the provider refuses JSON). Counts the request and records the outcome;
    None means it failed, so the caller moves on. Raises `_NoAllowance` before asking when the day's requests are used up.
    A reply the output limit cut off (`finish_reason: length`) is asked once more with twice the room, because a reasoning model can spend the
    whole cap on thinking and never reach its JSON (three of six failing review models on 17 Nov 2026).
    The judge cascade (judges.py, 22 Nov 2026) may add: `deadline` (time.monotonic) bounds the whole call, re-asks included; `once` sends no second
    request after a cut-off reply; `why` (a dict) is filled with the failure kind (see _fail_kind), the status and any reset time; `cap` the output
    tokens; `think` the thinking budget of an OpenRouter model. A request ended by a short deadline is not held against the model (reason "deadline")."""
    _served.pop(mid, None)  # what answered THIS request only: a router's earlier "served as" must not name a later reply that names no model (24 Nov 2026 review)
    is_extra = mid.startswith(EXTRA_PREFIX)
    via_or = not (is_extra or mid.startswith(GEMINI_PREFIX))  # the owner's provider and Google directly need none of OpenRouter's allowance
    if via_or and freemodels.remaining(now, key, cfg["free_daily_limit"]) <= 0:
        _note(now, f"{role}: today's free request allowance is used up")
        if why is not None:
            why.update(kind="quota", status=None)
        raise _NoAllowance
    if via_or and role == "cheap" and freemodels.requests_today(now, "cheap") >= int(cfg["free_daily_limit"] * CHEAP_SHARE):
        raise _NoAllowance  # keep the rest of the free requests for scripts and fact-checks
    if via_or and openrouter_refused(now, key):
        if why is not None:
            why.update(kind="refused", status=401)
        _attempt(mid, "skipped, OpenRouter key refused")
        return None
    json_mode, cap, retried = True, int(cap or cfg["max_output_tokens"]), False
    reasoning = {"max_tokens": think if think is not None else REASONING_BUDGET.get(role, 1024)} if via_or else None  # OpenRouter's free reasoning models: a thinking budget, so the answer gets written
    limit = float(cfg.get("free_timeout_s") or FREE_TIMEOUT)
    while True:
        if deadline is not None and deadline - time.monotonic() < 2:
            if why is not None:
                why.update(kind="timeout", status=None)
            _note(now, f"{role}: free model {mid}: the judge's time ran out before it was asked again")
            return None
        if via_or:
            freemodels.count_request(now, role)  # failed requests count against the limit too
        elif is_extra:
            _pace_extra(mid)
        t0 = time.monotonic()
        payload = _payload(mid, prompt, cap, json_mode, role)
        if reasoning is not None:
            payload["reasoning"] = reasoning
        sent_limit = min(limit, deadline - time.monotonic()) if deadline is not None else limit
        payload["_timeout_s"] = sent_limit
        try:
            body = _post(payload, key)
        except Exception as e:
            code = getattr(getattr(e, "response", None), "status_code", None)
            said = (str(getattr(getattr(e, "response", None), "text", "") or "") + " " + str(e)).lower()
            if reasoning is not None and isinstance(e, requests.HTTPError) and code == 400 and "reasoning" in said:
                reasoning = None  # a model that refuses the thinking budget is asked again exactly as before 20 Nov 2026
                continue
            if json_mode and isinstance(e, requests.HTTPError) and code == 400:
                json_mode = False  # some free models reject JSON mode: ask the same one again without it
                continue
            if reasoning is not None and isinstance(e, requests.HTTPError) and code == 400:
                reasoning = None  # refused again without JSON mode and the error named nothing: the budget is the last thing to drop
                continue
            try:
                ra = int(float((getattr(getattr(e, "response", None), "headers", None) or {}).get("Retry-After")))
            except (TypeError, ValueError):
                ra = None
            if via_or and code == 401:  # the key is refused, not this model: no mark against the model, one provider-wide record and alert
                _openrouter_refused_now(now, key, code, str(getattr(getattr(e, "response", None), "text", "") or e))
                if why is not None:
                    why.update(kind="refused", status=code)
                _attempt(mid, "OpenRouter key refused (401)")
                _note(now, f"{role}: OpenRouter refused the key (401); OpenRouter models are skipped for {OR_REFUSED_HOLD // 60} min")
                return None
            unreachable = isinstance(e, requests.ConnectionError)  # refused, no route, no DNS, connect timeout: nothing answered at all (a ReadTimeout is the model being slow)
            short = deadline is not None and isinstance(e, requests.Timeout) and not unreachable and sent_limit < limit - 1  # the cascade's own short limit ended it
            freemodels.record(mid, False, now, status=code, retry_after=ra, role=role, reason="unreachable" if unreachable else "deadline" if short else None,
                              seconds=(time.monotonic() - t0) if isinstance(e, requests.Timeout) and not unreachable else None)
            if why is not None:
                why.update(kind=_fail_kind(e, code, said), status=code, reset_s=_reset_after(e) if code == 429 else None)
            _note(now, f"{role}: free model {mid}: {type(e).__name__}{f' {code}' if code else ''}")
            _attempt(mid, f"{_fail_kind(e, code, said)}{f' ({code})' if code else ''}")
            return None
        took = time.monotonic() - t0
        u = body.get("usage") or {}
        record(now, role, mid, int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0)), 0.0)
        try:
            out = parse_json(body["choices"][0]["message"]["content"])
        except (ValueError, KeyError, IndexError, TypeError):
            try:
                fin = str(body["choices"][0].get("finish_reason") or "") or None
            except (KeyError, IndexError, TypeError, AttributeError):
                fin = None
            freemodels.record(mid, False, now, role=role, seconds=took, reason="json", finish=fin)
            if fin == "length" and not retried and not once and cap < FREE_MAX_TOKENS:
                retried = True
                cap = min(FREE_MAX_TOKENS, cap * 2)
                if via_or:  # the thinking ran on: a judge keeps a small budget, a writer or a small job answers without thinking
                    reasoning = {"max_tokens": 1024} if role == "review" else {"enabled": False}
                _note(now, f"{role}: free model {mid} was cut off by the output limit; asked again with {cap} tokens" + (f" and thinking {'capped at 1024' if role == 'review' else 'off'}" if via_or else ""))
                continue
            if why is not None:
                why.update(kind="json", status=None, finish=fin)
            _attempt(mid, "no JSON")
            _note(now, f"{role}: free model {mid} did not return JSON" + (" (cut off by the output limit)" if fin == "length" else f" (finish: {fin})" if fin else ""))
            return None
        freemodels.record(mid, True, now, role=role, seconds=took)
        _attempt(mid, "answered")
        if body.get("model"):  # what really answered: the owner's "auto" and OpenRouter's own router (openrouter/free) pick a different model each time (21 Nov 2026)
            _served[mid] = str(body["model"])[:80]
        return out  # who answered is recorded by the caller: a raced loser must not claim the role
    return None


_RACING: list = []  # race requests still running after their winner was used (see settle)


def settle(timeout: float = 30.0) -> int:
    """Wait up to `timeout` seconds for race requests that lost but are still answering, and return how many were still running at the end.
    A loser records its outcome in data/free_models.json when it finishes; anything that redirects that file for a while (the daily agent
    evaluation, tests) calls this before putting the real path back, or the late answer lands in the real file (20 Nov 2026: invented test
    models a/m1:free, b/m2:free, b/slow:free replaced the learned history of the real free models)."""
    from concurrent.futures import wait

    live = [f for f in _RACING if not f.done()]
    if live:
        wait(live, timeout=timeout)
    _RACING[:] = [f for f in _RACING if not f.done()]
    return len(_RACING)


def _race(models: list[str], prompt: str, role: str, cfg: dict, key: str, now: dt.datetime) -> dict | None:
    """The top two free models asked at once: the first answer that parses is used and the other is ignored. The loser's request is not cancelled
    (an HTTP call cannot be recalled), so both count against the daily allowance; the race costs at most one extra request."""
    top = list(models)[:2]
    if not top:
        return None
    if len(top) == 1:
        return _ask_free(top[0], prompt, role, cfg, key, now)
    pool = ThreadPoolExecutor(max_workers=2)
    try:
        futures = {pool.submit(_ask_free, m, prompt, role, cfg, key, now): m for m in top}
        for f in as_completed(futures):
            err = f.exception()
            if isinstance(err, _NoAllowance):
                raise err
            if err is not None:
                continue
            got = f.result()
            if got is not None:
                _answered(role, futures[f])  # only the winning model is the one that answered this role
                return got
        return None
    finally:
        _RACING.extend(f for f in futures if not f.done())  # settle() can wait for them
        pool.shutdown(wait=False)  # the loser may still be answering: the call does not wait for it


def _served_a_writer(mid, skip_ids: set) -> str:
    """The writer a router served this judge's request with, or "": a judge asked by a router's name (openrouter/free, the owner's auto) may have been
    answered by the very model that wrote the script, and that answer is not an independent judgement (21 Nov 2026 audit: openrouter/free answered 73
    reviews on 20 Nov while the router could pick any free model, the writer included)."""
    served = _served.get(mid or "")
    return served if served and model_identity(served) != model_identity(mid) and model_identity(served) in skip_ids else ""


def _free_chat(prompt: str, role: str, cfg: dict, key: str, now: dt.datetime, avoid=None, avoid_families=frozenset()) -> dict | None:
    """Try the free models in turn, waiting and trying again when they are all busy. None means: nothing answered. `avoid` (a model or a set of them) is never asked.
    `avoid_families`: makers (model_family) whose models are never asked, and no router either (its family is unknown until it answers): the second judge of a
    free review (24 Nov 2026: two NVIDIA Nemotron models fact-checked one script and counted as two independent judges).
    A script or a review starts with the two best models raced (Task 2 of the 17 Nov plan); the rest of the round then walks the remaining ones in order."""
    freemodels.refresh(now)
    refused: set = set()  # judges whose router served a writer in this call: not asked again by it
    for rnd in range(ROUNDS):
        skip = (set(avoid) if isinstance(avoid, (set, frozenset, list, tuple)) else ({avoid} if avoid else set())) | ({_last_free["script"]} if role == "review" and _last_free.get("script") else set())
        skip |= refused
        if role == "review":
            skip |= _WRITERS  # every model that wrote this script in this process, including what "auto" was served as
        skip_ids = {model_identity(m) for m in skip}  # the same model under another provider's name is the same judge
        # the owner's own provider is asked first (it needs none of OpenRouter's allowance), except models it says it cannot serve now
        extras = [m for m in extra_models(role) if model_identity(m) not in skip_ids and freemodels.available(m, now) and extra_status(m) not in UNUSABLE]
        if role == "review":  # then the cascade's own judges on the same provider (GLM, Qwen): a second family for the script fact-check
            listed = {model_identity(m) for m in extras}
            extras += [m for m in judge_extra_models() if model_identity(m) not in skip_ids | listed and freemodels.available(m, now) and extra_status(m) not in UNUSABLE]
        # Google directly, for judging only, when the owner saved a Gemini key (22 Nov 2026: the script fact-check never reached the judge cascade's Gemini
        # models, so a saved key changed nothing while every OpenRouter and FreeLLMAPI judge was failing). Same rules: never a writer, two must answer.
        gem = [m for m in gemini_models() if role == "review" and model_identity(m) not in skip_ids and freemodels.available(m, now)] if gemini_key() else []
        routed = [] if openrouter_refused(now, key) else [m for m in freemodels.choose(role, now, avoid=skip, n=4) if model_identity(m) not in skip_ids]
        sharing = set(picture_sharing_models())  # judges on the picture account (GLM, Qwen on Cloudflare) are asked last, never once it is spent
        if sharing:
            import freeart

            spent = freeart.account_exhausted(now)
            extras = [m for m in extras if m not in sharing] + ([] if spent else [m for m in extras if m in sharing])
        models = gem + [m for m in extras if m not in sharing] + routed + [m for m in extras if m in sharing]
        if avoid_families:
            models = [m for m in models if not is_router(m) and not (model_family(m) & avoid_families)]
        if role == "script" and _WRITERS:  # a model that already wrote this script writes the next part first: a film written by six rotating free models left no
            mine = {model_identity(w) for w in _WRITERS}  # model free to judge it (20 Nov 2026, "no free judge could answer" after two hours of writing)
            models = sorted(models, key=lambda m: model_identity(m) not in mine)  # stable: the usual order otherwise
        if not models:
            wait = freemodels.soonest_free(_waitable(role, avoid_families), now)  # everyone is only busy (429): wait for the first to come back instead of giving up
            if wait is not None and wait <= FREE_WAIT_LIMIT and rnd < ROUNDS - 1:
                time.sleep(wait + 1)
                now = now + dt.timedelta(seconds=wait + 1)
                continue
            break
        rest = models
        sticky = role == "script" and bool(_WRITERS) and len(models) >= 2 and model_identity(models[0]) in {model_identity(w) for w in _WRITERS} \
            and model_identity(models[1]) not in {model_identity(w) for w in _WRITERS}  # the script's own writer is asked alone first: a raced newcomer would join the writers
        if role in RACE_ROLES and len(models) >= 2 and not sticky:
            try:
                raced = _race(models[:2], prompt, role, cfg, key, now)
            except _NoAllowance:
                return None
            if raced is not None:
                won = _last_free.get(role)
                writer = _served_a_writer(won, skip_ids) if role == "review" else ""
                if not writer:
                    return raced
                refused.add(won)
                _last_free.pop(role, None)
                _note(now, f"review: {won} was answered by {writer}, a writer of this script; that judgement is not used")
            rest = models[2:]
        or_failed = False
        for mid in rest:
            if or_failed and not mid.startswith((EXTRA_PREFIX, GEMINI_PREFIX)):
                continue  # after an OpenRouter failure no more OpenRouter models this round, but the owner's own models after them are still asked
            try:
                got = _ask_free(mid, prompt, role, cfg, key, now)
            except _NoAllowance:
                return None
            if got is not None:
                writer = _served_a_writer(mid, skip_ids) if role == "review" else ""
                if writer:
                    refused.add(mid)
                    _note(now, f"review: {mid} was answered by {writer}, a writer of this script; that judgement is not used")
                    continue
                _answered(role, mid)
                return got
            if mid.startswith((EXTRA_PREFIX, GEMINI_PREFIX)):  # Google directly is a separate free tier too (22 Nov 2026: gemini-2.5-flash answered 404)
                continue  # one of the owner's models failed (app not running, its free tier used up, a bad reply): the next model is asked now. Its models are
                # separate free tiers; ending the round here let three failing own models use all three rounds and no OpenRouter model was asked (21 Nov 2026)
            or_failed = True  # an OpenRouter failure (network, or a reply that is not JSON) ends OpenRouter's part of this round: wait, then ask again
            # (24 Nov 2026: a `break` here also ended the round for the judges routed after OpenRouter, so "asked last" meant "never asked")
        if rnd < ROUNDS - 1:
            pause = 20 * (rnd + 1)  # everyone was busy: wait, then ask again (only as long as the first model needs, when it said so)
            soon = freemodels.soonest_free(_waitable(role, avoid_families), now)
            if soon is not None and soon + 1 < pause:
                pause = soon + 1
            time.sleep(pause)
            now = now + dt.timedelta(seconds=pause)
    return None


LAST_REVIEW: dict = {}  # how the newest review call was answered: {"mode": "paid"} or {"mode": "free", "models": [...]}; read by reviewer.llm_review for its note


def _leaf(v, other):
    """A value next to a number or a flag may come back as text ("7", "true"): read it as the number or flag. Text that is neither raises ValueError."""
    if isinstance(v, str) and isinstance(other, (bool, int, float)):
        t = v.strip().lower()
        if t in ("true", "false"):
            return t == "true"
        try:
            return float(t) if "." in t else int(t)
        except ValueError:
            raise ValueError(f"cannot read {v!r} as a number or a flag") from None
    return v


def strictest(a, b):
    """Two judges' answers merged so that the worse one counts: the larger number, true over false, every item either one listed, the first text that is not empty.
    ONLY for the judge prompts that ask for a risk score, a "misleading" flag or a list of unsupported lines (scriptgen._review_chat): for them larger, true and
    more items always mean a worse video. Numbers and flags that arrive as text are read as numbers and flags; two answers that cannot be reconciled raise ValueError."""
    empty = (None, "", [], {})
    if a in empty and not isinstance(a, bool):
        return b
    if b in empty and not isinstance(b, bool):
        return a
    if isinstance(a, dict) or isinstance(b, dict):
        if not (isinstance(a, dict) and isinstance(b, dict)):
            raise ValueError("one answer is an object and the other is not")
        return {k: (strictest(a[k], b[k]) if k in a and k in b else a[k] if k in a else b[k]) for k in list(a) + [k for k in b if k not in a]}
    if isinstance(a, list) or isinstance(b, list):
        if not (isinstance(a, list) and isinstance(b, list)):
            raise ValueError("one answer is a list and the other is not")
        seen, out = set(), []
        for item in a + b:
            key = json.dumps(item, sort_keys=True, default=str)
            if key not in seen:
                seen.add(key)
                out.append(item)
        return out
    a, b = _leaf(a, b), _leaf(b, a)
    if isinstance(a, bool) and isinstance(b, bool):
        return a or b
    if isinstance(a, bool) != isinstance(b, bool):
        raise ValueError("a flag and a number cannot be compared")
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return max(a, b)
    if isinstance(a, (int, float)) != isinstance(b, (int, float)):
        raise ValueError("a number and a text cannot be compared")
    return a


def _free_review(prompt: str, cfg: dict, key: str, now: dt.datetime, avoid=None) -> dict | None:
    """A review by two different free models (never the writer): None unless both gave a usable answer, so one model's word never passes a video.
    `avoid` holds the writers recorded with the video (`script_writers`), for a review that runs in another process than the writing did."""
    base = set(avoid or ())
    first = _free_chat(prompt, "review", cfg, key, now, **({"avoid": base} if base else {}))
    if not isinstance(first, dict) or not first:
        return None
    one = _last_free.get("review")
    fam_one = answer_family(one)
    if not fam_one:  # a router that did not say who answered: no second judge can be shown to be independent of it
        _blocked_review(now, [one], f"the first judge {one} did not say which model answered, so no second judge can be shown to be of another family")
        return None
    second = _free_chat(prompt, "review", cfg, key, now, avoid=(base | ({one} if one else set())) or None, avoid_families=fam_one)
    if not isinstance(second, dict) or not second:
        _blocked_review(now, [one], f"no judge of a family other than {'/'.join(sorted(fam_one))} answered")
        return None
    two = _last_free.get("review")
    fam_two = answer_family(two)
    if not fam_two or fam_one & fam_two:  # the provider served the second request with a model of the first judge's family: one family, one opinion
        _blocked_review(now, [one, two], f"both judges are of the {'/'.join(sorted(fam_one & (fam_two or fam_one)))} family; one family is one opinion")
        return None
    LAST_REVIEW.clear()
    LAST_REVIEW.update({"mode": "free", "models": [one, two], "served": [_served.get(one, one), _served.get(two, two)],
                        "families": [sorted(fam_one), sorted(fam_two)], "providers": [provider_of(one), provider_of(two)],
                        "answers": [first, second], "at": now.isoformat(timespec="seconds")})  # each judge's own answer is kept: a disagreement stays visible
    try:
        return strictest(first, second)
    except ValueError:  # the two answers disagree in shape: that is no review, never a pass
        LAST_REVIEW.clear()
        LAST_REVIEW["mode"] = "paid"
        return None


def provider_of(mid) -> str:
    """Which service answered under this id: the owner's own provider (extra:), Google AI Studio (gemini:) or OpenRouter (any other id)."""
    m = str(mid or "")
    return "owner-provider" if m.startswith(EXTRA_PREFIX) else "google-ai-studio" if m.startswith(GEMINI_PREFIX) else "openrouter"


def _waitable(role: str, avoid_families=frozenset()) -> list[str]:
    """The models worth waiting for when every candidate is busy: none of an excluded family (a second judge never waits for the first judge's family)."""
    ids = extra_models(role) + (judge_extra_models() if role == "review" else []) + freemodels.roster_ids()
    return [m for m in ids if not (avoid_families and (is_router(m) or model_family(m) & avoid_families))]


def _blocked_review(now: dt.datetime, models: list, why: str) -> None:
    """A free review that could not get two judges of different families: BLOCKED (never a pass, never one family counted twice); the reason is kept."""
    LAST_REVIEW.clear()
    LAST_REVIEW.update({"mode": "blocked", "models": [m for m in models if m], "why": why, "at": now.isoformat(timespec="seconds")})
    _note(now, f"review: blocked: {why}")


def paid_allowed(cfg: dict | None = None) -> bool:
    """May a paid model be called at all? Only while paid models are switched on (llm.json `enabled`, the Settings switch). Free Mode refuses every paid
    call whatever the daily cap says. 20 Nov 2026: the thumbnail score, the narration listen before an approval and the video analysis checked only the
    cap, so in Free Mode they still sent requests to paid models (refused by OpenRouter only because the credit was below zero)."""
    cfg = cfg or load_config()
    return bool(cfg.get("enabled"))


def free_only() -> bool:
    """Paid models and paid pictures are off and free models do every job, reviews included: nothing is spent, so the credit floors do not apply."""
    cfg = load_config()
    return bool(not cfg["enabled"] and cfg["free"] and cfg.get("free_review") and not cfg.get("ai_art"))


def chat(prompt: str, role: str = "cheap", fallback=None, now: dt.datetime | None = None, strict: bool = False, avoid=None) -> dict:
    """JSON from the model assigned to this role, or from the local fallback when that is not possible.
    `strict` marks a judge prompt (risk scores, misleading flags, unsupported lines) that two free models may answer when `free_review` is on; other review-role prompts never go to free models.
    `avoid`: models that must not answer (a review passes the video's recorded writers)."""
    import playbook

    stable, mark, rest = prompt.partition(CACHE_MARK)
    # the acting agent's role and limits ride along with every call it makes: after the cached part, so the cache is the same for every agent
    prompt = stable + mark + playbook.inject(rest) if mark else playbook.inject(prompt)
    plain = prompt.replace(CACHE_MARK, "")
    now = now or _now()
    cfg, key = load_config(), api_key()
    model = cfg["models"].get(role, "")
    capped = False
    if role == "review":
        LAST_REVIEW.clear()
        LAST_REVIEW["mode"] = "paid"
    if model and is_claude(model):
        key = anthropic_key()
    if cfg["enabled"] and key and model:
        if spent_today(now) >= cfg["daily_budget_usd"] + (REVIEW_RESERVE_USD if role == "review" else 0.0):
            _note(now, f"{role}: the daily cap was reached, so this job waits for free models or tomorrow")
            capped = True
        else:
            for _ in range(2):
                try:
                    body = _post(_payload(model, prompt, cfg["max_output_tokens"], role=role), key)
                except Exception as e:  # network, HTTP, auth: never stop the pipeline
                    _note(now, f"{role}: {type(e).__name__}: {e}")
                    break
                _account(now, role, model, body)
                try:
                    out = parse_json(body["choices"][0]["message"]["content"])
                except (ValueError, KeyError, IndexError, TypeError):
                    continue
                if role == "script":
                    _WRITERS.add(model)
                return out
            else:
                _note(now, f"{role}: invalid JSON from {model}, used the local model")
    cascade = None
    if role == "review" and strict and cfg["free"] and cfg.get("free_review"):
        import judges  # the judge cascade (22 Nov 2026): only for the AI review of a video, which reviewer.llm_review marks with judges.for_video

        cascade = judges.current() if judges.active(cfg) else None
    if cascade is not None:
        got = judges.review(plain, cascade, cfg, api_key(), now, avoid=avoid)  # two judges of different families, never a writer; None when two did not answer
        if got is not None:
            return got
    elif cfg["free"] and api_key() and (role != "review" or (strict and cfg.get("free_review"))):  # free models judge a video only when the owner switched free_review on (13 Nov 2026) and the caller is a judge prompt: then two of them must answer
        key = api_key()
        more = {"avoid": {avoid} if isinstance(avoid, str) else set(avoid)} if avoid else {}  # passed only when there is something to avoid
        got = _free_review(plain, cfg, key, now, **more) if role == "review" else _free_chat(plain, role, cfg, key, now, **more)
        if got is not None:
            return got
    if role == "review" and strict and LAST_REVIEW.get("mode") == "blocked":
        raise ModelUnavailable(f"the review is blocked: {LAST_REVIEW.get('why')}; it will be tried again later")
    if fallback is None or not cfg.get("local_fallback") or (role == "review" and strict):  # a judge prompt never falls back to one local model: one opinion is no review
        if capped:
            raise ModelUnavailable(f"the daily spending cap (${cfg['daily_budget_usd']:.2f}) is used up and the free models did not answer the {role} job; raise the cap in Settings or wait for tomorrow (UTC)")
        raise ModelUnavailable(f"no cloud model answered the {role} job; it will be tried again later")
    return fallback(plain)


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
