"""Stuck drafts: a video the fixer gave up on is given to the escalation ladder before it waits for the owner.

One draft per run, never one the owner approved, held or that is on YouTube, never one over its spending limit or when the day's money is spent. The ladder
may only choose from the safe fixes below. After a fix the video is reviewed again so the answer is real; a draft the ladder tried twice goes to Needs you."""
import datetime as dt
import json
from pathlib import Path

import config
import escalate
import records

MAX_LADDER = 2


def candidates(out: Path | None = None) -> list[tuple[Path, dict]]:
    import fixer

    found = []
    for m in sorted((out or config.OUT).glob("*/meta.json")):
        try:
            meta = json.loads(m.read_text())
        except ValueError:
            continue
        review = meta.get("review") or {}
        if meta.get("video_id") or meta.get("hold") or meta.get("approved_by") == "you" or meta.get("source") == "news":
            continue
        if review.get("verdict") not in ("fail", "needs_human") or (meta.get("ladder") or {}).get("tries", 0) >= MAX_LADDER:
            continue
        if meta.get("fix_attempts", 0) >= fixer.attempt_limit(review.get("checks", [])) or meta.get("fix_gave_up"):
            found.append((m.parent, meta))
    return sorted(found, key=lambda fm: ((fm[1].get("format") or "doc") != "doc", fm[0].name))


def affordable(slug: str, fmt: str) -> bool:
    import autopilot
    import llm

    limit = autopilot.MAX_VIDEO_COST.get(fmt, 2.5)
    return llm.video_cost(slug) < limit - 0.3 and llm.spent_today() < llm.load_config()["daily_budget_usd"] - 0.3


def fixes_for(folder: Path, chat=None, review=None) -> dict:
    import fixer
    import reviewer
    import thumbnail

    review = review or reviewer.review

    def verdict() -> bool:
        return review(folder).get("verdict") == "pass"

    def edit(apply) -> tuple[bool, str]:
        meta = json.loads((folder / "meta.json").read_text())
        note = apply(meta)
        if not note:
            return False, "nothing changed"
        meta["fix_attempts"] = 0  # the repaired draft gets its normal tries again
        meta.pop("fix_gave_up", None)
        reviewer.invalidate(meta)
        try:
            records.save(folder, meta)
        except OSError as e:
            return False, f"could not save the change ({type(e).__name__})"
        ok = verdict()
        return ok, note + ("; the review now passes" if ok else "; the review still does not pass")

    def new_title(meta):
        t = fixer.pick_title(meta, fixer.other_titles(folder), chat)
        if t:
            meta["title"] = t
            return f"new title: {t}"

    def new_hook(meta):
        hook = thumbnail.hook_for(meta, avoid=[meta.get("thumb_hook", "")])
        thumbnail.make(folder, hook)
        meta["thumb_hook"] = hook
        return f"new thumbnail text: {hook}"

    def new_description(meta):
        if fixer.realign_description(meta, "", chat):
            return "description rewritten from what the video covers"

    def more_tries(meta):
        if (meta.get("ladder") or {}).get("extra"):
            return None
        meta["ladder"] = {**(meta.get("ladder") or {}), "extra": True}
        return "one more repair round allowed"

    return {"new_title": ("choose a different honest title", lambda: edit(new_title)),
            "new_thumbnail_text": ("write new thumbnail text", lambda: edit(new_hook)),
            "rewrite_description": ("rewrite the description to match the narration", lambda: edit(new_description)),
            "one_more_repair": ("let the fixer try the whole video once more", lambda: edit(more_tries))}


def run(now: dt.datetime | None = None, out: Path | None = None, chat=None, review=None, ladder_chat=None, lock_file: Path | None = None) -> dict:
    import fcntl

    import autopilot

    now = now or dt.datetime.now(dt.timezone.utc)
    lock = open(lock_file or autopilot.LOCK_FILE, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)  # Autopilot may be repairing a draft right now
    except BlockingIOError:
        return {"skipped": "locked"}
    try:
        return _run(now, out, chat, review, ladder_chat)
    finally:
        lock.close()


def _run(now, out, chat, review, ladder_chat) -> dict:
    for folder, meta in candidates(out):
        slug, fmt = folder.name, meta.get("format") or "doc"
        try:
            records.update(folder, lambda d: d.__setitem__("ladder", {**(d.get("ladder") or {}), "tries": (d.get("ladder") or {}).get("tries", 0) + 1,
                                                                     "at": now.strftime("%Y-%m-%dT%H:%M:%SZ")}))
        except OSError:
            return {"skipped": "could not save the video record"}  # nothing was tried; the next run starts again
        checks = [c for c in (meta.get("review") or {}).get("checks", []) if not c["ok"] and c["severity"] in ("block", "human")]
        problem = f"video {fmt} repair failed: " + ", ".join(c["name"] for c in checks)
        evidence = " | ".join(f"{c['name']}: {c.get('detail', '')[:160]}" for c in checks[:5])
        import llm

        with llm.cost_scope(slug):
            res = escalate.solve("fixer", problem, evidence, fixes_for(folder, chat, review), slug=slug, may_spend=affordable(slug, fmt), chat=ladder_chat, now=now)
        return {"slug": slug, **res}
    return {"skipped": "no stuck draft"}
