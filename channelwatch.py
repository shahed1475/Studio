"""Reference-channel breakdown through the official YouTube API: which topics already work in the niche.

Reads public metadata only (titles, views, lengths). Ideas that come back are proposals in our own words,
built from public-domain legends or documented history; a person decides what enters the queue.
"""
import datetime as dt
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import config
import scriptgen
import trendwatch

REF_FILE = config.ROOT / "reference_channels.json"
DATA_DIR = config.ROOT / "data" / "channels"
MAX_REFS = 5
HANDLE = re.compile(r"^@[A-Za-z0-9._-]{3,30}$")
CHANNEL_ID = re.compile(r"^UC[A-Za-z0-9_-]{22}$")


def parse_ref(ref: str) -> dict:
    ref = (ref or "").strip()
    if CHANNEL_ID.match(ref):
        return {"id": ref}
    if HANDLE.match(ref):
        return {"handle": ref}
    u = urlparse(ref)
    if u.scheme in ("http", "https") and u.hostname in ("youtube.com", "www.youtube.com", "m.youtube.com"):
        parts = [p for p in u.path.split("/") if p]
        if parts and HANDLE.match(parts[0]):
            return {"handle": parts[0]}
        if len(parts) >= 2 and parts[0] == "channel" and CHANNEL_ID.match(parts[1]):
            return {"id": parts[1]}
    raise ValueError("paste a channel like @name, a youtube.com/@name link, or a channel ID that starts with UC")


def _key(ref: str) -> str:
    p = parse_ref(ref)
    return p.get("handle") or p["id"]


def load_refs() -> list[str]:
    return json.loads(REF_FILE.read_text()) if REF_FILE.exists() else []


def add_ref(ref: str) -> None:
    key = _key(ref)
    refs = load_refs()
    if key.lower() in (r.lower() for r in refs):
        return
    if len(refs) >= MAX_REFS:
        raise ValueError(f"at most {MAX_REFS} reference channels: remove one first")
    REF_FILE.write_text(json.dumps(refs + [key], indent=2))


def remove_ref(ref: str) -> None:
    key = _key(ref)
    REF_FILE.write_text(json.dumps([r for r in load_refs() if r.lower() != key.lower()], indent=2))


def resolve(yt, ref: str) -> dict:
    p = parse_ref(ref)
    kw = {"forHandle": p["handle"]} if "handle" in p else {"id": p["id"]}
    items = yt.channels().list(part="snippet,contentDetails", **kw).execute().get("items", [])
    if not items:
        raise ValueError(f"no channel found for {ref}")
    c = items[0]
    return {"id": c["id"], "title": c["snippet"]["title"], "uploads": c["contentDetails"]["relatedPlaylists"]["uploads"]}


def breakdown(yt, ref: str, scan: int = 50) -> dict:
    ch = resolve(yt, ref)
    ids = [i["contentDetails"]["videoId"] for i in
           yt.playlistItems().list(part="contentDetails", playlistId=ch["uploads"], maxResults=scan).execute().get("items", [])]
    vids = []
    for v in yt.videos().list(part="snippet,statistics,contentDetails", id=",".join(ids)).execute().get("items", []) if ids else []:
        vids.append({"id": v["id"], "title": v["snippet"]["title"], "channel": v["snippet"]["channelTitle"], "channel_id": v["snippet"]["channelId"],
                     "views": int(v["statistics"].get("viewCount", 0)), "seconds": trendwatch.iso_seconds(v["contentDetails"]["duration"]),
                     "published": v["snippet"]["publishedAt"], "url": f"https://www.youtube.com/watch?v={v['id']}"})
    vids.sort(key=lambda x: -x["views"])
    return {"channel": ch["title"], "channel_id": ch["id"], "top": vids[:5], "summary": trendwatch.summarize_videos(vids), "scanned": len(vids)}


def suggest(trends: dict | None) -> list[dict]:
    """Channels that keep showing up in the weekly niche search: good candidates to study."""
    seen: dict[str, dict] = {}
    for v in (trends or {}).get("videos", []):
        if not v.get("channel_id"):
            continue
        s = seen.setdefault(v["channel_id"], {"channel_id": v["channel_id"], "channel": v["channel"], "count": 0, "top_views": 0})
        s["count"] += 1
        s["top_views"] = max(s["top_views"], v["views"])
    return sorted((s for s in seen.values() if s["count"] >= 2), key=lambda s: -s["top_views"])


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def run(now: dt.datetime | None = None, yt=None) -> Path:
    now = now or dt.datetime.now(dt.timezone.utc)
    y, w, _ = now.isocalendar()
    path = DATA_DIR / f"{y}-W{w:02d}.json"
    if path.exists():
        old = json.loads(path.read_text())
        if old.get("generated_at", "")[:10] == now.strftime("%Y-%m-%d") and (old.get("channels") or not load_refs()):
            return path  # once a day at most; an empty digest made before any channel was added is redone
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    digest = {"week": f"{y}-W{w:02d}", "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "channels": [], "ideas": []}
    refs = load_refs()
    if not refs:
        digest["note"] = "no reference channels yet: add 3 to 5 channels you want to study"
    else:
        yt = yt or trendwatch._service()
        for ref in refs:
            try:
                digest["channels"].append(breakdown(yt, ref))
            except Exception as e:  # one bad channel must not stop the rest
                digest["channels"].append({"channel": ref, "top": [], "error": f"{type(e).__name__}: {e}"})
        top = [v for c in digest["channels"] for v in c.get("top", [])]
        if top:
            try:
                got = scriptgen._chat(
                    "You plan original YouTube videos for a calm storytelling channel (legends, mysteries, strange true history) for US "
                    "viewers. These titles from other channels only show which themes already work. Never reuse their wording, structure "
                    "or script.\n" + "\n".join(f"- {v['title']}" for v in top[:15]) +
                    "\n\nSuggest 5 different topics built from public-domain legends or well-documented history, each with its own angle "
                    'and fresh wording. Return JSON: {"topics": ["..."]}')
                scraped = {_norm(v["title"]) for v in top}
                digest["ideas"] = [t.strip() for t in got.get("topics", []) if isinstance(t, str) and t.strip() and _norm(t) not in scraped]
            except Exception as e:
                digest["ideas_error"] = f"{type(e).__name__}: {e}"
    path.write_text(json.dumps(digest, indent=2))
    return path


def latest() -> dict | None:
    files = sorted(DATA_DIR.glob("*.json")) if DATA_DIR.exists() else []
    return json.loads(files[-1].read_text()) if files else None
