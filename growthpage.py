"""The data behind the dashboard's Growth page, shaped defensively.

29 Oct 2026: the page assumed every weekly report had `studied` and `analysis`; the real report has neither, so it threw and showed nothing. Everything here takes
what the sources really hold (daily channel snapshots, the collector's per-video numbers, the growth view, the agent's own view) and returns plain, complete
structures: a missing source is an empty list, a missing number stays missing (None) with the reason, and nothing is ever turned into a 0 that was not measured."""
import datetime as dt

METRICS = ("views_90d", "avg_pct_viewed", "retention_at_30s", "ctr", "impressions")
REACH = ("ctr", "impressions")  # these two come from the Reporting API, whose state is recorded under sources["ctr"]


def _day(s) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def _num(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def _percent(fraction):
    """The collector stores a click rate as a fraction (0.01633 is 1.6 percent): shown as stored it read 0.0 percent. None stays None."""
    n = _num(fraction)
    return None if n is None else round(n * 100, 2)


def series(snaps) -> list[dict]:
    """Daily channel snapshots, oldest first; a row without a real date or real counts is dropped."""
    out = []
    for s in snaps or []:
        if not isinstance(s, dict) or _day(s.get("date")) is None:
            continue
        subs, views, videos = _num(s.get("subscribers")), _num(s.get("views")), _num(s.get("videos"))
        if subs is None or views is None:
            continue
        out.append({"date": str(s["date"])[:10], "subscribers": int(subs), "views": int(views), "videos": int(videos or 0)})
    out.sort(key=lambda p: p["date"])
    return out


def change(ser: list[dict], days: int = 7) -> dict | None:
    """What changed from the newest snapshot back to the latest one at least `days` older, else back to the oldest there is. `days` in the answer is the span really used."""
    if len(ser) < 2:
        return None
    last = ser[-1]
    end = _day(last["date"])
    older = [p for p in ser[:-1] if (end - _day(p["date"])).days >= days]
    ref = older[-1] if older else ser[0]
    return {"days": (end - _day(ref["date"])).days, "subscribers": last["subscribers"] - ref["subscribers"], "views": last["views"] - ref["views"], "videos": last["videos"] - ref["videos"]}


def video_rows(metrics, diagnoses=None) -> list[dict]:
    """One row per video from the collector's file, most views first. A number that is not there stays None and `why` says why."""
    diag = {d.get("title"): d for d in diagnoses or [] if isinstance(d, dict)}
    rows = []
    vids = (metrics or {}).get("videos") if isinstance(metrics, dict) else None
    for vid, v in (vids or {}).items():
        if not isinstance(v, dict):
            continue
        sources, unavailable = v.get("sources") or {}, v.get("unavailable") or {}
        row = {"id": vid, "title": (v.get("title") or "(untitled)")[:110], "published": v.get("published"), "kind": v.get("kind") or "short", "seconds": _num(v.get("seconds")),
               "views": _num(v.get("daily_views_total")), "views_90d": _num(v.get("views_90d")), "avg_pct_viewed": _num(v.get("avg_pct_viewed")),
               "retention_30s": _num(v.get("retention_at_30s")), "ctr": _percent(v.get("ctr")), "impressions": _num(v.get("impressions")), "why": {}}
        for key in METRICS:
            out_key = "retention_30s" if key == "retention_at_30s" else key
            if row[out_key] is None:
                row["why"][out_key] = unavailable.get(key) or (sources.get("ctr") if key in REACH else None) or "not available yet"
        row["diagnosis"] = diag.get(v.get("title"))
        rows.append(row)
    rows.sort(key=lambda r: (r["views"] is None, -(r["views"] or 0), r["published"] or ""))
    return rows


def build(base, snaps, gv, metrics) -> dict:
    """The whole Growth page as one structure. Every argument may be None or odd."""
    base = base if isinstance(base, dict) else {}
    ser = series(snaps)
    own = base.get("own") if isinstance(base.get("own"), dict) else None
    latest = ser[-1] if ser else ({"date": own.get("date"), "subscribers": own.get("subscribers"), "views": own.get("views"), "videos": own.get("videos")} if own else None)
    gv = gv if isinstance(gv, dict) else {}
    m = metrics if isinstance(metrics, dict) else {}
    return {"series": ser, "latest": latest, "change": change(ser, 7), "videos": video_rows(m, gv.get("diagnoses"))[:60], "metrics_updated": m.get("updated"),
            "metrics_problems": list(m.get("problems") or [])[:5], "growth": gv, "monetization": base.get("monetization"),
            "strategies": base.get("strategies") if isinstance(base.get("strategies"), list) else [], "discovered": base.get("discovered") if isinstance(base.get("discovered"), list) else [],
            "refs": base.get("refs") if isinstance(base.get("refs"), list) else [], "config": base.get("config") or {}, "profile": base.get("profile") or {},
            "timer_installed": bool(base.get("timer_installed")), "report": base.get("report") if isinstance(base.get("report"), dict) else None,
            "events": base.get("events") if isinstance(base.get("events"), list) else [], "own": own}
