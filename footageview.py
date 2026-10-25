"""The "Footage clips" view: for each video, every clip run with its status, error, cost, ledger row, decision, contact sheet and last log lines, plus today's spend
against the daily cap. Served by the dashboard at /footage (page) and /api/footage (data), behind the same login as everything else. Read-only."""
import datetime as dt
import json

import config
import footagestore

SHOWN_RUNS = 60
LOG_LINES = 50
LEDGER_FIELDS = ("source", "author", "licence", "fetched", "sha256")


def _title(scope: str) -> str:
    """The video's title from its record (read through records.py), or the scope's own name for a test run with no video."""
    import records

    try:
        return (records.read(config.OUT / scope).get("title") or scope)[:120]
    except (OSError, ValueError, records.RecordError):
        return scope


def _ledger(scope: str, run_id: str) -> dict | None:
    path = footagestore.file_path(scope, run_id, "ledger")
    if path is None:
        return None
    try:
        row = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return {k: str(row.get(k, ""))[:200] for k in LEDGER_FIELDS} if isinstance(row, dict) else None


def _number(x) -> float:
    try:
        return round(float(x or 0.0), 4)
    except (TypeError, ValueError):
        return 0.0


def _run(rec: dict) -> dict:
    scope, run_id = rec["scope"], rec["run_id"]
    base = f"/footage/file/{scope}/{run_id}/"
    urls = {f"{k}_url": base + k for k in footagestore.FILE_KINDS if footagestore.file_path(scope, run_id, k)}
    return {"run_id": run_id, "status": rec.get("status"), "error": rec.get("error"), "decision": rec.get("decision"), "reason": rec.get("reason") or "",
            "model": rec.get("model"), "job": rec.get("job"), "created_at": rec.get("created_at"), "finished_at": rec.get("finished_at"),
            "cost": _number(rec.get("cost_booked")), "ledger": _ledger(scope, run_id), "log": footagestore.tail(scope, run_id, LOG_LINES), **urls}


def build(now: dt.datetime | None = None) -> dict:
    import llm

    now = now or dt.datetime.now(dt.timezone.utc)
    cap, spent = llm.load_config()["daily_budget_usd"], llm.spent_today(now)
    by_scope: dict[str, list[dict]] = {}
    for rec in footagestore.runs()[:SHOWN_RUNS]:
        by_scope.setdefault(rec["scope"], []).append(rec)
    videos = [{"scope": scope, "title": _title(scope), "total_cost": round(llm.video_cost(scope), 4), "runs": [_run(r) for r in recs]} for scope, recs in by_scope.items()]
    return {"at": now.strftime("%Y-%m-%d %H:%M"), "money": {"spent_today": round(spent, 4), "cap": cap, "left": round(cap - spent, 4)}, "videos": videos}
