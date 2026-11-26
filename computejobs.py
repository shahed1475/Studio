"""Remote and local inference jobs (24 Nov 2026): one JSON file per job in data/compute/jobs/, written atomically, so a power cut or a killed
worker loses nothing. A job's id is the hash of what it asks (model, task, input reference, parameters): asking twice gives the same job, never a
second run. A payload that looks like a credential is refused: keys and tokens never travel inside a job."""
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

import config

DIR = config.ROOT / "data" / "compute" / "jobs"
STATUSES = ("QUEUED", "PREPARING", "MODEL_LOADING", "RUNNING", "CHECKPOINTED", "COMPLETED", "FAILED", "INTERRUPTED", "BLOCKED",
            "BLOCKED_PENDING_TERMS_REVIEW", "RECOVERY_PENDING")
FINAL = ("COMPLETED", "FAILED", "BLOCKED", "BLOCKED_PENDING_TERMS_REVIEW")
NEXT = {"QUEUED": {"PREPARING", "BLOCKED", "BLOCKED_PENDING_TERMS_REVIEW", "FAILED"},
        "PREPARING": {"MODEL_LOADING", "FAILED", "INTERRUPTED", "BLOCKED"},
        "MODEL_LOADING": {"RUNNING", "FAILED", "INTERRUPTED"},
        "RUNNING": {"CHECKPOINTED", "COMPLETED", "FAILED", "INTERRUPTED"},
        "CHECKPOINTED": {"CHECKPOINTED", "RUNNING", "COMPLETED", "INTERRUPTED", "FAILED"},  # every finished item saves its progress
        "INTERRUPTED": {"RECOVERY_PENDING", "FAILED"},
        "RECOVERY_PENDING": {"PREPARING", "FAILED"},
        "BLOCKED": {"QUEUED"}, "BLOCKED_PENDING_TERMS_REVIEW": {"QUEUED"}, "FAILED": {"QUEUED"}, "COMPLETED": set()}
SECRET = re.compile(r"(?i)(sk-[a-z0-9-]{16,}|AIza[0-9A-Za-z_-]{30,}|ya29\.[0-9A-Za-z_-]{20,}|hf_[A-Za-z0-9]{20,}|bearer\s+[a-z0-9._-]{20,}|"
                    r"\"?(api[_-]?key|token|password|secret|authorization)\"?\s*[:=])")


class JobError(ValueError):
    pass


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def job_id(model: str, task: str, input_ref: str, params: dict | None = None, environment: str = "", data_class: str = "production") -> str:
    """The same request on the same environment and data class is one job (24 Nov 2026: without the environment, a CPU run of a prompt found the GPU run's job;
    without the data class, a production request was handed an earlier public-test job and its label, which the Kaggle gate trusts)."""
    return hashlib.sha256(json.dumps([model, task, input_ref, params or {}, environment, data_class], sort_keys=True).encode()).hexdigest()[:16]


def _path(jid: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{16}", jid):
        raise JobError("bad job id")
    return DIR / f"{jid}.json"


def _write(job: dict) -> dict:
    DIR.mkdir(parents=True, exist_ok=True)
    p = _path(job["id"])
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(job, indent=1))
    tmp.replace(p)
    return job


def get(jid: str) -> dict | None:
    try:
        return json.loads(_path(jid).read_text())
    except (OSError, ValueError):
        return None


def submit(model: str, task: str, input_ref: str, *, environment: str, capabilities=(), resources: dict | None = None, timeout_s: int = 600,
           priority: int = 5, params: dict | None = None, data_class: str = "production", output_dir: str = "data/compute/outputs") -> dict:
    """A new job, or the existing one for the same request (a duplicate is never run twice). A job that FAILED or was BLOCKED is queued again."""
    payload = json.dumps([model, task, input_ref, params or {}, resources or {}])
    if SECRET.search(payload):
        raise JobError("a job must not carry a key, token or password: the worker reads its own credentials")
    jid = job_id(model, task, input_ref, params, environment, data_class)
    old = get(jid)
    if old and old["status"] not in ("FAILED", "BLOCKED", "BLOCKED_PENDING_TERMS_REVIEW"):
        return old
    job = {"id": jid, "model": model, "task": task, "input_ref": input_ref, "params": params or {}, "capabilities": list(capabilities),
           "resources": resources or {}, "timeout_s": timeout_s, "priority": priority, "data_class": data_class, "environment": environment,
           "checkpoint": None, "output": None, "output_dir": output_dir, "status": "QUEUED", "history": (old or {}).get("history", []) + [[_now(), "QUEUED", ""]],
           "created": (old or {}).get("created", _now()), "attempts": (old or {}).get("attempts", 0)}
    return _write(job)


def move(jid: str, status: str, why: str = "", **fields) -> dict:
    job = get(jid)
    if job is None:
        raise JobError(f"no job {jid}")
    if status not in STATUSES or status not in NEXT[job["status"]]:
        raise JobError(f"{job['status']} -> {status} is not allowed")
    job.update(fields)
    job["status"] = status
    job["history"] = (job.get("history") or [])[-40:] + [[_now(), status, str(why)[:300]]]
    if status == "PREPARING":
        job["attempts"] = job.get("attempts", 0) + 1
    return _write(job)


def checkpoint(jid: str, state: dict) -> dict:
    """Save how far a job got (done item ids, partial outputs' references): a resume continues from here, never from the start."""
    job = get(jid)
    if job is None or job["status"] not in ("RUNNING", "CHECKPOINTED"):
        raise JobError("only a running job checkpoints")
    return move(jid, "CHECKPOINTED", "progress saved", checkpoint={**(job.get("checkpoint") or {}), **state, "at": _now()}, heartbeat=__import__("time").time())


MAX_ATTEMPTS = 5


def alive(job: dict) -> bool:
    """Is a process still working on this job? Its pid is alive on this machine (24 Nov 2026 review: recover took over a job another process was running)."""
    pid = job.get("pid")
    if not pid:
        return False
    try:
        __import__("os").kill(int(pid), 0)
        return True
    except (OSError, ValueError):
        return False


def interrupted() -> list[dict]:
    """Jobs to resume: INTERRUPTED ones, and ones left PREPARING, MODEL_LOADING, RUNNING or CHECKPOINTED whose process is gone (a cut, a restart).
    A Kaggle job is remote: it is never declared dead from here."""
    out = []
    for p in sorted(DIR.glob("*.json")) if DIR.exists() else []:
        try:
            j = json.loads(p.read_text())
        except (OSError, ValueError):
            continue
        if j.get("environment") == "kaggle_gpu":
            continue
        if j.get("status") == "INTERRUPTED" or (j.get("status") in ("PREPARING", "MODEL_LOADING", "RUNNING", "CHECKPOINTED") and not alive(j)):
            out.append(j)
    return out


def all_jobs(limit: int = 50) -> list[dict]:
    if not DIR.exists():
        return []
    js = []
    for p in DIR.glob("*.json"):
        try:
            js.append(json.loads(p.read_text()))
        except (OSError, ValueError):
            pass
    return sorted(js, key=lambda j: j.get("history", [[""]])[-1][0], reverse=True)[:limit]
