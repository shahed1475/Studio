"""The owner's weekly programme (30 Oct 2026): four films and six Shorts a week.

Films: day 1 a mystery from history, day 2 an unsolved crime or case, day 3 a famous person, day 4 whatever is trending on the channel's subject. The studio keeps this rotation by looking at its
last three films (not the calendar), so a late film or a skipped day cannot break it: the next film is the first of mystery, case, person that the last three were not, and when all three were
covered it is the trending one (the plain research ranking). It PREFERS the wanted kind (topicrank.pop_best): when none is queued the best topic is made instead and the activity feed says so.
Shorts: five come from the week's films (Autopilot already clips our own films first) and the sixth copies what our best Short did (shortpick). Off by default: `weekly.enabled` in autopilot.json."""
import datetime as dt

import kinds
import records

ORDER = ("mystery", "case", "person")  # the three fixed days; the fourth is whatever is trending
WEEK = dt.timedelta(days=7)


def enabled(cfg: dict | None) -> bool:
    return bool(((cfg or {}).get("weekly") or {}).get("enabled"))


def next_long_kind(recent: list[str]) -> str:
    covered = set(recent[:3])
    return next((k for k in ORDER if k not in covered), "trending")


def _when(meta: dict) -> dt.datetime | None:
    raw = meta.get("made_at") or meta.get("uploaded_at") or meta.get("publish_at")
    try:
        return dt.datetime.fromisoformat(str(raw).replace("Z", "+00:00")) if raw else None
    except ValueError:
        return None


def recent_doc_kinds(metas: list[dict], n: int = 3) -> list[str]:
    """The kinds of the newest n films that are not on hold, newest first."""
    docs = [(w, m) for m in metas if records.format_of(m, m.get("slug", "")) == "doc" and not m.get("hold") for w in [_when(m)] if w]
    docs.sort(key=lambda x: x[0], reverse=True)
    return [m.get("kind") or kinds.classify(m) for _, m in docs[:n]]


def winner_due(metas: list[dict], cfg: dict, now: dt.datetime) -> bool:
    """True when this week already holds exactly `short_from_long` Shorts (not on hold): the next one is the sixth, which copies what our best Short did."""
    if not enabled(cfg):
        return False
    n = int((cfg["weekly"].get("short_from_long")) or 5)
    made = [m for m in metas if records.format_of(m, m.get("slug", "")) == "short" and not m.get("hold") and (_when(m) or now - 2 * WEEK) >= now - WEEK]
    return len(made) == n
