"""Our own channel's numbers: a daily snapshot from the YouTube Data API and a plain-number analysis."""
import datetime as dt
import json
import statistics

import config
import trendwatch

DIR = config.ROOT / "data" / "agent" / "own"


def snapshot(yt, now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    items = yt.channels().list(part="snippet,statistics,contentDetails", mine=True).execute().get("items", [])
    if not items:
        raise ValueError("no YouTube channel is connected to this login")
    c = items[0]
    s = c.get("statistics", {})
    ids = [i["contentDetails"]["videoId"] for i in
           yt.playlistItems().list(part="contentDetails", playlistId=c["contentDetails"]["relatedPlaylists"]["uploads"], maxResults=50).execute().get("items", [])]
    recent = []
    if ids:
        for v in yt.videos().list(part="snippet,statistics,contentDetails", id=",".join(ids)).execute().get("items", []):
            recent.append({"id": v["id"], "title": v["snippet"]["title"], "views": int(v["statistics"].get("viewCount", 0)),
                           "seconds": trendwatch.iso_seconds(v["contentDetails"]["duration"]), "published": v["snippet"]["publishedAt"]})
    snap = {"date": now.strftime("%Y-%m-%d"), "channel_id": c["id"], "title": c["snippet"]["title"],
            "subscribers": 0 if s.get("hiddenSubscriberCount") else int(s.get("subscriberCount", 0)),
            "views": int(s.get("viewCount", 0)), "videos": int(s.get("videoCount", 0)), "recent": recent}
    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / f"{snap['date']}.json").write_text(json.dumps(snap, indent=2))
    return snap


def load_snapshots(n: int = 30) -> list[dict]:
    files = sorted(DIR.glob("*.json")) if DIR.exists() else []
    return [json.loads(f.read_text()) for f in files[-n:]]


def _median(xs: list[int]) -> float:
    return statistics.median(xs) if xs else 0


def analyze(snaps: list[dict], study: list[dict]) -> dict:
    out = {"subs": 0, "subs_delta_7d": 0, "views_delta_7d": 0, "uploads_per_week": 0, "shorts_median_views": 0,
           "long_median_views": 0, "best": [], "competitor_median_views": 0, "gap_ratio": 0}
    if snaps:
        last = snaps[-1]
        day = dt.date.fromisoformat(last["date"])
        window = [s for s in snaps if (day - dt.date.fromisoformat(s["date"])).days <= 7]
        base = window[0]
        out.update(subs=last["subscribers"], subs_delta_7d=last["subscribers"] - base["subscribers"],
                   views_delta_7d=last["views"] - base["views"])
        recent = last.get("recent", [])
        since = (dt.datetime.combine(day, dt.time(), dt.timezone.utc) - dt.timedelta(days=28)).strftime("%Y-%m-%dT%H:%M:%SZ")
        out["uploads_per_week"] = round(sum(1 for v in recent if v["published"] >= since) / 4, 2)
        out["shorts_median_views"] = _median([v["views"] for v in recent if v["seconds"] <= 60])
        out["long_median_views"] = _median([v["views"] for v in recent if v["seconds"] > 60])
        out["best"] = sorted(recent, key=lambda v: -v["views"])[:3]
        ours = _median([v["views"] for v in recent])
        comp = _median([c["summary"]["median_views"] for c in study if c.get("summary", {}).get("median_views", 0) > 0])
        out["competitor_median_views"] = comp
        out["gap_ratio"] = round(ours / comp, 4) if comp else 0
    return out
