"""Title test agent: after a video has been public for two days, compare its views per day with the channel's other videos of the same kind.
A clearly weak video gets one new title (from fixer.pick_title). Five days later the agent compares views per day before and after the change and
puts the old title back if the new one did worse.

Only views are measured (YouTube Data API). Click-through rate needs the YouTube Analytics permission, which is not connected, so a weak title is
a suspicion, not a proof. Default mode is "suggest": the new title is written down and reported. Mode "apply" changes it on YouTube, and that needs
the token to hold the `youtube` permission (a one-time reconnect). One change per video, one change per day, never a video younger than two days.
"""
import datetime as dt
import json
import statistics
from pathlib import Path

import agentlog
import config
import records
import fixer

TS = "%Y-%m-%dT%H:%M:%SZ"
MIN_AGE = dt.timedelta(hours=48)
RECHECK_AFTER = dt.timedelta(days=5)
MIN_PEERS = 3            # no judgement without three other videos of the same kind to compare with
WEAK_RATIO = 0.4         # below 40% of the median views per day counts as weak
WORSE_RATIO = 0.8        # after the change, below 80% of the old rate: put the old title back
LOW_RETENTION = 25.0     # viewers who find the video watch under a quarter of it on average: the content, not the title, is what needs work
WRITE_SCOPES = {"https://www.googleapis.com/auth/youtube", "https://www.googleapis.com/auth/youtube.force-ssl"}
CONFIG = config.ROOT / "data" / "titletest.json"


def mode() -> str:
    try:
        return "apply" if json.loads(CONFIG.read_text()).get("mode") == "apply" else "suggest"
    except (OSError, ValueError):
        return "suggest"


def _parse(ts: str) -> dt.datetime:
    return dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))


def per_day(views: int, published: dt.datetime, now: dt.datetime) -> float:
    return views / max((now - published).total_seconds() / 86400, 1.0)


def judge(rate: float, peer_rates: list[float]) -> str:
    """'learning' with too few peers, 'weak' when clearly below the channel's median, otherwise 'ok'."""
    if len(peer_rates) < MIN_PEERS:
        return "learning"
    return "weak" if rate < statistics.median(peer_rates) * WEAK_RATIO else "ok"


def can_write(token: Path | None = None) -> bool:
    try:
        return bool(WRITE_SCOPES & set(json.loads((token or config.ROOT / "token.json").read_text()).get("scopes", [])))
    except (OSError, ValueError):
        return False


def _service():
    import trendwatch

    return trendwatch._service()


def watch_quality(now: dt.datetime | None = None) -> dict[str, float]:
    """{video id: average percent of the video watched} from YouTube Analytics (needs the read-only analytics permission and the Analytics API
    enabled). Any failure gives {}: the title test then judges by views alone, as before."""
    try:
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        import upload

        creds = upload.load_creds()
        if not creds.valid:
            creds.refresh(Request())
        end = (now or dt.datetime.now(dt.timezone.utc)).date()
        r = build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False).reports().query(
            ids="channel==MINE", startDate=str(end - dt.timedelta(days=90)), endDate=str(end), metrics="views,averageViewPercentage",
            dimensions="video", sort="-views", maxResults=200).execute()
        return {row[0]: float(row[2]) for row in r.get("rows", []) if int(row[1]) >= 3}  # under 3 views is noise
    except Exception:
        return {}


def _stats(yt, ids: list[str]) -> dict[str, dict]:
    out = {}
    for k in range(0, len(ids), 50):
        for v in yt.videos().list(part="snippet,statistics,status,contentDetails", id=",".join(ids[k:k + 50])).execute().get("items", []):
            out[v["id"]] = v
    return out


def set_title(yt, video: dict, title: str) -> None:
    """videos.update replaces the whole snippet, so send back everything that was there with only the title changed."""
    sn = dict(video["snippet"])
    sn["title"] = title
    yt.videos().update(part="snippet", body={"id": video["id"], "snippet": {k: sn[k] for k in ("title", "description", "categoryId", "tags", "defaultLanguage") if k in sn}}).execute()
    import actionlog

    actionlog.record(video["id"], {"title": video["snippet"]["title"]}, {"title": title}, "title test", "the title test changed or restored a title (owner's apply mode)")


def _kind(meta: dict) -> str:
    return "short" if meta.get("format", "short") == "short" else "long"


def run(now: dt.datetime | None = None, yt=None, pick=None, quality=None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    pick = pick or fixer.pick_title
    quality = quality or {}
    metas = []
    for m in sorted(config.OUT.glob("*/meta.json")):
        try:
            meta = json.loads(m.read_text())
        except ValueError:
            continue
        if meta.get("video_id") and meta.get("publish_at") and _parse(meta["publish_at"]) <= now - MIN_AGE:
            metas.append((m, meta))
    res = {"checked": 0, "weak": [], "changed": [], "reverted": [], "kept": [], "learning": 0, "content": []}
    if not metas:
        return res
    yt = yt or _service()
    found = _stats(yt, [m[1]["video_id"] for m in metas])
    rates = {}
    for path, meta in metas:
        v = found.get(meta["video_id"])
        if v and v["status"].get("privacyStatus") == "public":
            rates[meta["video_id"]] = per_day(int(v["statistics"].get("viewCount", 0)), _parse(meta["publish_at"]), now)
    write = mode() == "apply" and can_write()
    changed_today = any(_parse(mm.get("title_test", {}).get("changed_at", "2000-01-01T00:00:00Z")) > now - dt.timedelta(days=1) for _, mm in metas)
    for path, meta in metas:
        vid, tt = meta["video_id"], meta.get("title_test") or {}
        if vid not in rates:
            continue
        res["checked"] += 1
        if tt.get("changed_at") and not tt.get("verdict"):  # a change is waiting for its second look
            if _parse(tt["changed_at"]) > now - RECHECK_AFTER:
                continue
            views = int(found[vid]["statistics"].get("viewCount", 0))
            days = (now - _parse(tt["changed_at"])).total_seconds() / 86400
            after = (views - tt["views_at_change"]) / max(days, 1.0)
            if after < tt["rate_before"] * WORSE_RATIO:
                if write and tt.get("applied"):
                    set_title(yt, found[vid], tt["original"])
                    meta["title"] = tt["original"]
                tt["verdict"] = "reverted" if tt.get("applied") else "worse"
                res["reverted"].append(path.parent.name)
                agentlog.event("applied", f"Title test: the new title did worse ({tt['original'][:40]}...)",
                               f"{after:.1f} views/day after, {tt['rate_before']:.1f} before. " + ("The old title is back." if tt.get("applied") else "The old title was never replaced."), now=now)
            else:
                tt["verdict"] = "kept"
                res["kept"].append(path.parent.name)
            meta["title_test"] = tt
            records.merge(path.parent, {"title_test": tt, **({"title": meta["title"]} if write and tt.get("verdict") == "reverted" and tt.get("applied") else {})})
            continue
        if tt:  # already tested once: never a second change
            continue
        peers = [r for k, (pp, mm) in ((x[1]["video_id"], x) for x in metas) for r in [rates.get(k)] if r is not None and mm is not meta and _kind(mm) == _kind(meta)]
        verdict = judge(rates[vid], peers)
        if verdict == "learning":
            res["learning"] += 1
            continue
        if verdict == "ok":
            meta["title_test"] = {"verdict": "fine", "checked_at": now.strftime(TS), "rate": round(rates[vid], 2)}
            records.merge(path.parent, {"title_test": meta["title_test"]})
            continue
        pct = quality.get(vid)
        if pct is not None and pct < LOW_RETENTION:  # people who do find it leave early: a new title would only bring more people who leave
            meta["title_test"] = {"verdict": "content", "checked_at": now.strftime(TS), "rate": round(rates[vid], 2), "watched_percent": round(pct, 1)}
            records.merge(path.parent, {"title_test": meta["title_test"]})
            res["content"].append(path.parent.name)
            agentlog.event("found", f"Title test: {meta['title'][:50]} is watched only {pct:.0f}% through",
                           "Few views and viewers leave early, so the title is not the problem: look at its opening and pacing. The title was not changed.", now=now)
            continue
        new = pick(meta, fixer.other_titles(path.parent))
        if not new:
            continue
        import seo

        core = (meta.get("seo") or {}).get("core", "")
        new = seo.ensure_title_front(new, core) if core else new  # a test title must keep the words people search for
        views = int(found[vid]["statistics"].get("viewCount", 0))
        apply_now = write and not changed_today
        tt = {"original": meta["title"], "proposed": new, "changed_at": now.strftime(TS), "views_at_change": views, "rate_before": round(rates[vid], 2), "applied": apply_now}
        if apply_now:
            set_title(yt, found[vid], new)
            meta["title"] = new
            changed_today = True
            res["changed"].append(path.parent.name)
        else:
            res["weak"].append(path.parent.name)
        meta["title_test"] = tt
        records.merge(path.parent, {"title_test": tt, **({"title": new} if apply_now else {})})
        agentlog.event("applied" if apply_now else "found", f"Title test: {'changed' if apply_now else 'suggest changing'} the title of a weak video",
                       f"{tt['original']} -> {new}. It gets {tt['rate_before']} views/day, the channel median for this kind is {statistics.median(peers):.1f}."
                       + ("" if apply_now else " Not changed on YouTube (suggest mode" + ("" if can_write() else ", no permission to edit titles yet") + ")."), now=now)
    return res
