"""The owner's Google AI Studio (Gemini API) key (22 Nov 2026, the owner's request): saved from Settings, kept hidden, tested with one read-only call.

Used by the judge cascade (judges.py slot A, llm._post_gemini) so a script can be fact-checked when OpenRouter's free models are busy. Read by
llm.gemini_key(): GEMINI_API_KEY in .env wins, otherwise settings.json `gemini_api_key`. Google's free-tier limits are per Google Cloud project, so a key from
a NEW project adds capacity; one from the project the owner's FreeLLMAPI proxy already uses does not. On the free tier Google may use what is sent to
improve its products: the studio only ever sends public text (scripts and source articles).
The key goes only in a header to Google's Gemini API (llm.GEMINI_MODELS_URL; every model host lives in llm.py) (never in a URL, a log, an error text or a page), with a timeout and no redirects.
"""
import re
import time

import requests

import llm

FIELD = "gemini_api_key"
TEST_URL = llm.GEMINI_MODELS_URL  # read-only model list
KEY = re.compile(r"^(AIza[A-Za-z0-9_-]{30,40}|AQ\.[A-Za-z0-9._-]{20,250})$")  # AIza... (classic Google API key) or AQ.... (the newer format AI Studio issues, seen 22 Nov 2026)


def check_format(value: str) -> str:
    """The key, trimmed, or ValueError with a plain reason. The value itself is never put in the message."""
    v = str(value or "").strip()
    if not KEY.match(v):
        raise ValueError("that is not a Google AI Studio key: it should start with AQ. or AIza (aistudio.google.com/apikey)")
    return v


def scrub(text, key: str) -> str:
    t = str(text)
    return t.replace(key, "***") if key else t


def test(key: str, get=requests.get, chat=None) -> dict:
    """{"ok", "detail", "seconds"}: one read-only request with the key in a header. Never returns or logs the key."""
    if not key:
        return {"ok": False, "detail": "No Gemini key is saved yet."}
    t0 = time.monotonic()
    try:
        r = get(TEST_URL, headers={"x-goog-api-key": key, "Accept": "application/json"}, timeout=15, allow_redirects=False)
    except requests.RequestException as e:
        return {"ok": False, "detail": scrub(f"Google could not be reached ({type(e).__name__}).", key)}
    secs = round(time.monotonic() - t0, 1)
    code = getattr(r, "status_code", 0)
    if code == 200:
        try:
            listed = [str(m.get("name", "")).split("/")[-1] for m in (r.json().get("models") or [])]
        except (ValueError, AttributeError):
            listed = []
        return _ask(key, listed, secs, chat)
    if code in (400, 401, 403):
        return {"ok": False, "seconds": secs, "detail": "Google refused the key (wrong, deleted, or the Gemini API is not enabled for its project). Make one at aistudio.google.com/apikey."}
    if code == 429:
        return {"ok": False, "seconds": secs, "detail": "Google is limiting requests for this key right now (HTTP 429). The free quota resets daily."}
    return {"ok": False, "seconds": secs, "detail": f"Google answered HTTP {code}; the key was not confirmed."}


def judge_models() -> list[str]:
    """The Gemini models the judge cascade asks directly (config/judges.json, prefix gemini:)."""
    import json

    try:
        cfg = json.loads((llm.config.ROOT / "config" / "judges.json").read_text())
    except (OSError, ValueError):
        return []
    found = []

    def walk(v):
        if isinstance(v, str) and v.startswith(llm.GEMINI_PREFIX):
            found.append(v[len(llm.GEMINI_PREFIX):])
        elif isinstance(v, list):
            for x in v:
                walk(x)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
    walk(cfg)
    return list(dict.fromkeys(found))


def _ask(key: str, listed: list[str], secs: float, chat=None) -> dict:
    """The model list answered; now one tiny question through the judges' own path (Google may list models for a key that its chat endpoint then refuses).
    Each Gemini judge model is tried in turn (listed ones first) until one answers: 22 Nov 2026, gemini-2.5-flash answered 404 for the owner's key while
    gemini-3.5-flash-lite answered."""
    want = judge_models()
    order = [m for m in want if m in listed] + [m for m in want if m not in listed]
    if not order:
        return {"ok": True, "seconds": secs, "detail": f"Google accepted the key ({secs} s); no Gemini judge model is configured to try a question."}
    failed = []
    for model in order[:3]:
        t0 = time.monotonic()
        try:
            answer = (chat or llm.gemini_ping)(key, model)
        except Exception as e:  # the message may hold the key: only its kind and status are kept
            code = getattr(getattr(e, "response", None), "status_code", None)
            failed.append((model, code, type(e).__name__))
            continue
        took = round(time.monotonic() - t0, 1)
        skipped = f" ({', '.join(f'{m}: HTTP {c}' if c else f'{m}: {n}' for m, c, n in failed)} did not answer)" if failed else ""
        return {"ok": True, "seconds": secs, "detail": f"Google accepted the key: the judge model {model} answered a test question in {took} s{skipped}. The fact-checker can use it."}
    codes = {c for _, c, _ in failed}
    hint = " Google lists models for this key but refused every question with it: make a classic AIza key in Google Cloud Console > APIs & Services > Credentials (Generative Language API) and save that instead." if codes & {400, 401, 403} else ""
    return {"ok": False, "seconds": secs, "detail": scrub("Google lists models for this key, but no Gemini judge model answered a test question (" + ", ".join(f"{m}: HTTP {c}" if c else f"{m}: {n}" for m, c, n in failed) + ")." + hint, key)}
