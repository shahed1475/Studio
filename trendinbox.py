"""Trending videos a person (or an assistant in the owner's own browser) read from YouTube Studio's Trends tab, which has no API.

Autopilot never opens Studio itself: reading it unattended would need the owner's Google session on the server and YouTube's terms bar automated
access without written permission. This file is the hand-over: a few lines of public facts (title, channel, views, age, length), each one a ranking
signal for 14 days. Titles are third-party text: they are cleaned, length-capped and used only for word overlap, never as instructions.
"""
import datetime as dt
import json
import re

import config
import filelock
import seo
import trendwatch

FILE = config.ROOT / "data" / "trend_inbox.json"  # not under data/trends/: trendwatch.latest() reads the last file there as the weekly digest
MAX_ITEMS = 60
SOURCES = {"manual", "studio_trends"}
DEFAULT_SCORE = 3.0  # a person saw it on a trend feed: treated as clearly taking off, not as a record
WATCH = re.compile(r"^https://(www\.|m\.)?(youtube\.com/(watch\?v=|shorts/)|youtu\.be/)[A-Za-z0-9_-]{5,}")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def _read() -> list[dict]:
    try:
        data = json.loads(FILE.read_text())
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def add(title: str, channel: str = "", views: int = 0, age_days: float = 0.0, seconds: int = 0, url: str = "", source: str = "manual",
        score: float = DEFAULT_SCORE, note: str = "", now: dt.datetime | None = None) -> dict:
    """Keep one trending video. Raises ValueError for an empty or over-long title or a link that is not a YouTube video address."""
    now = now or dt.datetime.now(dt.timezone.utc)
    title = seo.plain(title)
    if not title or len(title) > 200:
        raise ValueError("a title of 1 to 200 characters is needed")
    if url and not WATCH.match(url.strip()):
        raise ValueError("the link must be a YouTube video address (youtube.com/watch, /shorts or youtu.be)")
    item = {"title": title, "channel": seo.plain(channel)[:80], "views": max(0, int(views)), "age_days": max(0.0, float(age_days)), "seconds": max(0, int(seconds)),
            "url": url.strip(), "source": source if source in SOURCES else "manual", "score": min(20.0, max(0.0, float(score))), "note": seo.plain(note)[:200],
            "added_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
    with filelock.locked(FILE):
        kept = [i for i in _read() if _norm(i.get("title", "")) != _norm(title)]
        filelock.write_atomic(FILE, json.dumps((kept + [item])[-MAX_ITEMS:], indent=2))
    return item


def active(now: dt.datetime | None = None) -> list[dict]:
    """The items added within the fresh window, newest first."""
    now = now or dt.datetime.now(dt.timezone.utc)
    edge = (now - dt.timedelta(days=trendwatch.FRESH_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return sorted((i for i in _read() if i.get("added_at", "") >= edge), key=lambda i: i["added_at"], reverse=True)


def import_items(rows: list, source: str = "manual", now: dt.datetime | None = None) -> tuple[list[dict], list[str]]:
    """Add many rows (dicts with the same names as `add`). A bad row is reported with its position and skipped; the rest are kept."""
    done, problems = [], []
    for n, row in enumerate(rows, 1):
        try:
            if not isinstance(row, dict):
                raise ValueError("not an object")
            fields = {k: row[k] for k in ("title", "channel", "views", "age_days", "seconds", "url", "score", "note") if k in row}
            done.append(add(source=source, now=now, **fields))
        except (ValueError, TypeError) as e:
            problems.append(f"row {n}: {e}")
    return done, problems


def taking_off() -> dict:
    """Everything that is taking off now, for the dashboard: the niche search (documentaries and Shorts), new uploads from the reference channels that beat
    their channel's usual views, and the inbox. Empty lists, never an error, before any study has run."""
    import channelwatch

    fresh = (trendwatch.latest() or {}).get("fresh") or {}
    hits = [v for c in ((channelwatch.latest() or {}).get("channels") or []) for v in c.get("fresh") or []]
    return {"docs": fresh.get("docs") or [], "shorts": fresh.get("shorts") or [], "channels": sorted(hits, key=lambda v: -float(v.get("score") or 0)),
            "inbox": active(), "hint": fresh.get("hint") or {}}
