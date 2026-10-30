"""The pace governor: how many documentaries and Shorts Autopilot may make and schedule in any 7 days, set from YouTube's inauthentic-content rule.

YouTube states no upload limit. Its monetization page says channels are judged as a whole (main theme, newest and most-viewed videos, titles) and that
templated, repetitive or mass-produced content is not allowed to earn; the spam policy bans using tools or AI to make high volumes of similar content with minimal
changes. So volume matters only through sameness. The numbers here are our own judgement, written down in docs/superpowers/plans/2026-10-27-pace-governor.md.
The governor only tightens: the base is the most Autopilot will ever do, and a higher base is the owner's choice (`governor.base` in autopilot.json)."""
import datetime as dt
import json
from pathlib import Path

import config
import records

BASE = {"doc": 3, "short": 7}  # per 7 days: 10 in all
WATCH_ABOVE, ACT_ABOVE = 10, 13  # the Risks card: more videos than this in the busiest 7 days is watch, act
WEEK = dt.timedelta(days=7)
STRUCTURE_WATCH, THEME_WATCH, RECENT = 0.6, 0.5, 8
FILE = Path("data") / "governor.json"


def _when(v: dict) -> dt.datetime | None:
    raw = v.get("publish_at") or v.get("uploaded_at")
    try:
        return dt.datetime.fromisoformat(str(raw).replace("Z", "+00:00")) if raw else None
    except ValueError:
        return None


def _times(videos, fmt: str | None = None) -> list[dt.datetime]:
    return sorted(t for v in videos if not v.get("hold") and (fmt is None or records.format_of(v, v.get("slug", "")) == fmt) for t in [_when(v)] if t)


def window_load(videos, now: dt.datetime) -> int:
    """The most videos (held ones and ones without a time ignored) in any real 7-day span between a week ago and a week from now."""
    ts = [t for t in _times(videos) if now - WEEK <= t <= now + WEEK]
    return max((sum(1 for u in ts if s <= u < s + WEEK) for s in ts), default=0)


def allowed(videos, fmt: str, at: dt.datetime, caps: dict | None) -> bool:
    """True when one more video of this format at `at` keeps every 7-day span that contains it within the cap. No caps: everything is allowed."""
    cap = (caps or {}).get(fmt)
    if cap is None:
        return True
    if cap <= 0:
        return False
    ts = _times(videos, fmt) + [at]
    return all(sum(1 for u in ts if s <= u < s + WEEK) <= cap for s in ts if at - WEEK < s <= at)


def theme_share(vs) -> float:
    """The largest share of the last stories (a Short clipped from a documentary is the same story) that use one distinctive word. 0 under four stories."""
    import duplicates

    recent = [m for _, m in sorted(vs, key=lambda x: x[1].get("made_at") or x[1].get("uploaded_at") or "")][-RECENT:]
    stories: dict[str, frozenset] = {}
    for i, m in enumerate(recent):
        key = m.get("source_doc") or m.get("slug") or f"#{i}"
        try:
            stories[key] = stories.get(key, frozenset()) | duplicates.subject(m)
        except Exception:
            stories.setdefault(key, frozenset())
    if len(stories) < 4:
        return 0.0
    words = set().union(*stories.values())
    return max((sum(1 for s in stories.values() if w in s) / len(stories) for w in words), default=0.0)


def caps(vs, now: dt.datetime, base: dict | None = None) -> dict:
    """{doc, short, level, why}: weekly caps per format. Starts at the base and only goes down; a reading that fails changes nothing."""
    start = {**BASE, **{k: int(x) for k, x in (base or {}).items() if k in BASE}}
    doc, short, why = start["doc"], start["short"], []
    try:
        import risk

        row = risk.pattern(vs, now)
    except Exception:
        row = {}
    try:
        theme = theme_share(vs)
    except Exception:
        theme = 0.0
    if row.get("content_act"):
        return {"doc": 0, "short": 0, "level": "act", "why": ["repeated openings or one shared structure are at the act level: nothing new is made until they clear"]}
    if row.get("same_structure", 0) >= STRUCTURE_WATCH:
        doc -= 1
        why.append(f"{row['same_structure']:.0%} of the last videos share one structure: one documentary fewer a week")
    if row.get("pairs", 0) >= 1:
        doc, short = doc - 1, short - 1
        why.append(f"{row['pairs']} pair(s) of near-identical openings: one fewer of each a week")
    if theme >= THEME_WATCH:
        doc, short = doc - 1, short - 1
        why.append(f"{theme:.0%} of the recent stories share one theme word: one fewer of each a week, and the next topics should be different")
    return {"doc": max(1, doc), "short": max(1, short), "level": "watch" if why else "ok", "why": why}


def record(c: dict, now: dt.datetime) -> None:
    """Save the caps and tell the owner once when they change. Never raises."""
    try:
        path = config.ROOT / FILE
        old = json.loads(path.read_text()) if path.exists() else {}
        if (old.get("doc"), old.get("short")) == (c["doc"], c["short"]):
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({**c, "at": now.strftime("%Y-%m-%dT%H:%M:%SZ")}, indent=1))
        import agentlog

        agentlog.event("info", f"Autopilot changed its weekly pace: {c['doc']} documentaries, {c['short']} Shorts",
                       " ".join(c["why"]) or "Nothing to worry about now: the base pace is back.", now=now)
    except Exception:
        pass
