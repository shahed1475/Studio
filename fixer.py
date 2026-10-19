"""Fixer agent: when the reviewer blocks a video or asks for a human check, repair what can be repaired and ask the reviewer again.

It never approves, schedules or uploads anything. What it can do:
- a title too close to another video, or a lower-case one: a distinct, properly written title
- tags that belong to other things (a game, a novel series): removed
- a missing thumbnail: made
- names, years or invented details the source article does not support: those narration lines are rewritten from the source,
  and the documentary is re-rendered
- a script with no source, a Short with unsupported claims, or pictures that do not match: the video is moved to output_old
  (never deleted) and its topic goes back in the queue, so the next try starts clean
After two tries a video that still fails is left for you, with the reason shown on the Autopilot page.
"""
import datetime as dt
import difflib
import json
import re
import shutil
from pathlib import Path

import agentlog
import config
import reviewer
import scriptgen
import seo
import topicqueue

MAX_ATTEMPTS = 2
SIMILAR = 0.7  # a new title may not be more like another video's title than this


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def _too_similar(title: str, others: list[str]) -> bool:
    return any(difflib.SequenceMatcher(None, _norm(title), _norm(o)).ratio() >= SIMILAR for o in others)


def other_titles(folder: Path) -> list[str]:
    return [json.loads(m.read_text()).get("title", "") for m in folder.parent.glob("*/meta.json") if m.parent != folder]


def pick_title(meta: dict, others: list[str], chat=None, misleading: str = "") -> str | None:
    """A title that is not like any other video's: the search-based options first, then three new ones from the writer.
    When the reviewer said the title promises more than the story delivers, the writer goes first and is told why."""
    chat = chat or scriptgen._chat
    options = [seo.polish_title(t) for t in (meta.get("seo") or {}).get("titles", [])]
    for t in ([] if misleading else options):
        if t != meta.get("title") and not _too_similar(t, others):
            return t
    story = " ".join(l["text"] for l in meta.get("lines", [])[:8])
    try:
        got = chat("Write 3 different YouTube titles, each under 65 characters, for this story. Honest about what the video covers, no ALL CAPS, "
                   "no emojis, a curiosity hook or a question. They must be clearly different from these existing titles: "
                   + json.dumps(others[:15]) + (f"\nThe reviewer rejected the current title: {misleading[:400]} Do not promise a definite answer the story does not give; "
                                               "a question or a 'what we know' angle is honest." if misleading else "")
                   + f"\nStory: {story}\nReturn JSON: {{\"titles\": [\"...\"]}}")
    except Exception:
        got = {}
    if not got and misleading:  # the writer was down: fall back to the search-based options
        for t in options:
            if t != meta.get("title") and not _too_similar(t, others):
                return t
        return None
    for t in (seo.polish_title(x) for x in got.get("titles", []) if isinstance(x, str)):
        if 8 < len(t) <= 70 and t != meta.get("title") and not _too_similar(t, others):
            return t
    return None


def clean_tags(meta: dict) -> list[str]:
    tags = seo.relevant_tags(list(meta.get("tags", [])), seo.corpus_of(meta))
    for generic in ("history stories for sleep", "legends and folklore"):  # the channel's own niche tags
        if len(tags) < 5 and generic not in tags:
            tags.append(generic)
    return tags


def rewrite_lines(meta: dict, source: str, problems: list[str], chat=None) -> int:
    """Ask the writer to rewrite only the narration lines whose names, years or details the source does not support.
    A rewrite may not bring in a number the source lacks. Returns how many lines were changed."""
    chat = chat or scriptgen._script_chat
    lines = meta.get("lines", [])
    numbered = "\n".join(f"{i}: {l['text']}" for i, l in enumerate(lines))
    try:
        got = chat("You edit the narration of a calm history documentary so every fact is supported.\n"
                   f"SOURCE (the only facts allowed):\n{source[:9000]}\n\nThe fact checker found these problems: {json.dumps(problems)[:1200]}\n\n"
                   f"Narration lines:\n{numbered}\n\nRewrite ONLY the lines that contain a name, year, number or quote the SOURCE does not support, or that the "
                   "problems mention. Use only facts from the SOURCE; if it does not support a detail, drop it or say that some accounts say so. Keep each "
                   "rewritten line 14 to 24 words with the same meaning and tone. Do not add new details.\n"
                   'Reply JSON {"edits": [{"index": 3, "text": "..."}]}')
    except Exception:
        return 0
    allowed_numbers = set(re.findall(r"\d{3,4}", source))
    changed = 0
    for e in (got.get("edits", []) if isinstance(got, dict) else [])[:10]:
        try:
            i, text = int(e["index"]), str(e["text"]).strip()
        except (KeyError, TypeError, ValueError):
            continue
        new_numbers = set(re.findall(r"\d{3,4}", text)) - allowed_numbers - set(re.findall(r"\d{3,4}", lines[i]["text"] if 0 <= i < len(lines) else ""))
        if 0 <= i < len(lines) and 6 <= len(text.split()) <= 40 and not new_numbers and text != lines[i]["text"]:
            lines[i]["text"] = text
            changed += 1
    return changed


def archive(folder: Path) -> Path:
    """Move a video to output_old (never deleted), under a name that is not taken."""
    dest_root = config.ROOT / "output_old"
    dest_root.mkdir(exist_ok=True)
    dest, n = dest_root / folder.name, 2
    while dest.exists():
        dest, n = dest_root / f"{folder.name}-{n}", n + 1
    shutil.move(str(folder), str(dest))
    return dest


def _save(folder: Path, meta: dict) -> None:
    (folder / "meta.json").write_text(json.dumps(meta, indent=2))


def fix(slug: str, chat=None, rerender=None, now: dt.datetime | None = None) -> dict:
    """One repair pass over one video. Returns {"fixed": [...], "archived": reason | None, "verdict": ...}."""
    now = now or dt.datetime.now(dt.timezone.utc)
    folder = config.OUT / slug
    meta = json.loads((folder / "meta.json").read_text())
    attempts = meta.get("fix_attempts", 0)
    if attempts >= MAX_ATTEMPTS or meta.get("fix_gave_up"):
        return {"skipped": "already tried"}
    checks = (meta.get("review") or {}).get("checks", [])
    failing = {c["name"]: c for c in checks if not c["ok"] and c["severity"] in ("block", "human")}
    is_doc = meta.get("format") == "doc"
    fixed: list[str] = []
    archive_reason = None

    if "duplicate_title" in failing or "title_matches" in failing or not any(ch.isupper() for ch in meta.get("title", "")):
        t = pick_title(meta, other_titles(folder), chat, failing["title_matches"]["detail"] if "title_matches" in failing else "")
        if t:
            meta["title"] = t
            fixed.append(f"new title: {t}")
    tags = clean_tags(meta)
    if tags != meta.get("tags"):
        meta["tags"] = tags
        fixed.append("cleaned the tags")
    if "thumbnail" in failing and is_doc:
        import thumbnail

        thumbnail.make(folder)
        meta = {**json.loads((folder / "meta.json").read_text()), "title": meta["title"], "tags": meta["tags"]}
        fixed.append("made the thumbnail")

    rewrite = False
    if {"claims", "invented_facts", "policy_risk"} & set(failing):
        source = reviewer.source_text(meta)
        problems = [c["detail"] for n, c in failing.items() if n in ("claims", "invented_facts", "policy_risk")]
        if is_doc and source:
            problems += reviewer.unhedged_claims([l["text"] for l in meta.get("lines", [])], source)
            n = rewrite_lines(meta, source, problems, chat)
            if n:
                fixed.append(f"rewrote {n} narration lines from the source")
                rewrite = True
            else:
                archive_reason = "its facts could not be repaired from the source"
        else:
            archive_reason = "a script whose facts cannot be checked against a source"
    if "grounded" in failing or ("images" in failing and failing["images"]["severity"] == "block"):
        archive_reason = archive_reason or ("its script has no source article" if "grounded" in failing else "its pictures do not match the story")

    if archive_reason:
        _save(folder, meta)
        dest = archive(folder)
        kept = topicqueue.requeue_failed(meta.get("topic", "")) if meta.get("topic") else False
        agentlog.event("info", f"Set aside and remade: {meta.get('title', slug)}", f"{archive_reason}. {'The topic is back in the queue.' if kept else 'The topic was dropped after two tries.'} Saved in {dest.parent.name}.", now=now)
        return {"fixed": fixed, "archived": archive_reason, "verdict": None}

    reviewer.invalidate(meta)
    meta["fix_attempts"] = attempts + 1
    _save(folder, meta)
    if rewrite:
        (rerender or _rerender)(slug)  # the voice and pictures are made again from the corrected script
        meta = json.loads((folder / "meta.json").read_text())
        meta["fix_attempts"] = attempts + 1
        _save(folder, meta)
    result = reviewer.review(folder)
    meta = json.loads((folder / "meta.json").read_text())
    if result["verdict"] != "pass" and attempts + 1 >= MAX_ATTEMPTS:
        meta["fix_gave_up"] = True
        _save(folder, meta)
        why = "; ".join(c["detail"] for c in result["checks"] if not c["ok"] and c["severity"] in ("block", "human"))[:300]
        agentlog.event("error", f"Needs your eyes: {meta.get('title', slug)}", f"I tried twice and the reviewer still says {result['verdict']}: {why}", notify=True, now=now)
    elif fixed:
        agentlog.event("applied", f"Fixed: {meta.get('title', slug)}", "; ".join(fixed) + f". The reviewer now says {result['verdict']}.", now=now)
    return {"fixed": fixed, "archived": None, "verdict": result["verdict"]}


def _rerender(slug: str) -> None:
    import run

    run.cmd_redo(slug)
