"""Packaging rules as code: score a title, rank the options, and audit a finished video's title, description and thumbnail text.

Everything here is deterministic and offline. The audit rows are warnings, never blocks: packaging advice must not fail a video that is otherwise fine.
Rules come from the packaging skills (.claude/skills/studio-packaging, yt-title-optimizer, yt-description-writer, yt-thumbnail-brief)."""
import difflib
import re

import kinds
import rulesfile

SEARCH_WORDS = {"real", "story", "legend", "mystery", "mysteries", "myth", "myths", "history", "truth", "origin", "origins", "who", "what", "why",
                "happened", "unsolved", "lost", "secret", "secrets", "true", "ancient", "haunting", "curse", "disappearance", "vanished"}
VAGUE_START = re.compile(r"^(what|how|why|did|does|do|is|are)\b.*\b(actually|really)\b.*\?$", re.I)
TITLE_BEST = rulesfile.rng("benchmarks", "title_chars")  # characters (config/rules.json): long enough to say something, short enough not to be cut on a phone
TITLE_HARD_MAX = rulesfile.get("benchmarks", "title_hard_max")  # longer than this is cut on a phone and scored down
FRONT = 40  # the words that decide the click sit inside the first 40 characters


def _words(s: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", (s or "").lower())


def _key_words(core: str) -> list[str]:
    return [w for w in _words(core) if len(w) > 3]


def title_score(title: str, core: str = "", others=(), kind: str = "") -> float:
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
    score += 1.5 if TITLE_BEST[0] <= n <= TITLE_BEST[1] else (0.5 if n <= TITLE_HARD_MAX else -2.0)
    score += 0.4 * min(len(SEARCH_WORDS & set(_words(t))), 3)
    score += 0.2 * min(len(kinds.title_words(kind) & set(_words(t))), 2)  # the words people type for this kind of video (kinds.py), a small nudge
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


def rank_titles(titles: list[str], core: str = "", others=(), kind: str = "") -> list[str]:
    """The same titles, best first (ties keep the writer's order)."""
    return [t for _, _, t in sorted(((-title_score(t, core, others, kind), i, t) for i, t in enumerate(titles)))]


_STOP = set("the a an and of to in on at for with from by is was were are be been it its this that these those as but or not no yet then there their they he she his her "
            "which who whom what when where while than into onto over under after before about also had has have do did does so such other another one two three first second third".split())


def script_repeats(lines: list[str]) -> list[tuple[int, int]]:
    """Pairs of narration lines (at least two apart) that say nearly the same thing: 6 or more shared content words and 70% of the shorter line's. Exact
    repeats are caught elsewhere; this finds a chapter retelling what the opening already told. Measured: only one of our four documentaries trips it."""
    sig = [{w for w in _words(t) if len(w) > 3 and w not in _STOP} for t in lines]
    out = []
    for i in range(len(sig)):
        for j in range(i + 2, len(sig)):
            shared = len(sig[i] & sig[j])
            if shared >= 6 and shared / max(min(len(sig[i]), len(sig[j])), 1) >= 0.7:
                out.append((i, j))
    return out


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
    pairs = script_repeats([l.get("text", "") for l in meta.get("lines", [])])
    if pairs:
        out.append(_row("script_retells", False, "the script tells the same thing twice: lines " + ", ".join(f"{i + 1} and {j + 1}" for i, j in pairs[:3])
                        + " (a viewer who hears it again may leave)"))
    fp = meta.get("footage") or {}
    if meta.get("format") == "doc" and fp.get("scenes"):
        share = fp.get("unique", 0) / fp["scenes"]
        ok = share >= 0.55
        out.append(_row("picture_variety", ok, f"{fp.get('unique', 0)} different pictures for {fp['scenes']} scenes ({share:.0%})" if ok
                        else f"only {fp.get('unique', 0)} different pictures for {fp['scenes']} scenes ({share:.0%}): the same few pictures repeat, which viewers leave on"))
    if len(title) > 70:
        out.append(_row("seo_title_length", False, f"{len(title)} characters: YouTube cuts titles over about 70 on a phone"))
    return out
