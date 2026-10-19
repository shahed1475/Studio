"""How far the channel is from the YouTube Partner Program, in plain numbers, and what is nearest.

Only public numbers from the YouTube Data API are used. Watch hours need the YouTube Analytics permission, so they are reported as unknown
instead of guessed. Rules are as reported in October 2026 by secondary sources: confirm them in YouTube Studio under Earn.
"""
import datetime as dt
import json

import config

EARLY = {"subs": 500, "uploads": 3, "watch_hours": 3000, "shorts_views": 3_000_000}  # fan funding: memberships, Super Thanks
FULL = {"subs": 1000, "watch_hours": 4000, "shorts_views": 10_000_000}  # ad revenue
NOTE = ("Rules as reported in October 2026: first step 500 subscribers, 3 public videos in 90 days and 3,000 watch hours or 3 million Shorts "
        "views; ad revenue 1,000 subscribers and 4,000 watch hours or 10 million Shorts views. From 1 February 2027 new applicants are "
        "reported to need 8,000 watch hours or 20 million Shorts views. That change was not confirmed on YouTube's own page, so check "
        "YouTube Studio, Earn.")


def _m(have: int | None, need: int) -> dict:
    return {"have": have, "need": need, "pct": 0 if have is None else min(100, int(100 * have / need))}


def ready_count() -> int:
    """Videos that are made and passed the check but are not on YouTube yet."""
    n = 0
    for m in config.OUT.glob("*/meta.json"):
        try:
            d = json.loads(m.read_text())
        except ValueError:
            continue
        if not d.get("video_id") and ((d.get("review") or {}).get("verdict") == "pass" or d.get("approved")):
            n += 1
    return n


def progress(snap: dict, now: dt.datetime, ready: int = 0) -> dict:
    subs = snap["subscribers"]
    since = (now - dt.timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
    recent = [v for v in snap.get("recent", []) if v["published"] >= since]
    uploads = len(recent)
    shorts = sum(v["views"] for v in recent if v["seconds"] <= 60)  # views of a video under 90 days old are its 90 day views
    out = {
        "subs": subs, "uploads_90d": uploads, "shorts_views_90d": shorts, "watch_hours": None, "note": NOTE,
        "early": {"subs": _m(subs, 500), "uploads": _m(uploads, 3), "watch_hours": _m(None, 3000), "shorts_views": _m(shorts, 3_000_000)},
        "full": {"subs": _m(subs, 1000), "watch_hours": _m(None, 4000), "shorts_views": _m(shorts, 10_000_000)},
    }
    nxt = []
    if ready:
        nxt.append(f"{ready} video{'s' if ready != 1 else ''} made and checked but not on YouTube yet. Publishing them is the fastest next step.")
    if uploads < 3:
        nxt.append(f"Publish {3 - uploads} more public video{'s' if 3 - uploads != 1 else ''} in the next 90 days (3 are needed for the first step).")
    if subs < 500:
        nxt.append(f"{500 - subs:,} more subscribers for the first step (500), {1000 - subs:,} for ad revenue (1,000).")
    elif subs < 1000:
        nxt.append(f"{1000 - subs:,} more subscribers for ad revenue (1,000).")
    if shorts < 10_000_000:
        nxt.append(f"Shorts views in the last 90 days: {shorts:,}. The first step needs 3,000,000 and ad revenue 10,000,000, or watch hours instead.")
    nxt.append("Watch hours cannot be read yet: they need the YouTube Analytics permission. Look at YouTube Studio, Analytics.")
    if subs >= 1000 and shorts >= 10_000_000:
        nxt.insert(0, "The numbers may already be enough for ad revenue: open YouTube Studio, Earn, and apply.")
    elif subs >= 500 and uploads >= 3 and shorts >= 3_000_000:
        nxt.insert(0, "The numbers may already be enough for the first step: open YouTube Studio, Earn, and apply.")
    out["next"] = nxt
    return out
