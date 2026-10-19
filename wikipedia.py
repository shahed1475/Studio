"""Source text for scripts: the Wikipedia article for a topic, so narration is built from documented facts."""
import re

import requests

API = "https://en.wikipedia.org/w/api.php"
UA = {"User-Agent": "SleepingLibraryBot/1.0 (educational storytelling channel)"}
_GENERIC = {"the", "of", "a", "an", "and", "in", "on", "mystery", "mysteries", "real", "true", "story", "legend", "secret",
            "secrets", "unsolved", "was", "is", "or", "did", "why", "what", "how", "behind", "truth"}


def _api(params: dict) -> dict:
    r = requests.get(API, params={**params, "format": "json"}, headers=UA, timeout=30)
    r.raise_for_status()
    return r.json()


def _terms(topic: str) -> str:
    words = [w for w in re.findall(r"[A-Za-z0-9']+", topic) if w.lower() not in _GENERIC]
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
