"""One small skill card per kind of video (legend, mystery, event, person, place), chosen from the topic's own words with fixed rules.

No model call picks the kind and no tokens are spent on it. A prompt gets only the card line for its job (`brief(meta, "seo")`, "thumb" or "hook"), a few dozen
tokens instead of a long general rule. The cards are in `config/kinds.json` (shipped, read only here); a missing or bad file means the plain default card.
Cards advise packaging. They hold no fact and no honesty rule: the title still has to keep its promise (the reviewer checks that)."""
import json
import re
from functools import lru_cache

import config

FILE = config.ROOT / "config" / "kinds.json"
PARTS = ("seo", "thumb", "hook")
MAX_CARD = 300  # characters per card line: prompts cost money
MIN_SCORE = 3  # one stray word in a chapter title is not a kind; the topic itself or two other places must say it
WEIGHTS = (("topic", 3), ("title", 2), ("anchors", 2), ("chapters", 1), ("opening", 1))
FALLBACK = {"seo": "The best-known name first, then one concrete twist the video really shows.", "thumb": "Two to four words that name the subject and add one new detail.",
            "hook": "Open on the strangest true fact or the central question."}


@lru_cache(maxsize=1)
def _load() -> dict:
    try:
        raw = json.loads(FILE.read_text())
        kinds = {k: v for k, v in raw["kinds"].items() if isinstance(v, dict) and isinstance(v.get("words"), list)}
        return {"order": [k for k in raw.get("order", []) if k in kinds] or list(kinds), "kinds": kinds, "default": raw.get("default") or FALLBACK,
                "title_words": raw.get("title_words") or {}}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {"order": [], "kinds": {}, "default": FALLBACK, "title_words": {}}


def names() -> list[str]:
    return list(_load()["order"])


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z]+", str(text or "").lower())


def _hits(tokens: list[str], text: str, words: list[str]) -> int:
    have = set(tokens)
    n = sum(1 for w in words if " " not in w and (w in have or w + "s" in have or w + "es" in have))
    return n + sum(1 for w in words if " " in w and w in text.lower())  # a phrase such as "who was"


def fields(meta: dict) -> dict[str, str]:
    lines = meta.get("lines") or []
    return {"topic": meta.get("topic", ""), "title": meta.get("title", ""), "anchors": " ".join(map(str, meta.get("anchors") or [])),
            "chapters": " ".join(str(c.get("title", "")) for c in meta.get("chapters") or [] if isinstance(c, dict)),
            "opening": " ".join(str(l.get("text", "")) for l in lines[:3] if isinstance(l, dict))}


def classify(meta: dict) -> str:
    """The kind of video, or "story" (the default card). Never raises. Ties go to the kind listed first in the file."""
    try:
        cfg = _load()
        parts = fields(meta)
        score = {k: 0 for k in cfg["order"]}
        for field, weight in WEIGHTS:
            text = parts.get(field, "")
            toks = _tokens(text)
            for k in score:
                score[k] += weight * min(_hits(toks, text, cfg["kinds"][k]["words"]), 2)  # two matching words in one field are as good as ten
        best = max(cfg["order"], key=lambda k: score[k], default=None)
        return best if best and score[best] >= MIN_SCORE else "story"
    except Exception:
        return "story"


def card(kind: str, part: str) -> str:
    """The card line for one job ("seo", "thumb" or "hook"), cut to MAX_CARD. The default card for an unknown kind or part."""
    cfg = _load()
    text = (cfg["kinds"].get(kind) or cfg["default"]).get(part) or FALLBACK.get(part, "")
    return " ".join(str(text).split())[:MAX_CARD]


def brief(meta: dict, part: str) -> str:
    """A prompt line: the card for this video's kind and job. Empty when there is nothing to say."""
    kind = meta.get("kind") or classify(meta)
    text = card(kind, part)
    return f"Kind of video ({kind}): {text}" if text else ""


def title_words(kind: str) -> set[str]:
    return {str(w).lower() for w in (_load()["title_words"].get(kind) or [])}


def problems() -> list[str]:
    """Anything wrong with the shipped cards (used by the test and the agent evaluation)."""
    cfg, out = _load(), []
    if not cfg["kinds"]:
        return ["config/kinds.json is missing or unreadable"]
    for k, v in cfg["kinds"].items():
        out += [f"{k}: {p} card is missing" for p in PARTS if not v.get(p)]
        out += [f"{k}: {p} card is over {MAX_CARD} characters" for p in PARTS if len(str(v.get(p, ""))) > MAX_CARD]
        if len(v["words"]) < 8:
            out.append(f"{k}: too few words to recognise it")
    out += [f"default: {p} card is missing" for p in PARTS if not cfg["default"].get(p)]
    return out
