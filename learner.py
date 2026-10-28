"""The weekly learner: what worked and what did not this week, from our own collected numbers, in plain words.

Every Monday (before the weekly news digest, which carries a short version) it:
- ranks documentaries and Shorts by views per day and lists the top and bottom three of each kind;
- finds which title patterns (question, number, colon, "real story", mystery words) do better or worse than the channel's median, and writes them as notes to
  rules.json insights (notes, not thresholds);
- compares this week's averages with last week's (retention at 30 s, average percent viewed, click rate when the Reporting API supplies it);
- queues a documentary subject for a Short that held its viewers (average percent viewed at or above `shorts_stayed_target_pct`) when no documentary covers the
  story and its source article exists: it only adds the subject to the normal queue, the usual ranking, duplicate and pace rules decide when it is made, at most one a week;
- proposes (never applies) a higher click-rate target when three weeks in a row ran well above it.
It reads the collector's file, writes its own files and one queue entry. It never writes to YouTube, never changes a rule, never makes a video."""
import datetime as dt
import json
import re
import statistics
from pathlib import Path

import config
import filelock
import growthdata
import rulesfile

WEEKLY = config.ROOT / "data" / "agent" / "metrics" / "weekly.json"
QUEUED = config.ROOT / "data" / "agent" / "metrics" / "queued_longs.json"
REPORTS = config.ROOT / "data" / "agent" / "reports"
PATTERNS = {
    "question": lambda t: t.strip().endswith("?") or bool(re.match(r"(?i)^(why|who|what|how|did|does|is|are|can)\b", t.strip())),
    "number": lambda t: bool(re.search(r"\d", t)),
    "colon": lambda t: ": " in t,
    "real story": lambda t: bool(re.search(r"(?i)real story|true story|\btruth\b", t)),
    "mystery words": lambda t: bool(re.search(r"(?i)mystery|unsolved|nobody|no one|unexplained|vanish|nobody can", t)),
}


def week_key(now: dt.datetime) -> str:
    y, w, _ = now.isocalendar()
    return f"{y}-W{w:02d}"


def patterns_of(title: str) -> list[str]:
    return [name for name, test in PATTERNS.items() if test(str(title))]


def views_per_day(e: dict, now: dt.datetime) -> float | None:
    if e.get("views_90d") is None or not e.get("published"):
        return None
    return e["views_90d"] / max(1, (now - growthdata._parse(e["published"])).days)


def ranking(videos: dict, now: dt.datetime, min_views: int) -> dict[str, list[dict]]:
    """{kind: rows best first} for videos with enough views to say anything (and at least a day old)."""
    out: dict[str, list[dict]] = {"doc": [], "short": []}
    for vid, e in videos.items():
        vpd = views_per_day(e, now)
        if vpd is None or (e.get("views_90d") or 0) < min_views:
            continue
        out.setdefault(e.get("kind", "short"), []).append({"id": vid, "title": e["title"], "vpd": round(vpd, 1), "avg_pct": e.get("avg_pct_viewed"), "ret30": e.get("retention_at_30s"),
                                                          "ctr": e.get("ctr"), "kind": e.get("kind", "short")})
    for rows in out.values():
        rows.sort(key=lambda r: -r["vpd"])
    return out


def title_patterns(rows: list[dict]) -> dict:
    """{"median": views per day, "stats": {pattern: (videos, mean views per day)}, "winning": [...], "losing": [...]} as plain notes (a pattern needs two videos)."""
    if len(rows) < 4:
        return {"median": None, "stats": {}, "winning": [], "losing": []}
    median = statistics.median(r["vpd"] for r in rows)
    stats = {}
    for name in PATTERNS:
        have = [r["vpd"] for r in rows if name in patterns_of(r["title"])]
        if len(have) >= 2:
            stats[name] = (len(have), round(sum(have) / len(have), 1))
    note = lambda n, s: f"{n} titles: {s[1]} views a day over {s[0]} videos (median {median:.1f})"
    return {"median": round(median, 1), "stats": stats,
            "winning": [note(n, s) for n, s in stats.items() if median and s[1] >= 1.2 * median],
            "losing": [note(n, s) for n, s in stats.items() if median and s[1] <= 0.7 * median]}


def _avg(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 1) if xs else None


def snapshot(rows_by_kind: dict, min_impressions: int, videos: dict) -> dict:
    ctrs = [e["ctr"] for e in videos.values() if e.get("ctr") is not None and (e.get("impressions") or 0) >= min_impressions]
    return {"docs": {"n": len(rows_by_kind["doc"]), "avg_pct": _avg(r["avg_pct"] for r in rows_by_kind["doc"]), "ret30": _avg(r["ret30"] for r in rows_by_kind["doc"])},
            "shorts": {"n": len(rows_by_kind["short"]), "avg_pct": _avg(r["avg_pct"] for r in rows_by_kind["short"]), "ret30": _avg(r["ret30"] for r in rows_by_kind["short"])},
            "ctr": round(statistics.median(ctrs), 5) if len(ctrs) >= 3 else None}


def trend_lines(prev: dict | None, cur: dict) -> list[str]:
    if not prev:
        return ["First week with numbers: no trend to compare yet."]
    out = []
    for kind in ("docs", "shorts"):
        for key, label in (("avg_pct", "average percent viewed"), ("ret30", "retention at 30 s")):
            a, b = prev[kind].get(key), cur[kind].get(key)
            out.append(f"{kind}: {label} {b}% (last week {a}%)" if a is not None and b is not None else f"{kind}: {label} not comparable (missing in one of the weeks)")
    out.append(f"click rate (median) {cur['ctr'] * 100:.1f}% (last week {prev['ctr'] * 100:.1f}%)" if cur.get("ctr") is not None and prev.get("ctr") is not None else
               "click rate: not available yet (needs the Reporting API reach report and at least three videos with enough impressions)")
    return out


def _load(path: Path) -> dict:
    try:
        d = json.loads(Path(path).read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _wikipedia_article(topic: str) -> str | None:
    """The source article's text, asked for again after a pause when empty (topicrank.read_article): a rate limit looks exactly like "no article"."""
    import topicrank
    import wikipedia

    return topicrank.read_article(lambda t: (wikipedia.facts_for(t, chars=7000) or (None, None))[1], topic)


def queue_longs(videos: dict, rules: dict, now: dt.datetime, article_of=None, out: Path | None = None, queued_file: Path | None = None, limit: int = 1) -> list[str]:
    """Subjects added to the documentary queue for Shorts that held their viewers. At most `limit` a call, never one already queued, never one a documentary covers,
    and only when the source article is long enough (topicrank.viable)."""
    import diagnose
    import duplicates
    import topicqueue
    import topicrank

    b = rules["benchmarks"]
    qf = Path(queued_file or QUEUED)
    done, added = _load(qf), []
    for vid, e in sorted(videos.items(), key=lambda kv: -(kv[1].get("views_90d") or 0)):
        if len(added) >= limit:
            break
        if e.get("kind") != "short" or e.get("avg_pct_viewed") is None or e["avg_pct_viewed"] < b["shorts_stayed_target_pct"] or (e.get("views_90d") or 0) < b["min_views_for_diagnosis"] or vid in done:
            continue
        meta = diagnose._meta_for(vid, out)
        topic = str((meta or {}).get("topic") or "").strip()
        if not topic or duplicates.conflict(duplicates.subject(meta), "doc", duplicates.catalogue(out), clip_of=meta.get("source_doc")):
            continue
        if any(duplicates.same_subject(duplicates.tokens(topic), duplicates.tokens(t)) for t in topicqueue.items()):
            done[vid] = {"at": now.strftime("%Y-%m-%d"), "topic": topic, "note": "already in the queue"}
            continue
        ok, why = topicrank.viable(topic, (article_of or _wikipedia_article)(topic))
        done[vid] = {"at": now.strftime("%Y-%m-%d"), "topic": topic, "note": "queued" if ok else f"not queued: {why}"}
        if ok:
            topicqueue.extend([topic])
            added.append(topic)
    qf.parent.mkdir(parents=True, exist_ok=True)
    filelock.write_atomic(qf, json.dumps(done, indent=1))
    return added


def propose_ctr_target(weekly: dict, rules: dict, now: dt.datetime) -> str | None:
    """A proposal (never applied) to raise the click-rate target when each of the last three weeks had a median click rate at least 25% above it."""
    target = rules["benchmarks"]["ctr_target"]
    last3 = [w["ctr"] for _, w in sorted(weekly.items())[-3:] if w.get("ctr") is not None]
    if len(last3) < 3 or min(last3) < 1.25 * target:
        return None
    new = round(min(min(last3) * 0.9, 0.5), 3)
    return rulesfile.propose({"benchmarks": {"ctr_target": new}}, f"three weeks in a row the median click rate ({', '.join(f'{c * 100:.1f}%' for c in last3)}) was above {target * 100:.1f}% by 25% or more",
                             "weekly learner", now) if new > target else None


def markdown(week: str, ranks: dict, pats: dict, trend: list[str], actions: list[str], rules: dict) -> str:
    def rows(kind, rs, best):
        part = rs[:3] if best else rs[3:][::-1][:3]  # the weakest list never repeats a video already among the best three
        line = lambda r: f"- {r['title'][:60]}: {r['vpd']} views a day, {r['avg_pct']}% watched" + (f", click rate {r['ctr'] * 100:.1f}%" if r.get("ctr") is not None else "")
        return [line(r) for r in part] or (["- not enough videos with views yet"] if not rs else ["- fewer than four videos: no separate weakest list yet"])
    lines = [f"# Weekly growth report, {week}", ""]
    for kind, name in (("doc", "Documentaries"), ("short", "Shorts")):
        lines += [f"## {name}: best three", *rows(kind, ranks[kind], True), f"## {name}: weakest three", *rows(kind, ranks[kind], False), ""]
    lines += ["## Title patterns", *(pats["winning"] and [f"- doing well: {x}" for x in pats["winning"]] or ["- no pattern is clearly ahead yet"]), *[f"- doing badly: {x}" for x in pats["losing"]], "", "## Trend",
              *[f"- {x}" for x in trend], "", "## What I did", *([f"- {a}" for a in actions] or ["- nothing needed"]), "", f"Rules {rules['rules_version']}, last verified {rules['last_verified']}. Numbers come from the YouTube Analytics API; "
              "unique viewers are not available from it, so views per unique viewer is not reported.", ""]
    return "\n".join(lines)


def run(now: dt.datetime | None = None, metrics: Path | None = None, out: Path | None = None, weekly_file: Path | None = None, reports: Path | None = None,
        queued_file: Path | None = None, article_of=None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    rules = rulesfile.load()
    b = rules["benchmarks"]
    videos = growthdata.load(metrics)["videos"]
    ranks = ranking(videos, now, int(b["min_views_for_diagnosis"]))
    pats = title_patterns(ranks["doc"] + ranks["short"])
    week, wf = week_key(now), Path(weekly_file or WEEKLY)
    weekly = _load(wf)
    cur = snapshot(ranks, int(b["min_impressions_for_ctr"]), videos)
    prev = next((w for k, w in sorted(weekly.items(), reverse=True) if k < week), None)
    weekly[week] = cur
    wf.parent.mkdir(parents=True, exist_ok=True)
    filelock.write_atomic(wf, json.dumps(dict(sorted(weekly.items())[-26:]), indent=1))
    actions = []
    winners = [r["title"][:80] for r in sorted(ranks["doc"] + ranks["short"], key=lambda r: -r["vpd"])[:3]]  # the best three of any kind
    rulesfile.set_insights({"winning_title_patterns": pats["winning"], "winning_topics": winners, "losing_patterns": pats["losing"]})
    actions.append("wrote the winning and losing patterns to the rules insights (notes only)")
    try:
        queued = queue_longs(videos, rules, now, article_of, out, queued_file)
    except Exception as e:
        queued = []
        actions.append(f"could not queue a documentary from a strong Short: {type(e).__name__}")
    actions += [f"queued a documentary subject because a Short held its viewers: {t}" for t in queued]
    pid = propose_ctr_target(weekly, rules, now)
    if pid:
        actions.append(f"proposed a higher click-rate target ({pid}): you approve it with `python run.py rules approve {pid}`")
    text = markdown(week, ranks, pats, trend_lines(prev, cur), actions, rules)
    rd = Path(reports or REPORTS)
    rd.mkdir(parents=True, exist_ok=True)
    filelock.write_atomic(rd / f"weekly-{week}.md", text)
    filelock.write_atomic(rd / "latest.md", text)
    filelock.write_atomic(rd / "latest.json", json.dumps({"week": week, "generated_at": growthdata._iso(now), "queued": queued, "proposal": pid, "winning": pats["winning"], "losing": pats["losing"]}))
    return {"week": week, "videos": sum(len(v) for v in ranks.values()), "queued": queued, "proposal": pid, "report": str(rd / f"weekly-{week}.md")}


def latest_summary(now: dt.datetime, reports: Path | None = None, lines: int = 14) -> str:
    """The first lines of this week's report for the weekly digest, or "" when none was written this week."""
    rd = Path(reports or REPORTS)
    meta = _load(rd / "latest.json")
    try:
        return "\n".join((rd / "latest.md").read_text().splitlines()[:lines]) if meta.get("week") == week_key(now) else ""
    except OSError:
        return ""
