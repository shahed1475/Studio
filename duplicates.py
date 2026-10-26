"""Same-subject check: the studio never tells the same story twice in the same format.

A video's subject is the distinctive words of its topic and of its first Wikipedia source article (generic words such as legend, story, myth are ignored).
Two videos of one format with the same subject are duplicates. A Short may sit beside the documentary it was cut from (`source_doc`), but a Short made from the
queue on a documentary's story, or a second Short on one story, is a duplicate. Videos on hold do not count: they are parked, style demos, or duplicates already dealt with.
Used when a topic is chosen, when a clip is chosen, and before a video is scheduled or uploaded."""
import json
import re
import unicodedata
from pathlib import Path

import config

GENERIC = frozenset("""legend legends story stories myth myths mystery mysteries truth real true history historical ancient folklore folktale folktales tale tales origin origins
mythology spirit spirits behind what who why how unsolved lost secret secrets curse haunted haunting famous known many from with that this their about into""".split())


def tokens(text: str) -> frozenset[str]:
    plain = unicodedata.normalize("NFKD", str(text or "")).lower()
    return frozenset(w for w in re.findall(r"[a-z]+", plain) if len(w) >= 4 and w not in GENERIC)


def subject(meta: dict) -> frozenset[str]:
    import reviewer

    return tokens(meta.get("topic", "")) | tokens(reviewer.source_title(meta))


def same_subject(a: frozenset, b: frozenset) -> bool:
    """One side's words all appear in the other's, or two distinctive words are shared."""
    shared = a & b
    return bool(shared) and (shared == a or shared == b or len(shared) >= 2)


def catalogue(out: Path | None = None) -> list[dict]:
    rows = []
    for m in sorted((out or config.OUT).glob("*/meta.json")):
        try:
            d = json.loads(m.read_text())
        except (OSError, ValueError):
            continue
        # a record without a format is a Short: the default the uploader and Autopilot use
        rows.append({"slug": m.parent.name, "format": d.get("format", "short"), "subject": subject(d), "title": d.get("title", ""), "source_doc": d.get("source_doc"),
                     "live": bool(d.get("video_id")), "scheduled": bool(d.get("publish_at")), "hold": bool(d.get("hold")),
                     "at": str(d.get("uploaded_at") or d.get("publish_at") or "")})
    return rows


def takes_its_story(row: dict) -> bool:
    return not row["hold"]  # a video set aside, or pulled back to private, will not go public by itself: parked, a style demo or a duplicate already dealt with


def conflict(subj: frozenset, fmt: str, rows: list[dict], slug: str | None = None, clip_of: str | None = None) -> dict | None:
    """The existing video that already tells this subject in this format, or None. For a new Short, a documentary on the same story also counts unless the
    Short is a clip of that very documentary (`clip_of`)."""
    if not subj:
        return None
    for r in rows:
        if r["slug"] == slug or not takes_its_story(r) or not same_subject(subj, r["subject"]):
            continue
        if r["format"] == fmt or (fmt == "short" and r["format"] == "doc" and clip_of != r["slug"]):
            return r
    return None


def topic_conflict(topic: str, fmt: str, out: Path | None = None) -> dict | None:
    """For a topic about to be made. Never raises: a catalogue that cannot be read lets the topic through (the model's premise screen still stands)."""
    try:
        return conflict(tokens(topic), fmt, catalogue(out))
    except Exception:
        return None


def taken_by(slug: str, rows: list[dict] | None = None, out: Path | None = None) -> dict | None:
    """An earlier video (already out, or scheduled to go out sooner) of the same format and subject, if any: the one to keep. Asked before a video is
    scheduled or uploaded, so the later of two duplicates is the one that waits."""
    rows = catalogue(out) if rows is None else rows
    me = next((r for r in rows if r["slug"] == slug), None)
    if not me or not me["subject"]:
        return None
    mine = (me["at"] if me["scheduled"] or me["live"] else "9999", slug)
    for r in rows:
        if r["slug"] == slug or not takes_its_story(r) or r["format"] != me["format"] or not (r["live"] or r["scheduled"]) or not same_subject(me["subject"], r["subject"]):
            continue
        if r["live"] or (r["at"], r["slug"]) < mine:
            return r
    return None
