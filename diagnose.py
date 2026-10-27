"""Diagnoser: one primary problem per video, 48 hours and 7 days after it was published, from the numbers growthdata.py collected.

Every threshold comes from config/rules.json (rulesfile.py); none is written here. A video with too few views is "insufficient_data": nothing is guessed.
The findings go to a file and, for a real problem, to the owner as a task. This module never writes to YouTube and never changes a video or a rule."""
import datetime as dt
import json
import statistics
from pathlib import Path

import agentbus
import config
import filelock
import growthdata
import rulesfile

FILE = config.ROOT / "data" / "agent" / "metrics" / "diagnoses.json"
WINDOWS = (("48h", 2), ("7d", 7))  # name, days after publishing
ORDER = ("packaging", "hook", "pacing", "missed_long", "topic")  # which problem is "the primary one" when several apply
ACTIONS = {
    "packaging": "The title or thumbnail is not earning the click: write three new titles and thumbnail briefs and test them (you approve any change).",
    "hook": "People click but leave early: the opening does not deliver the title's promise. Rewrite the hook for the next videos.",
    "pacing": "A steep drop at one moment: look at that part of the script and tighten or re-hook it in the next videos.",
    "missed_long": "A Short held its viewers and no documentary covers the story: queue a documentary on this subject.",
    "topic": "Viewers who see it like it but few see it: improve the search keywords or pick related topics.",
}


def sudden_drop(curve: list, seconds: float, pp: float, span: int = 5) -> tuple[float, float] | None:
    """(second, percentage points) of the steepest fall over `span` points (5% of the video) between 10% and 90% in, when it is at least `pp`."""
    pts = [(float(r[0]), float(r[1])) for r in curve or []]
    worst = None
    for i in range(len(pts) - span):
        (x0, y0), (x1, y1) = pts[i], pts[i + span]
        if x0 < 0.10 or x1 > 0.90:
            continue
        drop = (y0 - y1) * 100
        if drop >= pp and (worst is None or drop > worst[1]):
            worst = (round(x0 * seconds, 1), round(drop, 1))
    return worst


def _meta_for(video_id: str, out: Path | None = None) -> dict | None:
    for f in sorted((out or config.OUT).glob("*/meta.json")):
        try:
            m = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        if m.get("video_id") == video_id:
            return {**m, "_folder": f.parent.name}
    return None


def _clock(sec: float) -> str:
    return f"{int(sec // 60)}:{int(sec % 60):02d}"


def findings(vid: str, e: dict, videos: dict, rules: dict | None = None, out: Path | None = None) -> list[dict]:
    """Every problem that applies to this video (empty when it is doing fine or there is too little data), in the order of ORDER."""
    b = (rules or rulesfile.load())["benchmarks"]
    views = e.get("views_90d") or 0
    if views < b["min_views_for_diagnosis"]:
        return []
    ctr, imp, ret30, avg = e.get("ctr"), e.get("impressions") or 0, e.get("retention_at_30s"), e.get("avg_pct_viewed")
    found = []
    if ctr is not None and imp >= b["min_impressions_for_ctr"] and ctr < b["ctr_retest_below"]:
        found.append(("packaging", f"click rate {ctr * 100:.1f}% on {imp} impressions, below {b['ctr_retest_below'] * 100:.0f}%"))
    if ret30 is not None and ret30 < b["retention_at_30s_min_pct"] and (ctr is None or ctr >= b["ctr_target"]):
        found.append(("hook", f"retention at 30 s is {ret30:.0f}%, below {b['retention_at_30s_min_pct']}%" + (" (click rate not available yet, so a broken promise is not proven)" if ctr is None else f" although the click rate is {ctr * 100:.1f}%")))
    if e.get("kind") == "doc":
        drop = sudden_drop(e.get("retention_curve"), e.get("seconds") or 0, b["retention_drop_pp"])
        if drop:
            meta, seg = _meta_for(vid, out), ""
            if meta:
                try:
                    import fixer

                    seg = (fixer.lines_at(meta, (out or config.OUT) / meta["_folder"], [drop[0]]) or [""])[0][:140]
                except Exception:
                    seg = ""
            found.append(("pacing", f"viewers fall by {drop[1]:.0f} points around {_clock(drop[0])}" + (f': "{seg}"' if seg else "")))
    if e.get("kind") == "short" and avg is not None and avg >= b["shorts_stayed_target_pct"]:
        meta = _meta_for(vid, out)
        if meta:
            import duplicates

            if not duplicates.conflict(duplicates.subject(meta), "doc", duplicates.catalogue(out), clip_of=meta.get("source_doc")):
                found.append(("missed_long", f"average {avg:.0f}% of the Short was watched (a proxy for 'stayed to watch') and no documentary covers this story"))
    others = [v["impressions"] for k, v in videos.items() if k != vid and v.get("impressions")]
    if avg is not None and avg >= b["retention_target_pct"] and imp and len(others) >= 3 and imp < 0.5 * statistics.median(others):
        found.append(("topic", f"{avg:.0f}% watched but only {imp} impressions, under half the channel's median"))
    return sorted(found, key=lambda f: ORDER.index(f[0]))


def due_windows(published: str, now: dt.datetime, done: dict) -> list[str]:
    age = (now - growthdata._parse(published)).days
    return [name for name, days in WINDOWS if age >= days and name not in done]


def load(path: Path | None = None) -> dict:
    try:
        d = json.loads(Path(path or FILE).read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def run(now: dt.datetime | None = None, metrics: Path | None = None, path: Path | None = None, out: Path | None = None, tasks: Path | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    videos = growthdata.load(metrics)["videos"]
    store, rules, new, posted = load(path), rulesfile.load(), [], 0
    for vid, e in videos.items():
        if not e.get("published") or e.get("views_90d") is None:
            continue
        for window in due_windows(e["published"], now, store.get(vid, {})):
            fs = findings(vid, e, videos, rules, out)
            few = (e.get("views_90d") or 0) < rules["benchmarks"]["min_views_for_diagnosis"]
            primary = fs[0][0] if fs else ("insufficient_data" if few else "none")
            store.setdefault(vid, {})[window] = {"at": growthdata._iso(now), "title": e["title"], "primary": primary, "findings": [{"problem": p, "evidence": ev} for p, ev in fs],
                                                   "action": ACTIONS.get(primary, "")}
            new.append((vid, window, primary))
            if primary in ACTIONS and ("growth_" + primary, vid) not in {(t["kind"], t["slug"]) for t in agentbus.tasks(tasks) if t["state"] in agentbus.LIVE + ("owner",)}:
                t = agentbus.post("growth_" + primary, "diagnoser", "owner", slug=vid, reason=f"{e['title'][:70]} ({window}): {ACTIONS[primary]}",
                                  evidence="; ".join(ev for _, ev in fs)[:500], now=now, file=tasks)
                if t.get("id"):
                    agentbus.to_owner(t["id"], "growth diagnosis: a decision is yours", now, tasks)
                    posted += 1
    if new:
        path = Path(path or FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        filelock.write_atomic(path, json.dumps(store, indent=1))
    return {"diagnosed": len(new), "tasks_for_owner": posted, "results": new[:20]}


def report(path: Path | None = None) -> str:
    lines = []
    for vid, wins in load(path).items():
        for w, d in wins.items():
            lines.append(f"{d['title'][:50]:50} {w:3} {d['primary']:17} " + "; ".join(f["evidence"] for f in d["findings"])[:160])
    return "\n".join(lines) or "no diagnoses yet"
