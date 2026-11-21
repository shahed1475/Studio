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


VIDEO_ID = __import__("re").compile(r"^[A-Za-z0-9_-]{11}$")  # a real YouTube id: test rows such as "V2" are never counted


def _weighted(cells) -> tuple[int, float | None]:
    """(impressions, click rate as a fraction) over reach cells, weighted by impressions."""
    imp = sum(int(_num(c.get("impressions")) or 0) for c in cells)
    clicks = sum(int(_num(c.get("impressions")) or 0) * float(_num(c.get("ctr")) or 0) for c in cells)
    return imp, (clicks / imp if imp else None)


def _window(reach: dict, start: dt.date, end: dt.date) -> list[dict]:
    """Reach cells of the days start..end, both included."""
    return [c for d, c in (reach or {}).items() if isinstance(c, dict) and (day := _day(d)) and start <= day <= end]


def _videos(metrics) -> dict:
    """The collector's videos that are records, each with a reach dict (an odd entry is left out, never a crash of the page)."""
    vids = (metrics or {}).get("videos") if isinstance(metrics, dict) else None
    if not isinstance(vids, dict):
        return {}
    return {k: {**v, "reach": v["reach"] if isinstance(v.get("reach"), dict) else {}} for k, v in vids.items() if isinstance(v, dict)}


def _bench(rules) -> dict:
    try:
        import rulesfile

        b = (rules or rulesfile.load())["benchmarks"]
        return {"target": float(b["ctr_target"]), "retest": float(b["ctr_retest_below"]), "min_imp": int(b["min_impressions_for_ctr"])}
    except Exception:  # an unreadable rules file must not take the page down: the shipped numbers
        return {"target": 0.04, "retest": 0.03, "min_imp": 200}


def ctr_summary(metrics, now: dt.datetime | None = None, rules=None) -> dict:
    """The channel's thumbnail click rate from YouTube's reach reports: the last 28 days against the 28 before, documentaries and Shorts apart,
    and the best and weakest videos that have enough impressions to judge. A video below the rules file's retest line is marked."""
    now = now or dt.datetime.now(dt.timezone.utc)
    vids = _videos(metrics)
    b = _bench(rules)
    days = [_day(d) for e in vids.values() for d in e["reach"]]
    days = [d for d in days if d]
    end = max(days) if days else now.date()  # reports arrive a day or two late: windows end at the newest reported day
    last = (end - dt.timedelta(days=27), end)
    prev = (end - dt.timedelta(days=55), end - dt.timedelta(days=28))

    def block(cells) -> dict:
        imp, ctr = _weighted(cells)
        return {"impressions": imp, "ctr_pct": _percent(ctr)}

    out = {"through": end.isoformat() if days else None, "last_28": block([c for e in vids.values() for c in _window(e.get("reach"), *last)]),
           "prev_28": block([c for e in vids.values() for c in _window(e.get("reach"), *prev)]), "by_kind": {},
           "target_pct": _percent(b["target"]), "retest_pct": _percent(b["retest"]), "min_impressions": b["min_imp"]}
    for kind in ("doc", "short"):
        out["by_kind"][kind] = block([c for e in vids.values() if e.get("kind") == kind for c in _window(e.get("reach"), *last)])
    judged = []
    for vid, e in vids.items():
        if not VIDEO_ID.match(str(vid)):
            continue
        imp, ctr = _weighted([c for c in (e.get("reach") or {}).values() if isinstance(c, dict)])
        if imp >= b["min_imp"] and ctr is not None:
            judged.append({"video_id": vid, "title": str(e.get("title") or "")[:90], "kind": e.get("kind"), "impressions": imp, "ctr_pct": _percent(ctr),
                           "below_retest": ctr < b["retest"]})
    judged.sort(key=lambda r: -r["ctr_pct"])
    out["videos_judged"] = len(judged)
    out["best"] = judged[:3]
    out["weakest"] = [r for r in reversed(judged[3:])][:3] if len(judged) > 3 else []
    out["below_retest"] = sum(1 for r in judged if r["below_retest"])
    return out


def title_effects(metrics, actions, rules=None, days: int = 7) -> list[dict]:
    """For each logged title change of a video with reach data: the click rate in the `days` before and after (the day of the change left out).
    Read only: a before/after reading, not a controlled test (the video's age, the season and the traffic mix change too)."""
    vids = _videos(metrics)
    b = _bench(rules)
    rows = []
    for a in actions if isinstance(actions, list) else []:
        if not isinstance(a, dict) or not isinstance(a.get("before"), dict) or not isinstance(a.get("after"), dict):
            continue
        vid, old, new = str(a.get("video_id") or ""), a["before"].get("title"), a["after"].get("title")
        if not VIDEO_ID.match(vid) or not new or old == new or vid not in vids:
            continue
        day = _day(a.get("at"))
        reach = vids[vid].get("reach") or {}
        newest = max((d for d in (_day(x) for x in reach) if d), default=None)
        if not day or not newest:
            continue
        bi, bc = _weighted(_window(reach, day - dt.timedelta(days=days), day - dt.timedelta(days=1)))
        ai, ac = _weighted(_window(reach, day + dt.timedelta(days=1), day + dt.timedelta(days=days)))
        if newest < day + dt.timedelta(days=days):
            verdict = "too recent: the reports do not cover the week after yet"
        elif bi < b["min_imp"] or ai < b["min_imp"]:
            verdict = f"not enough impressions yet (at least {b['min_imp']} on each side)"
        else:
            diff = (ac - bc) * 100
            verdict = "about the same" if abs(diff) < 0.5 else ("higher after" if diff > 0 else "lower after")
        rows.append({"video_id": vid, "at": str(a.get("at"))[:16], "title_before": str(old or "")[:90], "title_after": str(new)[:90], "source": a.get("source"),
                     "rolled_back": bool(a.get("rolled_back")), "before": {"impressions": bi, "ctr_pct": _percent(bc)}, "after": {"impressions": ai, "ctr_pct": _percent(ac)},
                     "verdict": verdict})
    return sorted(rows, key=lambda r: r["at"], reverse=True)[:20]


def build(base, snaps, gv, metrics, actions=None) -> dict:
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
            "events": base.get("events") if isinstance(base.get("events"), list) else [], "own": own,
            "ctr": ctr_summary(m), "title_effects": title_effects(m, actions)}
