"""Finds competitor channels in our niche through the official YouTube Data API (public numbers only)."""
import datetime as dt
import json

import agentlog
import channelwatch
import config
import scriptgen

FILE = config.ROOT / "data" / "agent" / "discovered.json"
MAX_FOUND = 15
MAX_SEARCHES = 6  # 100 quota units each
SEEDS = ["folklore legends retold", "unsolved mysteries history documentary", "history stories for sleep",
         "bedtime stories mythology", "dark history true stories", "ancient legends explained"]


def score(c: dict) -> float:
    """Views per video; channels under 10,000 subscribers do not count as competitors yet."""
    if c.get("subscribers", 0) < 10000:
        return 0
    return c.get("views", 0) / max(c.get("videos", 0), 1)


def search(yt, seeds: list[str], exclude: set[str]) -> list[dict]:
    ids: list[str] = []
    for q in seeds[:MAX_SEARCHES]:
        res = yt.search().list(q=q, part="id", type="channel", maxResults=10, order="viewCount",
                               regionCode="US", relevanceLanguage="en").execute()
        for i in res.get("items", []):
            cid = i["id"]["channelId"]
            if cid not in exclude and cid not in ids:
                ids.append(cid)
    found, today = [], dt.date.today().isoformat()
    for k in range(0, len(ids), 50):
        for c in yt.channels().list(part="snippet,statistics", id=",".join(ids[k:k + 50])).execute().get("items", []):
            s = c.get("statistics", {})
            row = {"id": c["id"], "title": c["snippet"]["title"], "subscribers": int(s.get("subscriberCount", 0)),
                   "views": int(s.get("viewCount", 0)), "videos": int(s.get("videoCount", 0)), "found": today}
            row["score"] = round(score(row), 1)
            if row["score"] > 0:
                found.append(row)
    return found


def fit_niche(candidates: list[dict], chat) -> list[dict]:
    """One model call: keep channels that really tell stories in our niche. A model failure keeps everyone, marked unchecked."""
    if not candidates:
        return []
    nc = config.niche()
    listing = "\n".join(f"- {c['id']}: {c['title']}" for c in candidates)
    try:
        got = chat(f"Our channel: {nc['channel_angle']}\nWhich of these YouTube channels make similar story, mystery, folklore or history "
                   f'videos for the same kind of viewer? Reply JSON {{"fits": ["channel id", ...]}}\n{listing}')
        fits = {i for i in got.get("fits", []) if isinstance(i, str)}
        return [c for c in candidates if c["id"] in fits]
    except Exception:
        return [{**c, "unchecked": True} for c in candidates]


def load() -> list[dict]:
    return json.loads(FILE.read_text()) if FILE.exists() else []


def _ref_ids(yt, refs: list[str]) -> set[str]:
    out = set()
    for r in refs:
        if channelwatch.CHANNEL_ID.match(r):
            out.add(r)
            continue
        try:
            out.add(channelwatch.resolve(yt, r)["id"])
        except Exception:
            pass  # an unresolvable handle just cannot be excluded
    return out


def run(yt, own_id: str, refs: list[str], chat=None) -> list[dict]:
    """Search, filter, merge into the saved list (best MAX_FOUND by score). Returns only channels not seen before."""
    chat = chat or scriptgen._chat
    known = load()
    known_ids = {c["id"] for c in known}
    exclude = {own_id} | _ref_ids(yt, refs) | known_ids
    fresh = fit_niche(search(yt, SEEDS, exclude), chat)
    merged = sorted(known + fresh, key=lambda c: -c["score"])[:MAX_FOUND]
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(merged, indent=2))
    kept = {c["id"] for c in merged}
    new = [c for c in fresh if c["id"] in kept]
    for c in new:
        agentlog.event("found", f"New competitor: {c['title']}", f"{c['subscribers']:,} subscribers, {c['score']:,.0f} views per video")
    return new
