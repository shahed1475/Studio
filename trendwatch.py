"""Niche trend research through the official YouTube Data API. Reads public metadata only; never copies a video or its text."""
import datetime as dt
import json
import re
import statistics
from pathlib import Path

import config
import scriptgen

DATA_DIR = config.ROOT / "data" / "trends"
SEEDS = ["history stories for sleep", "unsolved mysteries history documentary", "folklore legends explained", "medieval legends true story"]
PATTERNS = {
    "question": re.compile(r"\?"),
    "real_story": re.compile(r"\b(real story|true story|really happened|what happened)\b", re.I),
    "number": re.compile(r"\d"),
    "colon": re.compile(r":"),
}


def iso_seconds(duration: str) -> int:
    m = re.fullmatch(r"P(?:\d+D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration or "")
    if not m:
        return 0
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s


def summarize_videos(items: list[dict]) -> dict:
    views = [i["views"] for i in items]
    long_ = [i["seconds"] for i in items if i["seconds"] > 60]
    return {
        "median_views": int(statistics.median(views)) if views else 0,
        "short_share": (sum(1 for i in items if i["seconds"] <= 60) / len(items)) if items else 0,
        "avg_minutes": round(statistics.mean(long_) / 60, 1) if long_ else 0,
        "patterns": {k: sum(1 for i in items if rx.search(i["title"])) for k, rx in PATTERNS.items()},
    }


def _service():
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    import upload

    creds = upload.load_creds()
    if not creds.valid:
        creds.refresh(Request())
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def search_niche(queries: list[str], yt=None) -> list[dict]:
    yt = yt or _service()
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ids: list[str] = []
    for q in queries[:6]:  # 100 quota units each
        res = yt.search().list(q=q, part="id", type="video", maxResults=8, order="viewCount", regionCode="US",
                               relevanceLanguage="en", publishedAfter=since).execute()
        ids += [i["id"]["videoId"] for i in res.get("items", []) if i["id"]["videoId"] not in ids]
    out = []
    for k in range(0, len(ids), 50):
        for v in yt.videos().list(part="snippet,statistics,contentDetails", id=",".join(ids[k:k + 50])).execute().get("items", []):
            out.append({"id": v["id"], "title": v["snippet"]["title"], "channel": v["snippet"]["channelTitle"], "channel_id": v["snippet"]["channelId"],
                        "views": int(v["statistics"].get("viewCount", 0)), "seconds": iso_seconds(v["contentDetails"]["duration"]),
                        "published": v["snippet"]["publishedAt"], "url": f"https://www.youtube.com/watch?v={v['id']}"})
    return sorted(out, key=lambda x: -x["views"])


FRESH_DAYS = 14        # "trending" means taking off now, not popular for years
FRESH_SEARCHES = 4     # 100 quota units each, shared by the documentary and Short searches, once a day
HINT_MAX_DOC = 45 * 60  # the niche has two-to-three-hour sleep videos; they are a different format and would make the hint meaningless
MIN_SUBS, UNKNOWN_SUBS = 500, 50_000  # a tiny channel counts as 500 (one lucky video must not explode the score); a hidden subscriber count as a mid-size channel


def outlier_score(views: int, subs: int | None, age_days: float) -> float:
    """Views per day divided by the channel's size: how far a video beats what its channel normally gets. About 1 is ordinary, 5 or more is taking off."""
    return round((views / max(age_days, 1)) / max(subs if subs is not None else UNKNOWN_SUBS, MIN_SUBS), 3)


def search_fresh(queries: list[str], yt=None, now: dt.datetime | None = None, days: int = FRESH_DAYS, kind: str = "doc") -> list[dict]:
    """Videos on the niche's themes published in the last `days`, best outlier score first. kind "doc": at least 4 minutes; "short": 90 seconds or less.
    Reads public numbers only (API: search 100 units, videos and channels 1 unit per 50)."""
    yt, now = yt or _service(), now or dt.datetime.now(dt.timezone.utc)
    since = (now - dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ids: list[str] = []
    for q in queries[:FRESH_SEARCHES]:
        extra = {"videoDuration": "short"} if kind == "short" else {}
        res = yt.search().list(q=q, part="id", type="video", maxResults=15, order="viewCount", regionCode="US", relevanceLanguage="en", publishedAfter=since, **extra).execute()
        ids += [i["id"]["videoId"] for i in res.get("items", []) if i["id"]["videoId"] not in ids]
    found = []
    for k in range(0, len(ids), 50):
        for v in yt.videos().list(part="snippet,statistics,contentDetails", id=",".join(ids[k:k + 50])).execute().get("items", []):
            secs = iso_seconds(v["contentDetails"]["duration"])
            if (kind == "short" and not 0 < secs <= 90) or (kind != "short" and secs < 240):
                continue
            age = (now - dt.datetime.fromisoformat(v["snippet"]["publishedAt"].replace("Z", "+00:00"))).total_seconds() / 86400
            if age > days:
                continue
            found.append({"id": v["id"], "title": v["snippet"]["title"], "channel": v["snippet"]["channelTitle"], "channel_id": v["snippet"]["channelId"], "seconds": secs,
                          "views": int(v["statistics"].get("viewCount", 0)), "age_days": round(age, 1), "url": f"https://www.youtube.com/watch?v={v['id']}"})
    subs: dict[str, int | None] = {}
    chans = sorted({f["channel_id"] for f in found})
    for k in range(0, len(chans), 50):
        for c in yt.channels().list(part="statistics", id=",".join(chans[k:k + 50])).execute().get("items", []):
            st = c.get("statistics", {})
            subs[c["id"]] = None if st.get("hiddenSubscriberCount") else int(st.get("subscriberCount", 0))
    for f in found:
        f["subs"] = subs.get(f["channel_id"])
        f["score"] = outlier_score(f["views"], f["subs"], f["age_days"])
    return sorted(found, key=lambda f: -f["score"])[:12]


def fresh_hint(fresh: dict) -> dict:
    """The typical length of what is taking off now (the top few of each kind; documentaries over 45 minutes left out): a hint for the writer, not a rule."""
    mid = lambda xs: int(statistics.median(xs)) if xs else 0
    return {"doc_minutes": round(mid([f["seconds"] for f in fresh.get("docs", [])[:8] if f["seconds"] <= HINT_MAX_DOC]) / 60, 1), "short_seconds": mid([f["seconds"] for f in fresh.get("shorts", [])[:5]])}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def run(now: dt.datetime | None = None, yt=None) -> Path:
    now = now or dt.datetime.now(dt.timezone.utc)
    y, w, _ = now.isocalendar()
    path = DATA_DIR / f"{y}-W{w:02d}.json"
    if path.exists() and json.loads(path.read_text()).get("generated_at", "")[:10] == now.strftime("%Y-%m-%d"):
        return path  # once a day at most: every search costs API quota
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    queue = json.loads(config.TOPICS_FILE.read_text()) if config.TOPICS_FILE.exists() else []
    digest = {"week": f"{y}-W{w:02d}", "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "videos": [], "ideas": []}
    try:
        videos = search_niche(config.search_seeds(SEEDS) + queue[:2], yt)
        digest["videos"] = videos[:25]
        digest["summary"] = summarize_videos(videos)
        got = scriptgen._chat(
            f"You plan original YouTube videos for {config.channel_blurb()} "
            "for US viewers. These titles from other channels only show which themes are popular. Never reuse their wording "
            "or structure.\n" + "\n".join(f"- {v['title']}" for v in videos[:15]) +
            f"\n\nSuggest 5 different topics {config.topic_kinds()}, each with its own "
            'angle and fresh wording. Return JSON: {"topics": ["..."]}')
        scraped = {_norm(v["title"]) for v in videos}
        new = [t.strip() for t in got.get("topics", []) if isinstance(t, str) and t.strip() and _norm(t) not in scraped and t not in queue]
        digest["ideas"] = new  # proposals only: the model can get facts wrong, so a person decides what enters the queue
    except Exception as e:  # quota, missing token, model down: record it and stop cleanly
        digest["error"] = f"{type(e).__name__}: {e}"
        digest.setdefault("summary", summarize_videos([]))
    try:  # what is taking off now: one search budget a day, and a failure here never loses the digest above
        seeds = config.search_seeds(SEEDS)
        half = max(1, FRESH_SEARCHES // 2)
        fresh = {"docs": search_fresh(seeds[:half], yt, now, kind="doc"), "shorts": search_fresh(seeds[:half], yt, now, kind="short")}
        fresh["hint"] = fresh_hint(fresh)
        digest["fresh"] = fresh
    except Exception as e:
        digest["fresh"] = {"docs": [], "shorts": [], "hint": {}, "error": f"{type(e).__name__}: {e}"}
    path.write_text(json.dumps(digest, indent=2))
    return path


def latest() -> dict | None:
    files = sorted(DATA_DIR.glob("*.json")) if DATA_DIR.exists() else []
    return json.loads(files[-1].read_text()) if files else None
