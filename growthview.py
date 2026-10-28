"""One read-only summary of the growth system for the dashboard: the policy hold, the rules file, the collector, the latest diagnoses, drift, the weekly report and
the changes waiting for the owner. It reads files, never writes, never calls YouTube, and never raises (a part that cannot be read is shown as empty)."""
import datetime as dt

import actionlog
import diagnose
import drift
import growthdata
import learner
import policyclass
import rulesfile


def _safe(fn, default):
    try:
        return fn()
    except Exception:
        return default


def diagnoses(limit: int = 8) -> list[dict]:
    """The latest diagnosis of each video (its 7-day one if it has it), real problems first."""
    rows = []
    for vid, wins in diagnose.load().items():
        window = "7d" if "7d" in wins else "48h"
        d = wins[window]
        rows.append({"video": vid, "title": d["title"][:70], "window": window, "primary": d["primary"], "evidence": "; ".join(f["evidence"] for f in d["findings"])[:200]})
    rows.sort(key=lambda r: (r["primary"] in ("none", "insufficient_data"), r["title"]))
    return rows[:limit]


def view(now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    rules = _safe(rulesfile.load, {"rules_version": "?", "last_verified": "?", "pending_changes": [], "_problems": ["rules could not be read"]})
    metrics = _safe(growthdata.load, {"videos": {}})
    vids = metrics.get("videos", {})
    d = _safe(lambda: drift.detect(drift.load(), rules), {"status": "unavailable", "have_days": 0, "need_days": 0, "events": []})
    return {
        "hold": _safe(policyclass.hold_active, None),
        "policy_recent": _safe(lambda: policyclass.recent(3), []),
        "rules": {"version": rules.get("rules_version"), "last_verified": rules.get("last_verified"), "pending": len(rules.get("pending_changes", [])),
                  "stale_days": _safe(lambda: rulesfile.stale_days(rules, now), None), "problems": rules.get("_problems", [])[:3]},
        "metrics": {"updated": metrics.get("updated"), "videos": len(vids), "with_ctr": sum(1 for e in vids.values() if e.get("ctr") is not None), "problems": metrics.get("problems", [])[:3]},
        "diagnoses": _safe(diagnoses, []),
        "drift": {"status": d["status"], "have_days": d["have_days"], "need_days": d["need_days"], "events": [e["text"] for e in d["events"]]},
        "report": _safe(lambda: learner.latest_summary(now, lines=16), ""),
        "edits_pending": len(_safe(actionlog.pending, [])),
        "actions": [{"at": a["at"], "video_id": a["video_id"], "source": a["source"], "why": a["why"][:100], "rolled_back": bool(a.get("rolled_back"))} for a in _safe(lambda: actionlog.actions(3), [])],
    }
