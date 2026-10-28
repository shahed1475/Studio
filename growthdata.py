"""Collector: the channel's own per-video numbers from YouTube's official APIs, one file, every number with its source.

- Analytics API (read-only): views, average percent viewed, minutes watched, subscribers gained, the retention curve (retention at 30 s) and traffic sources.
- Reporting API reach reports: thumbnail impressions and click-through rate (the Analytics API has neither; checked 28 Oct 2026). Needs the "YouTube
  Reporting API" enabled in the Google Cloud project; until it is, ctr stays null with the reason. A number that could not be read is never filled in.
- Not available from any API we can reach: unique viewers (the Analytics API answered "Unknown identifier"), so views per unique viewer is not computed.
A video under 7 days old is collected every 6 hours, an older one once a day. This module only reads; it writes nothing to YouTube."""
import csv
import datetime as dt
import io
import json
from pathlib import Path

import config
import filelock
import growth

FILE = config.ROOT / "data" / "agent" / "metrics" / "videos.json"  # not under data/agent/own/: growth.load_snapshots reads every .json there
REACH_TYPE = "channel_reach_basic_a1"
FRESH_HOURS, OLD_HOURS, FRESH_DAYS = 6, 24, 7
UNAVAILABLE = {"views_per_unique": "no unique-viewers metric in the Analytics API (checked 28 Oct 2026)"}


def _iso(now: dt.datetime) -> str:
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(ts: str) -> dt.datetime:
    return dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))


def retention_at(rows: list, seconds: float, duration: float) -> float | None:
    """The audience watch ratio, in percent, at `seconds` into a video of `duration` seconds (the curve has 100 points). None when it cannot be read."""
    if not rows or not duration or duration <= 0:
        return None
    pos = min(seconds / duration, 1.0)
    point = min(rows, key=lambda r: abs(float(r[0]) - pos))
    return round(float(point[1]) * 100, 1)


def parse_reach_csv(text: str) -> dict[str, dict[str, dict]]:
    """{video id: {YYYY-MM-DD: {impressions, ctr}}} from a reach report. ctr is a fraction: a column whose values go above 1 is read as percent."""
    rows = list(csv.DictReader(io.StringIO(text or "")))
    need = ("video_id", "video_thumbnail_impressions", "video_thumbnail_impressions_ctr")
    if not rows or any(k not in rows[0] for k in need):
        return {}
    pct = max((float(r[need[2]] or 0) for r in rows), default=0) > 1
    out: dict = {}
    for r in rows:
        try:
            imp, ctr = int(float(r[need[1]] or 0)), float(r[need[2]] or 0) / (100 if pct else 1)
        except ValueError:
            continue
        day = str(r.get("date", ""))
        day = f"{day[:4]}-{day[4:6]}-{day[6:8]}" if len(day) == 8 and day.isdigit() else day
        cell = out.setdefault(r["video_id"], {}).setdefault(day, {"impressions": 0, "clicks": 0.0})
        cell["impressions"] += imp
        cell["clicks"] += imp * ctr
    return {v: {d: {"impressions": c["impressions"], "ctr": round(c["clicks"] / c["impressions"], 5) if c["impressions"] else None} for d, c in days.items()}
            for v, days in out.items()}


def due(entry: dict | None, published: str, now: dt.datetime) -> bool:
    if not entry or not entry.get("collected"):
        return True
    young = (now - _parse(published)).days < FRESH_DAYS
    return now - _parse(entry["collected"]) >= dt.timedelta(hours=FRESH_HOURS if young else OLD_HOURS)


def load(path: Path | None = None) -> dict:
    try:
        d = json.loads(Path(path or FILE).read_text())
        return d if isinstance(d, dict) and isinstance(d.get("videos"), dict) else {"videos": {}}
    except (OSError, ValueError):
        return {"videos": {}}


def clients():
    """(youtube data, analytics, reporting, authorised session) from the saved login; reporting may be None when its API cannot be built."""
    from google.auth.transport.requests import AuthorizedSession, Request
    from googleapiclient.discovery import build

    import upload

    creds = upload.load_creds()
    if not creds.valid:
        creds.refresh(Request())
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    an = build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)
    rp = build("youtubereporting", "v1", credentials=creds, cache_discovery=False)
    return yt, an, rp, AuthorizedSession(creds)


def fetch_reach(rp, session, store: dict) -> tuple[dict, str | None]:
    """Make sure a reach-report job exists (a read-only job on Google's side), then read the reports not yet seen. (per-video days, problem or None)."""
    try:
        jobs = rp.jobs().list().execute().get("jobs", [])
        job = next((j for j in jobs if j.get("reportTypeId") == REACH_TYPE), None)
        if not job:
            job = rp.jobs().create(body={"reportTypeId": REACH_TYPE, "name": "studio reach (thumbnail impressions and click rate)"}).execute()
        seen = set(store.get("reach_reports_seen", []))
        days: dict = {}
        for rep in rp.jobs().reports().list(jobId=job["id"]).execute().get("reports", []):
            if rep["id"] in seen:
                continue
            resp = session.get(rep["downloadUrl"], timeout=60)
            resp.raise_for_status()
            for vid, d in parse_reach_csv(resp.text).items():
                days.setdefault(vid, {}).update(d)
            seen.add(rep["id"])
        store["reach_reports_seen"] = sorted(seen)[-200:]
        return days, None
    except Exception as e:  # not enabled (403), no report yet, a network error: ctr stays null
        return {}, f"reach reports unavailable: {type(e).__name__}: {str(e)[:160]}"


DAILY = config.ROOT / "data" / "agent" / "metrics" / "daily.json"


def fetch_daily(an, now: dt.datetime, base: dict, video_ids: list[str], path: Path | None = None, every_hours: int = 20) -> bool:
    """Daily views per video (one filtered query each: the API does not support the day and video dimensions together, checked 28 Oct 2026) and per traffic source
    for the last 90 days, kept for the drift detector. At most once every `every_hours`. `path` is the metrics file's path when a test passes one: the daily
    file then sits beside it."""
    target = (Path(path).with_name("daily.json") if path else DAILY)
    try:
        old = json.loads(target.read_text())
        if now - _parse(old["updated"]) < dt.timedelta(hours=every_hours):
            return False
    except (OSError, ValueError, KeyError):
        pass
    vids, traffic = {}, {}
    for vid in video_ids[:50]:
        rows = an.reports().query(metrics="views", dimensions="day", filters=f"video=={vid}", sort="day", **base).execute().get("rows", [])
        vids[vid] = {day: int(views) for day, views in rows}
    for day, src, views in an.reports().query(metrics="views", dimensions="day,insightTrafficSourceType", maxResults=10000, **base).execute().get("rows", []):
        traffic.setdefault(day, {})[src] = int(views)
    target.parent.mkdir(parents=True, exist_ok=True)
    filelock.write_atomic(target, json.dumps({"updated": _iso(now), "videos": vids, "traffic": traffic}))
    return True


def collect(now: dt.datetime | None = None, cl=None, path: Path | None = None, list_videos=None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    yt, an, rp, session = cl or clients()
    store = load(path)
    videos = (list_videos or (lambda: growth.snapshot(yt, now)["recent"]))()
    problems, collected = [], 0
    end = now.date()
    base = dict(ids="channel==MINE", startDate=str(end - dt.timedelta(days=90)), endDate=str(end))
    try:
        rows = an.reports().query(metrics="views,averageViewPercentage,estimatedMinutesWatched,subscribersGained", dimensions="video", sort="-views", maxResults=200, **base).execute().get("rows", [])
        totals = {r[0]: r for r in rows}
    except Exception as e:
        totals = {}
        problems.append(f"analytics totals unavailable: {type(e).__name__}: {str(e)[:160]}")
    for v in videos:
        prev = store["videos"].get(v["id"])
        if not due(prev, v["published"], now):
            continue
        entry = {"title": str(v["title"])[:120], "published": v["published"], "seconds": v["seconds"], "kind": "doc" if v["seconds"] > 180 else "short",
                 "daily_views_total": v.get("views"), **{k: None for k in ("views_90d", "avg_pct_viewed", "minutes_90d", "subs_gained_90d", "retention_at_30s", "traffic")}}
        sources = {}
        t = totals.get(v["id"])
        if t:
            entry.update(views_90d=int(t[1]), avg_pct_viewed=round(float(t[2]), 1), minutes_90d=int(t[3]), subs_gained_90d=int(t[4]))
            entry["subs_per_1k_views"] = round(1000 * int(t[4]) / int(t[1]), 2) if int(t[1]) else None
            sources["analytics"] = f"Analytics API {now.date()}"
        try:
            curve = an.reports().query(metrics="audienceWatchRatio", dimensions="elapsedVideoTimeRatio", filters=f"video=={v['id']}", **base).execute().get("rows", [])
            entry["retention_at_30s"] = retention_at(curve, 30, v["seconds"])
            entry["retention_curve"] = [[float(r[0]), round(float(r[1]), 4)] for r in curve][:100]
            sources["retention"] = f"Analytics API {now.date()}"
        except Exception as e:
            problems.append(f"{v['id']} retention: {type(e).__name__}")
        try:
            tr = an.reports().query(metrics="views", dimensions="insightTrafficSourceType", filters=f"video=={v['id']}", sort="-views", **base).execute().get("rows", [])
            entry["traffic"] = {r[0]: int(r[1]) for r in tr}
        except Exception as e:
            problems.append(f"{v['id']} traffic: {type(e).__name__}")
        entry.update(collected=_iso(now), sources=sources, unavailable=UNAVAILABLE, reach=(prev or {}).get("reach", {}))
        store["videos"][v["id"]] = entry
        collected += 1
    try:
        fetch_daily(an, now, base, [v["id"] for v in videos], path)
    except Exception as e:
        problems.append(f"daily series unavailable: {type(e).__name__}: {str(e)[:120]}")
    days, reach_problem = fetch_reach(rp, session, store) if rp is not None else ({}, "reporting API client could not be built")
    for vid, d in days.items():
        if vid in store["videos"]:
            store["videos"][vid].setdefault("reach", {}).update(d)
    for vid, e in store["videos"].items():
        r = e.get("reach") or {}
        imp = sum(c["impressions"] for c in r.values())
        e["impressions"] = imp or None
        e["ctr"] = round(sum(c["impressions"] * (c["ctr"] or 0) for c in r.values()) / imp, 5) if imp else None
        e["sources"]["ctr"] = f"Reporting API {REACH_TYPE}" if imp else (reach_problem or "no reach report yet")
    if reach_problem:
        problems.append(reach_problem)
    store.update(updated=_iso(now), problems=problems[:20])
    path = Path(path or FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    filelock.write_atomic(path, json.dumps(store, indent=1))
    return {"videos": len(videos), "collected": collected, "with_ctr": sum(1 for e in store["videos"].values() if e.get("ctr") is not None), "problems": problems[:6]}
