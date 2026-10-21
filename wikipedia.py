"""Source text for scripts: the Wikipedia article for a topic, so narration is built from documented facts."""
import os
import re
import threading
import time

import requests

API = "https://en.wikipedia.org/w/api.php"
# Wikimedia asks every bot to say who runs it (API etiquette): a name, a version and a place to reach the operator
UA = {"User-Agent": f"SleepingLibraryBot/1.0 ({os.getenv('WIKI_CONTACT', 'https://github.com/shahed1475/Studio')}; educational storytelling channel)"}
MIN_GAP = 1.0  # seconds between requests from this process: on 21 Oct 2026 about ten requests in ten seconds brought HTTP 429 for half a minute, and every studio on the server shares one address
MAX_WAIT = 60  # the longest pause obeyed after a 429, whatever Retry-After says
TRIES = 4
_last_call = [0.0]
_gate = threading.Lock()
_GENERIC = {"the", "of", "a", "an", "and", "in", "on", "mystery", "mysteries", "real", "true", "story", "legend", "secret",
            "secrets", "unsolved", "was", "is", "or", "did", "why", "what", "how", "behind", "truth"}


def _api(params: dict) -> dict:
    """One API call, spaced from the last one, and patient with HTTP 429: it waits the time Retry-After names (at most MAX_WAIT) and asks again, a few times."""
    for attempt in range(TRIES):
        with _gate:
            wait = _last_call[0] + MIN_GAP - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            _last_call[0] = time.monotonic()
        r = requests.get(API, params={**params, "format": "json"}, headers=UA, timeout=30)
        if r.status_code == 429 and attempt < TRIES - 1:
            try:
                pause = float(r.headers.get("Retry-After", 10))
            except (TypeError, ValueError):
                pause = 10.0
            time.sleep(min(max(pause, 1.0), MAX_WAIT))
            continue
        r.raise_for_status()
        return r.json()


def _terms(topic: str) -> str:
    words = [w for w in re.findall(r"[\w']+", topic) if w.lower() not in _GENERIC]
    return " ".join(words) or topic


def facts_for(topic: str, chars: int = 7000) -> tuple[str, str] | None:
    """(article title, plain text trimmed to `chars`) for the best match, or None."""
    try:
        hits = _api({"action": "query", "list": "search", "srsearch": _terms(topic), "srlimit": 1}).get("query", {}).get("search", [])
        if not hits:
            return None
        page = next(iter(_api({"action": "query", "prop": "extracts", "explaintext": 1, "redirects": 1,
                               "titles": hits[0]["title"]}).get("query", {}).get("pages", {}).values()), {})
    except requests.RequestException:
        return None
    text = re.sub(r"\n{3,}", "\n\n", page.get("extract", "")).strip()
    return (page.get("title", hits[0]["title"]), text[:chars]) if len(text) > 400 or text else None


def article_text(title: str, chars: int = 80000) -> str:
    """The plain text of one article (for checking a script's names and years against its own source). Empty when it cannot be read."""
    try:
        page = next(iter(_api({"action": "query", "prop": "extracts", "explaintext": 1, "redirects": 1, "titles": title}).get("query", {}).get("pages", {}).values()), {})
    except requests.RequestException:
        return ""
    return re.sub(r"\n{3,}", "\n\n", page.get("extract", "")).strip()[:chars]


def article_info(title: str, chars: int = 20000) -> dict | None:
    """One article with its address, text and the date of its latest revision: {title, url, text, revised}. None when it cannot be read."""
    try:
        data = _api({"action": "query", "prop": "extracts|revisions", "explaintext": 1, "redirects": 1, "rvprop": "timestamp", "titles": title})
    except requests.RequestException:
        return None
    page = next(iter(data.get("query", {}).get("pages", {}).values()), {})
    text = re.sub(r"\n{3,}", "\n\n", page.get("extract", "")).strip()
    if not text:
        return None
    name = page.get("title", title)
    rev = (page.get("revisions") or [{}])[0].get("timestamp", "")
    return {"title": name, "url": "https://en.wikipedia.org/wiki/" + name.replace(" ", "_"), "text": text[:chars], "revised": rev}


def facts_multi(topic: str, n: int = 2, chars_each: int = 7000) -> list[dict]:
    """The best n matching articles (the main one first), each as {title, url, text, revised}, so a script can draw on more than one source."""
    try:
        hits = _api({"action": "query", "list": "search", "srsearch": _terms(topic), "srlimit": max(n, 1) + 2}).get("query", {}).get("search", [])
    except requests.RequestException:
        return []
    out, seen = [], set()
    for h in hits:
        if len(out) >= n:
            break
        info = article_info(h["title"], chars_each)
        if info and info["title"] not in seen and len(info["text"]) > 400:
            seen.add(info["title"])
            out.append(info)
    return out
