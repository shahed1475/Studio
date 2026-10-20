"""The daily plan: which publish slots are coming, what fills each one, and how many videos Autopilot still has to make.

A video is made just in time: finished and approved a full review window (24 h) before its slot, started `prepare_hours` before that window opens. Slots
inside that horizon are due. A due slot is filled by a passed video, else the best unfinished draft is repaired, else a new video is made; slots beyond
the horizon cost nothing. See docs/AUTOPILOT.md.
"""
import datetime as dt
import os
from pathlib import Path

import config
import scheduler

TZ_AUDIENCE = "America/New_York"
TZ_OWNER = "Asia/Dhaka"
MATCH = dt.timedelta(hours=6)  # a scheduled video belongs to the slot it is within 6 hours of


def slot_times(slots: list[dict], now: dt.datetime, days: int = 22, tz: str = TZ_AUDIENCE) -> list[dt.datetime]:
    """Every publish slot from now on, as UTC instants, oldest first."""
    from zoneinfo import ZoneInfo

    zone = ZoneInfo(tz)
    out = []
    for offset in range(days):
        day = now.astimezone(zone).date() + dt.timedelta(days=offset)
        for s in slots:
            if scheduler.DAYS[day.weekday()] == s["day"]:
                hh, mm = map(int, s["time"].split(":"))
                at = dt.datetime.combine(day, dt.time(hh, mm), tzinfo=zone).astimezone(dt.timezone.utc)
                if at > now:
                    out.append(at)
    return sorted(out)


def _parse(ts: str) -> dt.datetime:
    return dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))


def slots_for(cfg: dict, fmt: str) -> list[dict]:
    return cfg["short_slots"] if fmt == "short" else cfg["slots"]


def coming(v: dict) -> bool:
    """A video that has no slot yet but will get one: not yet reviewed, passed and waiting, or still being repaired."""
    if v.get("video_id") or v.get("hold") or v.get("publish_at") or v.get("source") == "news":
        return False
    verdict = v.get("verdict")
    if verdict in (None, "pass"):
        return True
    by_you = v.get("approved") and v.get("approved_by") == "you"
    return by_you or (verdict in ("fail", "needs_human") and v.get("fix_attempts", 0) < 2 and not v.get("gave_up"))


def horizon(cfg: dict, now: dt.datetime) -> dt.datetime:
    """Slots up to here are due: their video is made now so it is finished a full review window (24 h) before the slot."""
    return now + dt.timedelta(hours=cfg["review_window_hours"] + cfg["prepare_hours"])


def _draft_key(v: dict) -> tuple:
    return (0 if v.get("verdict") is None else 1, 0 if v.get("fix_attempts", 0) > 0 else 1, v.get("blocking", 9), v.get("slug", ""))


def rows(cfg: dict, videos: list[dict], now: dt.datetime, per_format: int | None = None) -> list[dict]:
    """The coming slots and what fills each: uploaded, scheduled, ready (passed, its time is set next), a draft being repaired or checked, empty (a new
    video is made now), later (not due: nothing is made or repaired until `starts`), or too soon (less than the review window away, cannot take a new video).
    Passed videos take the earliest empty slots; drafts and new videos are only for slots that are due."""
    earliest = now + dt.timedelta(hours=cfg["review_window_hours"])
    due_until = horizon(cfg, now)
    out = []
    for fmt in ("doc", "short"):
        slots = slot_times(slots_for(cfg, fmt), now)
        if per_format:
            slots = slots[:per_format]
        mine = [v for v in videos if (v.get("format") or "doc") == fmt]
        taken = {}
        for v in mine:
            if v.get("publish_at") and not v.get("hold") and not (v.get("verdict") in ("fail",) and not v.get("approved")):
                at = _parse(v["publish_at"])
                best = min(slots, key=lambda s: abs(s - at), default=None)
                if best is not None and abs(best - at) <= MATCH and best not in taken:
                    taken[best] = v
        ready = sorted((v for v in mine if coming(v) and v.get("verdict") == "pass"), key=lambda v: v.get("slug", ""))
        drafts = sorted((v for v in mine if coming(v) and v.get("verdict") != "pass"), key=_draft_key)
        for at in slots:
            starts = at - dt.timedelta(hours=cfg["review_window_hours"] + cfg["prepare_hours"])
            row = {"format": fmt, "at": scheduler.to_rfc3339(at), "us": scheduler.fmt_local(at, TZ_AUDIENCE), "bd": scheduler.fmt_local(at, TZ_OWNER),
                   "slug": None, "title": "", "status": "empty", "starts_us": scheduler.fmt_local(starts, TZ_AUDIENCE), "starts_bd": scheduler.fmt_local(starts, TZ_OWNER)}
            if at in taken:
                v = taken[at]
                row.update(slug=v["slug"], title=v.get("title", ""), status="uploaded" if v.get("video_id") else "scheduled")
            elif at < earliest:
                row["status"] = "too_soon"
            elif ready:
                v = ready.pop(0)
                row.update(slug=v["slug"], title=v.get("title", ""), status="ready")
            elif at > due_until:
                row["status"] = "later"
            elif drafts:
                v = drafts.pop(0)
                row.update(slug=v["slug"], title=v.get("title", ""), status="repairing" if v.get("verdict") else "checking")
            out.append(row)
    return sorted(out, key=lambda r: (r["at"], r["format"]))


def needs(cfg: dict, videos: list[dict], now: dt.datetime) -> dict:
    """How many new videos of each kind are missing for the slots that are due."""
    out = {"doc": 0, "short": 0}
    for r in rows(cfg, videos, now):
        if r["status"] == "empty":
            out[r["format"]] += 1
    return out


def repair_targets(cfg: dict, videos: list[dict], now: dt.datetime) -> set[str]:
    """The drafts worth working on now: the ones that take a slot which is due. Every other draft stays parked."""
    return {r["slug"] for r in rows(cfg, videos, now) if r["status"] in ("repairing", "checking") and r["slug"]}


def sync_ready_folder(videos: list[dict], root: Path | None = None) -> list[str]:
    """ready/ holds one link per video that passed, is approved and has a post time, named by that time, so the folder reads as the posting order."""
    root = root or config.ROOT / "ready"
    root.mkdir(exist_ok=True)
    want = {}
    for v in videos:
        if v.get("publish_at") and v.get("approved") and not v.get("hold") and v.get("verdict") == "pass":
            at = _parse(v["publish_at"])
            want[f"{at.strftime('%Y-%m-%d_%H%MZ')}_{v.get('format') or 'doc'}_{v['slug'][:50]}"] = v["slug"]
    for p in root.iterdir():
        if p.is_symlink() and p.name not in want:
            p.unlink()  # only our own links are ever removed
    for name, slug in want.items():
        link = root / name
        if not link.is_symlink():
            link.symlink_to(os.path.relpath(config.OUT / slug, root))
    return sorted(want)
