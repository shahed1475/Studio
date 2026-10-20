"""The daily plan: which publish slots are coming, what fills each one, and how many videos Autopilot still has to make.

Autopilot keeps the next `plan_ahead` slots of each kind (documentary, Short) covered. A slot is covered when a video is scheduled for it, or a video
that will be (reviewed, being repaired, passed and waiting for its slot) is on its way. Only the slots nothing covers need a new video, so nothing is
made for a day that is already taken, and a day is never left empty without a video being prepared for it.
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


def rows(cfg: dict, videos: list[dict], now: dt.datetime, per_format: int | None = None) -> list[dict]:
    """The coming slots with what fills each: uploaded, scheduled, a video on its way (ready or being repaired), or empty (to make).
    A slot closer than the review window cannot be filled by a new video any more and says so."""
    earliest = now + dt.timedelta(hours=cfg["review_window_hours"])
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
        pipeline = [v for v in mine if coming(v)]
        pipeline.sort(key=lambda v: (0 if v.get("verdict") == "pass" else 1, v.get("slug", "")))
        for at in slots:
            row = {"format": fmt, "at": scheduler.to_rfc3339(at), "us": scheduler.fmt_local(at, TZ_AUDIENCE), "bd": scheduler.fmt_local(at, TZ_OWNER),
                   "slug": None, "title": "", "status": "empty"}
            if at in taken:
                v = taken[at]
                row.update(slug=v["slug"], title=v.get("title", ""), status="uploaded" if v.get("video_id") else "scheduled")
            elif at < earliest:
                row["status"] = "too_soon"
            elif pipeline:
                v = pipeline.pop(0)
                row.update(slug=v["slug"], title=v.get("title", ""), status="ready" if v.get("verdict") == "pass" else "repairing" if v.get("verdict") else "checking")
            out.append(row)
    return sorted(out, key=lambda r: (r["at"], r["format"]))


def needs(cfg: dict, videos: list[dict], now: dt.datetime) -> dict:
    """How many new videos of each kind are still missing for the next `plan_ahead` fillable slots."""
    earliest = now + dt.timedelta(hours=cfg["review_window_hours"])
    out = {}
    for fmt in ("doc", "short"):
        fillable = [at for at in slot_times(slots_for(cfg, fmt), now) if at >= earliest][: cfg["plan_ahead"]]
        keep = {scheduler.to_rfc3339(a) for a in fillable}
        empty = [r for r in rows(cfg, videos, now) if r["format"] == fmt and r["at"] in keep and r["status"] == "empty"]
        out[fmt] = len(empty)
    return out


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
