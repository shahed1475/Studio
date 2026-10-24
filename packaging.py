"""Packaging rules as code: score a title, rank the options, and audit a finished video's title, description and thumbnail text.

Everything here is deterministic and offline. The audit rows are warnings, never blocks: packaging advice must not fail a video that is otherwise fine.
Rules come from the packaging skills (.claude/skills/studio-packaging, yt-title-optimizer, yt-description-writer, yt-thumbnail-brief)."""
import difflib
import re

SEARCH_WORDS = {"real", "story", "legend", "mystery", "mysteries", "myth", "myths", "history", "truth", "origin", "origins", "who", "what", "why",
                "happened", "unsolved", "lost", "secret", "secrets", "true", "ancient", "haunting", "curse", "disappearance", "vanished"}
VAGUE_START = re.compile(r"^(what|how|why|did|does|do|is|are)\b.*\b(actually|really)\b.*\?$", re.I)
TITLE_BEST = (40, 62)  # characters: long enough to say something, short enough not to be cut on a phone
FRONT = 40  # the words that decide the click sit inside the first 40 characters


def _words(s: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", (s or "").lower())


def _key_words(core: str) -> list[str]:
    return [w for w in _words(core) if len(w) > 3]


def title_score(title: str, core: str = "", others=()) -> float:
    """Higher is better. Rewards: the search phrase inside the first 40 characters, a length of 40 to 62, words people type, a proper name.
    Penalises: a vague 'what do ... actually ...?' question, shouting, being near-identical to another title."""
    t = (title or "").strip()
    if not t:
        return -99.0
    score = 0.0
    low = t.lower()
    key = _key_words(core)
    if key:
        front = low[:FRONT]
        share = sum(w in front for w in key) / len(key)
        score += 3.0 * share  # the main phrase up front
        score += 1.0 * (sum(w in low for w in key) / len(key))  # and somewhere at all
    n = len(t)
    score += 1.5 if TITLE_BEST[0] <= n <= TITLE_BEST[1] else (0.5 if n <= 70 else -2.0)
    score += 0.4 * min(len(SEARCH_WORDS & set(_words(t))), 3)
    if re.search(r"\b[A-Z][a-z]+\b", t[1:]):
        score += 0.5  # a named subject, not a label
    if VAGUE_START.match(t):
        score -= 2.5
    letters = [c for c in t if c.isalpha()]
    if len(letters) > 10 and sum(c.isupper() for c in letters) / len(letters) > 0.6:
        score -= 3.0
    if any(difflib.SequenceMatcher(None, low, o.lower()).ratio() >= 0.85 for o in others):
        score -= 4.0
    return round(score, 2)


def rank_titles(titles: list[str], core: str = "", others=()) -> list[str]:
    """The same titles, best first (ties keep the writer's order)."""
    return [t for _, _, t in sorted(((-title_score(t, core, others), i, t) for i, t in enumerate(titles)))]


def _row(name: str, ok: bool, detail: str) -> dict:
    return {"name": name, "ok": ok, "detail": detail, "severity": "warn"}


def audit(meta: dict) -> list[dict]:
    """Warning rows for a finished documentary or Short: is the main phrase up front, does the description's first 150 characters carry it, and does the
    thumbnail text add to the title instead of repeating it."""
    out = []
    title = meta.get("title", "")
    core = (meta.get("seo") or {}).get("core", "")
    key = _key_words(core)
    if key:
        front = title.lower()[:FRONT]
        ok = all(w in front for w in key)
        out.append(_row("seo_title_front", ok, "the search phrase is in the first 40 characters of the title" if ok
                        else f"the search phrase '{core}' is not in the first 40 characters of the title (it may be cut off on a phone)"))
        first = (meta.get("description", "") or "")[:150].lower()
        ok = all(w in first for w in key)
        out.append(_row("seo_description_150", ok, "the first 150 characters of the description carry the search phrase" if ok
                        else f"the first 150 characters of the description do not carry '{core}' (they are all that shows before 'Show more')"))
    hook = meta.get("thumb_hook", "")
    if hook:
        hw, tw = set(_words(hook)), set(_words(title))
        shared = len(hw & tw) / max(len(hw), 1)
        ok = shared < 1.0 and len(hook.split()) <= 5
        out.append(_row("seo_thumbnail_text", ok, "the thumbnail text adds something the title does not" if ok
                        else "the thumbnail text only repeats the title's words or is too long; it should name the subject and add a new word"))
    if len(title) > 70:
        out.append(_row("seo_title_length", False, f"{len(title)} characters: YouTube cuts titles over about 70 on a phone"))
    return out
