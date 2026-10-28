"""Shorts cut from our own finished documentaries (never from anyone else's video).

A chapter that works on its own is re-told as a vertical Short: a new hook first, the chapter's lines, then a closing line that
points to the full video. Voice, pictures and render are rebuilt from the saved script, so no model call is needed beyond one short hook.
"""
import json
import re

import config
import editprofile
import filelock
import kinds
import scriptgen

MAX_CLIPS = 3  # per documentary
MAX_TRIES = 2  # chapters tried in one run
LO, HI = 25.0, 50.0  # seconds of story; with hook and closing line a Short stays under 59 seconds
WORDS_PER_SEC = 2.3
PAUSE = 0.12
OUTRO = "The full story is on our channel."
CLOSINGS = ["The full story of {s} is on our channel.", "Want the sources? The whole {s} film is on our channel.",
            "There is much more to {s}, and it is all in our full video.", "Watch the complete {s} documentary on our channel.",
            "We tell the rest of the {s} story in our full documentary.", "The long version of {s} is waiting on our channel."]
GENERIC_CLOSINGS = ["More quiet stories from history are on our channel.", "If this was new to you, there is a lot more like it on our channel.",
                    "We tell old stories like {s} every week on this channel.", "That is what the records say about {s}. More on our channel.",
                    "Stay a while: our channel is full of stories like {s}.", "There are many more stories like {s} on our channel."]
CONTRAST = re.compile(r"\b(but|however|yet|until|secret|hidden|never|only|nobody|vanished|disappeared|mystery)\b", re.I)


def _plain(t: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", t.lower()).strip()


def outro_for(topic: str, recent: list[str], doc: bool = True) -> str:
    """A closing line that is not like any recent Short's: the template least like the recent endings (a Short that points to a full film, or a generic one)."""
    import difflib

    subject = " ".join(re.sub(r"^(the )?(legend|mystery|story) of (the )?", "", (topic or "").strip(), flags=re.I).strip(" ?.").split()[:5]) or "this story"
    options = [t.format(s=subject) for t in (CLOSINGS if doc else GENERIC_CLOSINGS)]
    worst = lambda t: max((difflib.SequenceMatcher(None, _plain(t), _plain(r)).ratio() for r in recent), default=0.0)
    return min(options, key=worst)


def recent_endings(exclude: str = "") -> list[str]:
    """Last narration line of the newest Shorts, so a new Short can avoid them."""
    metas = sorted((m for m in config.OUT.glob("*/meta.json") if m.parent.name != exclude), key=lambda m: m.stat().st_mtime, reverse=True)
    out = []
    for m in metas[:40]:
        try:
            d = json.loads(m.read_text())
        except ValueError:
            continue
        if d.get("format", "short") != "doc" and d.get("lines"):
            out.append(d["lines"][-1]["text"])
        if len(out) >= 12:
            break
    return out


def line_seconds(words: list[dict], texts: list[str], pause: float = PAUSE) -> list[float]:
    """Seconds each narration line lasts: from the saved word timings, else estimated from the word count."""
    spans: dict[int, list[float]] = {}
    for w in words:
        s = spans.setdefault(w["i"], [w["s"], w["e"]])
        s[0], s[1] = min(s[0], w["s"]), max(s[1], w["e"])
    return [round(spans[i][1] - spans[i][0] + pause, 2) if i in spans else round(len(t.split()) / WORDS_PER_SEC + pause, 2) for i, t in enumerate(texts)]


def score(lines: list[dict]) -> float:
    text = [l["text"] for l in lines]
    s = min(3, sum(1 for t in text if re.search(r"\d", t))) * 1.5
    s += sum(t.count("?") for t in text)
    s += min(3, sum(1 for t in text if CONTRAST.search(t)))
    s += 1 if text and len(text[0].split()) <= 18 else 0
    return round(s, 2)


def windows(lines: list[dict], chapters: list[dict], secs: list[float], lo: float = LO, hi: float = HI) -> list[dict]:
    """Each chapter, from its first line, as many whole lines as fit under `hi`; kept only if it reaches `lo`."""
    out = []
    starts = [c["start_line"] for c in chapters] or [0]
    for n, start in enumerate(starts):
        stop = starts[n + 1] if n + 1 < len(starts) else len(lines)
        total, end = 0.0, start
        while end < stop and total + secs[end] <= hi:
            total += secs[end]
            end += 1
        if end > start and total >= lo:
            title = chapters[n]["title"] if chapters else ""
            out.append({"start": start, "end": end, "secs": round(total, 1), "lines": lines[start:end], "chapter": title,
                        "score": score(lines[start:end])})
    return out


def pick(ws: list[dict], n: int, used: list[int] | None = None) -> list[dict]:
    fresh = [w for w in ws if w["start"] not in (used or [])]
    return sorted(fresh, key=lambda w: (-w["score"], w["start"]))[:n]


def _trim(text: str, words: int) -> str:
    return " ".join(text.split()[:words])


OVERCLAIM = re.compile(r"\b(?:nobody|no one|no-one)\s+(?:has\s+)?ever\b|\bnever\s+(?:been\s+)?(?:found|seen|solved|explained)\b|\bhas\s+never\b|\bproven\s+(?:fact|true)\b", re.I)  # 28 Oct 2026: "Nobody has ever found them" opened a Short whose source describes disputed finds; the review called it overstated


def hook(meta: dict, w: dict, chat=None) -> dict:
    """A hook line (under 12 words) that raises a question, and a title. A model failure falls back to the story's own words."""
    chat = chat or scriptgen._chat
    story = " ".join(l["text"] for l in w["lines"])[:900]
    try:
        got = chat(f"Documentary: {meta['title']}. This part is called '{w['chapter']}'. Story part:\n{story}\n\n"
                   "Write a first line for a YouTube Short that makes a viewer need the answer (a question or a surprising claim, "
                   "under 12 words, true to the story, no clickbait lies; never say flatly what the story itself calls a legend or a dispute: no 'nobody has ever', "
                   "'never been found', use 'legend says' or 'said to') and a title under 70 characters. " + kinds.brief(meta, "hook") + " "
                   'Return JSON {"hook": "...", "title": "..."}')
        h, t = str(got["hook"]).strip(), str(got["title"]).strip()
        if h and t and not OVERCLAIM.search(h):  # an absolute the model added anyway: the story's own question below is used instead
            return {"hook": _trim(h, 12), "title": t[:70]}
    except Exception:
        pass
    question = next((l["text"] for l in w["lines"] if "?" in l["text"]), "")
    title = (w["chapter"] or meta["title"]).strip()
    return {"hook": _trim(question or f"What really happened: {title}?", 12), "title": title[:70]}


def build_short(meta: dict, w: dict, h: dict, doc_slug: str, outro: str = OUTRO) -> dict:
    first = w["lines"][0].get("visual", "")
    lines = [{"text": h["hook"], "visual": first}, *[{"text": l["text"], "visual": l.get("visual", "")} for l in w["lines"]],
             {"text": outro, "visual": first}]
    desc = f"{meta.get('description', '').split(chr(10) + chr(10) + 'Chapters:')[0].strip()}"
    if meta.get("video_id"):
        desc += f"\n\nFull video: https://youtu.be/{meta['video_id']}"
    return {"topic": meta["topic"], "format": "short", "grounded": bool(meta.get("grounded")), "anchors": meta.get("anchors", []),
            "title": h["title"], "description": desc, "tags": meta.get("tags", []), "lines": lines, "sources": meta.get("sources", []),
            "source_doc": doc_slug, "clip_start_line": w["start"]}


def _record(path, key: str, start: int) -> dict:
    """Add a chapter to the documentary's clip list without overwriting anything the owner changed while the Short was rendering."""
    with filelock.locked(path):
        cur = json.loads(path.read_text())
        cur[key] = [*cur.get(key, []), start]
        filelock.write_atomic(path, json.dumps(cur, indent=2))
        return cur


MODERN_MEDIA = re.compile(r"\b(films?|movies?|box office|grossed|sequels?|franchise|netflix|hollywood|starring|trailer|streaming|critics?|reviews? scores?)\b", re.I)


def _docs() -> list:
    out = []
    for m in sorted(config.OUT.glob("*/meta.json")):
        try:
            d = json.loads(m.read_text())
        except ValueError:
            continue
        ok = (d.get("review") or {}).get("verdict") == "pass" or (d.get("approved") and d.get("approved_by") == "you")
        scheduled = bool(d.get("publish_at") or d.get("video_id"))  # the Short says "the full story is on our channel": only once that film is on its way
        if d.get("format") == "doc" and d.get("lines") and d.get("chapters") and ok and scheduled and len(d.get("clips", [])) + len(d.get("clips_failed", [])) < MAX_CLIPS:
            out.append((m, d))
    return out


def clippable() -> int:
    return len(_docs())


def make_next(produce=None, chat=None):
    """Make one Short from the first documentary that still has an unused good chapter. Returns the Short's folder, or None."""
    if produce is None:
        import run

        produce = run._produce_short
    import duplicates

    try:
        rows = duplicates.catalogue()
    except Exception:
        rows = []
    for m, d in _docs():
        if duplicates.conflict(duplicates.subject(d), "short", rows, clip_of=m.parent.name):
            continue  # a Short on this story already exists (clipped or made from the queue): a second one would tell it twice
        texts = [l["text"] for l in d["lines"]]
        try:
            words = json.loads((m.parent / "words.json").read_text())
        except (OSError, ValueError):
            words = []
        ws = windows(d["lines"], d["chapters"], line_seconds(words, texts, editprofile.short_pause()))
        for w in pick(ws, MAX_TRIES, used=[*d.get("clips", []), *d.get("clips_failed", [])]):
            if MODERN_MEDIA.search(" ".join(l["text"] for l in w["lines"])):
                _record(m, "clips_failed", w["start"])  # a chapter about a film's box office or reviews is not a legend: never cut as a Short
                continue
            data = build_short(d, w, hook(d, w, chat), m.parent.name, outro_for(d["topic"], recent_endings()))
            try:
                folder = produce(data, d["topic"], requeue=False, pool_size=10, min_unique=3)
            except (Exception, SystemExit):  # missing footage, a voice failure: skip this chapter for good, try the next
                _record(m, "clips_failed", w["start"])
                continue
            _record(m, "clips", w["start"])
            return folder
    return None


def make_from(slug: str, extra: dict | None = None, produce=None, chat=None):
    """One Short cut from this named documentary (the owner asked for it), with `extra` settings merged into the Short's record (for example a 3D look and animation).
    The same chapter rules as make_next. Returns the Short's folder, or None when no chapter is usable or the pictures could not be made."""
    if produce is None:
        import run

        produce = run._produce_short
    path = config.OUT / slug / "meta.json"
    try:
        d = json.loads(path.read_text())
        texts = [l["text"] for l in d["lines"]]
        chapters = d["chapters"]
    except (OSError, ValueError, KeyError):
        return None
    try:
        words = json.loads((path.parent / "words.json").read_text())
    except (OSError, ValueError):
        words = []
    ws = windows(d["lines"], chapters, line_seconds(words, texts, editprofile.short_pause()))
    for w in pick(ws, MAX_TRIES, used=[*d.get("clips", []), *d.get("clips_failed", [])]):
        if MODERN_MEDIA.search(" ".join(l["text"] for l in w["lines"])):
            _record(path, "clips_failed", w["start"])
            continue
        data = {**build_short(d, w, hook(d, w, chat), slug, outro_for(d["topic"], recent_endings())), **(extra or {})}
        try:
            folder = produce(data, d["topic"], requeue=False, pool_size=10, min_unique=3)
        except (Exception, SystemExit):
            _record(path, "clips_failed", w["start"])
            continue
        _record(path, "clips", w["start"])
        return folder
    return None
