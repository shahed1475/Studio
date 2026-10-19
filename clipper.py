"""Shorts cut from our own finished documentaries (never from anyone else's video).

A chapter that works on its own is re-told as a vertical Short: a new hook first, the chapter's lines, then a closing line that
points to the full video. Voice, pictures and render are rebuilt from the saved script, so no model call is needed beyond one short hook.
"""
import json
import re

import config
import scriptgen

MAX_CLIPS = 3  # per documentary
MAX_TRIES = 2  # chapters tried in one run
LO, HI = 25.0, 50.0  # seconds of story; with hook and closing line a Short stays under 59 seconds
WORDS_PER_SEC = 2.3
PAUSE = 0.12
OUTRO = "The full story is on our channel."
CONTRAST = re.compile(r"\b(but|however|yet|until|secret|hidden|never|only|nobody|vanished|disappeared|mystery)\b", re.I)


def line_seconds(words: list[dict], texts: list[str]) -> list[float]:
    """Seconds each narration line lasts: from the saved word timings, else estimated from the word count."""
    spans: dict[int, list[float]] = {}
    for w in words:
        s = spans.setdefault(w["i"], [w["s"], w["e"]])
        s[0], s[1] = min(s[0], w["s"]), max(s[1], w["e"])
    return [round(spans[i][1] - spans[i][0] + PAUSE, 2) if i in spans else round(len(t.split()) / WORDS_PER_SEC + PAUSE, 2) for i, t in enumerate(texts)]


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


def hook(meta: dict, w: dict, chat=None) -> dict:
    """A hook line (under 12 words) that raises a question, and a title. A model failure falls back to the story's own words."""
    chat = chat or scriptgen._chat
    story = " ".join(l["text"] for l in w["lines"])[:900]
    try:
        got = chat(f"Documentary: {meta['title']}. This part is called '{w['chapter']}'. Story part:\n{story}\n\n"
                   "Write a first line for a YouTube Short that makes a viewer need the answer (a question or a surprising claim, "
                   "under 12 words, true to the story, no clickbait lies) and a title under 70 characters. "
                   'Return JSON {"hook": "...", "title": "..."}')
        h, t = str(got["hook"]).strip(), str(got["title"]).strip()
        if h and t:
            return {"hook": _trim(h, 12), "title": t[:70]}
    except Exception:
        pass
    question = next((l["text"] for l in w["lines"] if "?" in l["text"]), "")
    title = (w["chapter"] or meta["title"]).strip()
    return {"hook": _trim(question or f"What really happened: {title}?", 12), "title": title[:70]}


def build_short(meta: dict, w: dict, h: dict, doc_slug: str) -> dict:
    first = w["lines"][0].get("visual", "")
    lines = [{"text": h["hook"], "visual": first}, *[{"text": l["text"], "visual": l.get("visual", "")} for l in w["lines"]],
             {"text": OUTRO, "visual": first}]
    desc = f"{meta.get('description', '').split(chr(10) + chr(10) + 'Chapters:')[0].strip()}"
    if meta.get("video_id"):
        desc += f"\n\nFull video: https://youtu.be/{meta['video_id']}"
    return {"topic": meta["topic"], "format": "short", "grounded": bool(meta.get("grounded")), "anchors": meta.get("anchors", []),
            "title": h["title"], "description": desc, "tags": meta.get("tags", []), "lines": lines, "sources": meta.get("sources", []),
            "source_doc": doc_slug, "clip_start_line": w["start"]}


def _docs() -> list:
    out = []
    for m in sorted(config.OUT.glob("*/meta.json")):
        try:
            d = json.loads(m.read_text())
        except ValueError:
            continue
        ok = (d.get("review") or {}).get("verdict") == "pass" or (d.get("approved") and d.get("approved_by") == "you")
        if d.get("format") == "doc" and d.get("lines") and d.get("chapters") and ok and len(d.get("clips", [])) + len(d.get("clips_failed", [])) < MAX_CLIPS:
            out.append((m, d))
    return out


def clippable() -> int:
    return len(_docs())


def make_next(produce=None, chat=None):
    """Make one Short from the first documentary that still has an unused good chapter. Returns the Short's folder, or None."""
    if produce is None:
        import run

        produce = run._produce_short
    for m, d in _docs():
        texts = [l["text"] for l in d["lines"]]
        try:
            words = json.loads((m.parent / "words.json").read_text())
        except (OSError, ValueError):
            words = []
        ws = windows(d["lines"], d["chapters"], line_seconds(words, texts))
        for w in pick(ws, MAX_TRIES, used=[*d.get("clips", []), *d.get("clips_failed", [])]):
            data = build_short(d, w, hook(d, w, chat), m.parent.name)
            try:
                folder = produce(data, d["topic"], requeue=False, pool_size=10, min_unique=3)
            except (Exception, SystemExit):  # missing footage, a voice failure: skip this chapter for good, try the next
                d["clips_failed"] = [*d.get("clips_failed", []), w["start"]]
                m.write_text(json.dumps(d, indent=2))
                continue
            d["clips"] = [*d.get("clips", []), w["start"]]
            m.write_text(json.dumps(d, indent=2))
            return folder
    return None
