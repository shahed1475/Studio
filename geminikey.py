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
KEY = re.compile(r"^AIza[A-Za-z0-9_-]{30,40}$")  # Google API keys start with AIza (39 characters in all)


def check_format(value: str) -> str:
    """The key, trimmed, or ValueError with a plain reason. The value itself is never put in the message."""
    v = str(value or "").strip()
    if not KEY.match(v):
        raise ValueError("that is not a Google AI Studio key: it should start with AIza (aistudio.google.com/apikey)")
    return v


def scrub(text, key: str) -> str:
    t = str(text)
    return t.replace(key, "***") if key else t


def test(key: str, get=requests.get) -> dict:
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
            n = len(r.json().get("models") or [])
        except (ValueError, AttributeError):
            n = None
        return {"ok": True, "seconds": secs, "detail": f"Google accepted the key ({secs} s)" + (f": it lists {n} models, nothing was changed." if n is not None else ".")}
    if code in (400, 401, 403):
        return {"ok": False, "seconds": secs, "detail": "Google refused the key (wrong, deleted, or the Gemini API is not enabled for its project). Make one at aistudio.google.com/apikey."}
    if code == 429:
        return {"ok": False, "seconds": secs, "detail": "Google is limiting requests for this key right now (HTTP 429). The free quota resets daily."}
    return {"ok": False, "seconds": secs, "detail": f"Google answered HTTP {code}; the key was not confirmed."}
