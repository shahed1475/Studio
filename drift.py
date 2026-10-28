"""Algorithm drift: a sustained shift in how YouTube treats several of our videos, or in where our views come from, found from our own daily numbers.

A video's daily views are compared with that video's own previous `drift_baseline_days`: the shift counts when EVERY one of the last `drift_recent_days` days is
beyond `drift_sigma` standard deviations, in the same direction. It becomes a finding only when at least `drift_min_videos` videos shift the same way (one
video moving is that video, not the algorithm), or when one traffic source's share of views shifts. All four numbers come from config/rules.json.
It never changes strategy or rules: it tells the owner what moved, since when, and which YouTube rule changes happened in that window (a hint, not a cause)."""
import datetime as dt
import json
import math
from pathlib import Path

import agentbus
import config
import rulesfile

FILE = config.ROOT / "data" / "agent" / "metrics" / "daily.json"


def _series(by_day: dict, days: int, end: str) -> list[float]:
    last = dt.date.fromisoformat(end)
    return [float(by_day.get(str(last - dt.timedelta(days=i)), 0)) for i in range(days - 1, -1, -1)]


def sustained_shift(values: list[float], baseline: int, recent: int, sigma: float) -> dict | None:
    """{"direction", "baseline_mean", "recent_mean", "change_pct"} when every recent day is beyond sigma standard deviations of the baseline, else None.
    The deviation is never smaller than the square root of the mean (counts are noisy), so a flat quiet series cannot trigger on one view."""
    if len(values) < baseline + recent:
        return None
    base, rec = values[-(baseline + recent):-recent], values[-recent:]
    mean = sum(base) / len(base)
    if mean < 2:
        return None  # too little traffic to say anything
    std = max(math.sqrt(sum((x - mean) ** 2 for x in base) / len(base)), math.sqrt(mean))
    up, down = all(x > mean + sigma * std for x in rec), all(x < mean - sigma * std for x in rec)
    if not (up or down):
        return None
    rm = sum(rec) / len(rec)
    return {"direction": "up" if up else "down", "baseline_mean": round(mean, 2), "recent_mean": round(rm, 2), "change_pct": round(100 * (rm - mean) / mean)}


def detect(daily: dict, rules: dict | None = None, policy_changes: list[dict] | None = None) -> dict:
    """{"status", "have_days", "need_days", "events": [...]}. Not enough history is said plainly, never guessed around."""
    b = (rules or rulesfile.load())["benchmarks"]
    base, rec, sigma, need_v = int(b["drift_baseline_days"]), int(b["drift_recent_days"]), b["drift_sigma"], int(b["drift_min_videos"])
    days = sorted({d for v in (daily.get("videos") or {}).values() for d in v} | set(daily.get("traffic") or {}))
    out = {"status": "ok", "have_days": len(days), "need_days": base + rec, "events": []}
    if len(days) < base + rec:
        out["status"] = "not enough history"
        return out
    end, since = days[-1], str(dt.date.fromisoformat(days[-1]) - dt.timedelta(days=rec - 1))
    hints = [f"{c.get('page')} ({c.get('severity', '?')})" for c in (policy_changes or []) if str(c.get("at", ""))[:10] >= str(dt.date.fromisoformat(end) - dt.timedelta(days=base))]
    shifted = {"up": [], "down": []}
    for vid, by_day in (daily.get("videos") or {}).items():
        s = sustained_shift(_series(by_day, base + rec, end), base, rec, sigma)
        if s:
            shifted[s["direction"]].append((vid, s))
    for direction, rows in shifted.items():
        if len(rows) >= need_v:
            out["events"].append({"id": f"views-{direction}-{end}", "kind": "views", "direction": direction, "since": since, "videos": [v for v, _ in rows],
                                  "text": f"Views are {direction} on {len(rows)} videos for {rec} days in a row since {since} (median change {sorted(s['change_pct'] for _, s in rows)[len(rows) // 2]}%)",
                                  "policy_hints": hints})
    sources = {s for d in (daily.get("traffic") or {}).values() for s in d}
    for src in sorted(sources):
        share = {d: (t.get(src, 0) / sum(t.values()) * 100) for d, t in daily["traffic"].items() if sum(t.values())}
        s = sustained_shift(_series(share, base + rec, end), base, rec, sigma)
        if s:
            out["events"].append({"id": f"traffic-{src}-{s['direction']}-{end}", "kind": "traffic", "direction": s["direction"], "since": since, "source": src,
                                  "text": f"{src} is {s['change_pct']}% {'above' if s['direction'] == 'up' else 'below'} its share of views for {rec} days in a row since {since}",
                                  "policy_hints": hints})
    return out


def load(path: Path | None = None) -> dict:
    try:
        d = json.loads(Path(path or FILE).read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def run(now: dt.datetime | None = None, path: Path | None = None, tasks: Path | None = None, policy_changes: list[dict] | None = None) -> dict:
    """Detect, and tell the owner once per finding. Proposes nothing to YouTube and changes no rule."""
    import agentlog

    now = now or dt.datetime.now(dt.timezone.utc)
    res = detect(load(path), None, policy_changes)
    for e in res["events"]:
        t = agentbus.post_to_owner_once("algorithm_drift", "diagnoser", e["id"], e["text"][:280],
                                        ("YouTube rule changes in that window: " + "; ".join(e["policy_hints"])) if e["policy_hints"] else "No YouTube rule change was detected in that window.",
                                        "a sustained shift was found: a decision about strategy is yours", now, tasks)
        if t:
            agentlog.event("found", "Possible algorithm change", e["text"] + " Nothing was changed.", notify=True, now=now)
    return res
