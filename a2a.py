"""A2A on the agent bus: Agent Cards, contract-checked tasks between agents, and checked hand-overs between the stages of one video.

The shape of the open Agent2Agent protocol (an Agent Card for each agent; a message to an agent becomes a task with an id, a context id and a status)
built on `agentbus` (no second bus) and the registry in `agents.py`. Plan: docs/superpowers/plans/2026-11-17-free-quality-pipeline.md, Task 7.

Rules the tests pin (tests/test_a2a.py):
- an agent never messages itself, and only an agent it hands over to (agents.AGENTS hands_to), unless the sender is the doctor or autopilot;
- the same open question to the same agent about the same video is one task, not two (agentbus keeps one live task per kind, target and video);
- text from any agent is cleaned (no links, no control characters), capped, and stored as data: it is never run as an instruction;
- only the agent a task was sent to may acknowledge or answer it; the answer must match the task's expected schema; a closed task keeps its
  outcome, so a late or repeated answer can never complete it a second time;
- a task past its deadline is offered again up to its retry limit, then failed with the reason;
- nothing here can publish, delete, change a public video, flip an owner switch, release a policy hold or spend money: the only kinds are
  questions, checks and diagnoses (SCHEMAS), and an answer is information for the agent that asked.

The stage hand-overs (`handoff`) are the orchestrator's own checks: the creator does not move from voice to pictures to render on its word alone, it
checks the real files and numbers each stage produced, and records every hand-over in the video's record (`handoffs`).
"""
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

import agentbus
import agents
import filelock

FREE_SENDERS = ("doctor", "autopilot")  # they coordinate everyone; every other agent talks only along its hand-over map
SCHEMAS = {  # what an answer must contain: field -> type
    "answer": {"answer": str, "evidence": str},
    "verdict": {"ok": bool, "findings": list},
    "diagnosis": {"cause": str, "evidence": str, "safe_fix": str},
}
STATE_NAMES = {"open": "submitted", "working": "working", "done": "completed", "failed": "failed", "owner": "input-required"}
MAX_TEXT = 1200
MAX_RETRIES = 3
DEFAULT_TIMEOUT_S = 3600


class A2AError(ValueError):
    pass


class HandoffError(RuntimeError):
    pass


def _now(now=None) -> dt.datetime:
    return now or dt.datetime.now(dt.timezone.utc)


def _iso(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def clean(text, cap: int = MAX_TEXT) -> str:
    """Plain text only: links and control characters removed, whitespace folded, capped. It is stored as data."""
    t = re.sub(r"https?://\S+|www\.\S+", "[link removed]", str(text or ""))
    t = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", " ", t)
    return re.sub(r"\s+", " ", t).strip()[:cap]


# ---- Agent Cards ----
def card(agent: str) -> dict:
    """The A2A Agent Card for one studio agent, from agents.AGENTS and its playbook (playbooks/<agent>.md)."""
    if agent not in agents.AGENTS:
        raise A2AError(f"no agent called {agent!r}")
    import playbook

    a, pb = agents.AGENTS[agent], playbook.load(agent) or {}
    return {"name": agent, "description": clean(pb.get("Role", ""), 300), "version": "1",
            "skills": [{"id": c, "name": c, "description": f"python run.py {c}"} for c in a.get("cmds", [])],
            "capabilities": {"streaming": False, "pushNotifications": False, "stateTransitionHistory": True},
            "defaultInputModes": ["text/plain", "application/json"], "defaultOutputModes": ["application/json"],
            "handsTo": list(a.get("hands_to", [])), "acceptsFrom": sorted(set(FREE_SENDERS) | {s for s, v in agents.AGENTS.items() if agent in v.get("hands_to", [])})}


def cards() -> list[dict]:
    return [card(a) for a in agents.AGENTS]


def may_message(source: str, target: str) -> bool:
    return source in agents.AGENTS and target in agents.AGENTS and source != target and (
        source in FREE_SENDERS or target in agents.AGENTS[source].get("hands_to", []))


# ---- tasks between agents ----
def view(t: dict | None) -> dict | None:
    """A bus task in A2A form: {id, contextId, status: {state, message}, ...}."""
    if not t:
        return None
    a = t.get("a2a") or {}
    state = "canceled" if a.get("canceled") else STATE_NAMES.get(t["state"], t["state"])
    return {"id": t["id"], "contextId": a.get("context", t.get("slug", "")), "from": t["source"], "to": t["target"], "kind": t["kind"],
            "status": {"state": state, "message": t.get("outcome", "")}, "expects": a.get("schema"), "deadline": a.get("deadline"),
            "retries_left": a.get("retries_left"), "result": a.get("result"), "history": t.get("history", [])}


def send(source: str, target: str, text: str, schema: str = "answer", slug: str = "", context_id: str | None = None, inputs: list[str] | None = None,
         timeout_s: int = DEFAULT_TIMEOUT_S, retries: int = 1, now=None) -> dict:
    """Ask `target` something. Returns the task in A2A form. The kind holds a hash of the question, so one open question is one task."""
    if not may_message(source, target):
        raise A2AError(f"{source} may not message {target}: not on its hand-over map")
    if schema not in SCHEMAS:
        raise A2AError(f"unknown answer schema {schema!r}")
    q = clean(text)
    if not q:
        raise A2AError("an empty message")
    now = _now(now)
    kind = f"a2a:{schema}:{hashlib.sha256(q.encode()).hexdigest()[:10]}"
    t = agentbus.post(kind, source, target, slug=slug, reason=q[:300], evidence=clean(" ".join(inputs or []), 600), now=now)
    with filelock.locked(agentbus.FILE):
        rows = agentbus._load(agentbus.FILE)
        for r in rows:
            if r["id"] == t["id"] and "a2a" not in r:
                r["a2a"] = {"schema": schema, "question": q, "context": context_id or slug or r["id"], "inputs": [clean(i, 200) for i in (inputs or [])][:5],
                            "deadline": _iso(now + dt.timedelta(seconds=max(60, int(timeout_s)))), "timeout_s": max(60, int(timeout_s)),
                            "retries_left": max(0, min(MAX_RETRIES, int(retries)))}
                r.setdefault("history", []).append(f"{_iso(now)} a2a contract: answer as {schema}, deadline {r['a2a']['deadline']}")
                t = r
        agentbus._save(agentbus.FILE, rows)
    return view(t)


def _row(task_id: str) -> dict | None:
    return next((r for r in agentbus.tasks() if r["id"] == task_id), None)


def get(task_id: str) -> dict | None:
    return view(_row(task_id))


def acknowledge(task_id: str, who: str, now=None) -> dict:
    """The target takes the task (working)."""
    t = _row(task_id)
    if not t or "a2a" not in t:
        raise A2AError(f"no A2A task {task_id}")
    if who != t["target"]:
        raise A2AError(f"{who} cannot take a task sent to {t['target']}")
    return view(agentbus.claim(task_id, who, now=now) or t)


def _valid(result, schema: str) -> list[str]:
    if not isinstance(result, dict):
        return ["the answer is not a JSON object"]
    return [f"'{k}' must be {typ.__name__}" for k, typ in SCHEMAS[schema].items() if not isinstance(result.get(k), typ)]


def deliver(task_id: str, who: str, result: dict, now=None) -> dict:
    """The target's answer. Checked against the task's schema: a wrong answer is sent back while retries are left, then the task fails.
    A closed task keeps its outcome: a second or late answer is refused."""
    now = _now(now)
    with filelock.locked(agentbus.FILE):
        rows = agentbus._load(agentbus.FILE)
        t = next((r for r in rows if r["id"] == task_id), None)
        if not t or "a2a" not in t:
            raise A2AError(f"no A2A task {task_id}")
        if who != t["target"]:
            raise A2AError(f"{who} cannot answer a task sent to {t['target']}")
        if t["state"] not in agentbus.LIVE:
            raise A2AError(f"task {task_id} is already {t['state']}: its outcome stays")
        a = t["a2a"]
        problems = _valid(result, a["schema"])
        if problems:
            if a["retries_left"] > 0:
                a["retries_left"] -= 1
                t["state"] = "open"
                t["history"].append(f"{_iso(now)} answer refused ({'; '.join(problems)}), asked again")
            else:
                t["state"], t["outcome"] = "failed", clean("answer did not match the contract: " + "; ".join(problems), 300)
                t["history"].append(f"{_iso(now)} failed: {t['outcome']}")
        else:
            a["result"] = {k: (clean(v, 600) if isinstance(v, str) else v) for k, v in result.items() if k in SCHEMAS[a["schema"]]}
            t["state"], t["outcome"] = "done", clean(json.dumps(a["result"]), 300)
            t["history"].append(f"{_iso(now)} answered by {who}")
        agentbus._save(agentbus.FILE, rows)
        return view(t)


def cancel(task_id: str, who: str, now=None) -> dict:
    """Only the sender (or the doctor) cancels; a closed task stays as it is."""
    now = _now(now)
    with filelock.locked(agentbus.FILE):
        rows = agentbus._load(agentbus.FILE)
        t = next((r for r in rows if r["id"] == task_id), None)
        if not t or "a2a" not in t:
            raise A2AError(f"no A2A task {task_id}")
        if who not in (t["source"], "doctor"):
            raise A2AError(f"{who} cannot cancel a task sent by {t['source']}")
        if t["state"] in agentbus.LIVE:
            t["state"], t["outcome"] = "failed", f"canceled by {who}"
            t["a2a"]["canceled"] = True
            t["history"].append(f"{_iso(now)} canceled by {who}")
            agentbus._save(agentbus.FILE, rows)
        return view(t)


def expire(now=None) -> list[str]:
    """Tasks past their deadline: offered again with a new deadline while retries are left, failed otherwise. Returns the ids it touched."""
    now = _now(now)
    touched = []
    with filelock.locked(agentbus.FILE):
        rows = agentbus._load(agentbus.FILE)
        for t in rows:
            a = t.get("a2a")
            if not a or t["state"] not in agentbus.LIVE or dt.datetime.strptime(a["deadline"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc) > now:
                continue
            if a["retries_left"] > 0:
                a["retries_left"] -= 1
                a["deadline"] = _iso(now + dt.timedelta(seconds=a["timeout_s"]))
                t["state"] = "open"
                t["history"].append(f"{_iso(now)} no answer in time, asked again (deadline {a['deadline']})")
            else:
                t["state"], t["outcome"] = "failed", "no answer before the deadline"
                t["history"].append(f"{_iso(now)} failed: no answer before the deadline")
            touched.append(t["id"])
        if touched:
            agentbus._save(agentbus.FILE, rows)
    return touched


# ---- checked hand-overs between the stages of one video ----
def _check_script(data: dict, min_lines: int = 6, **_) -> tuple[list[str], dict]:
    """min_lines: 6 for a film; a Short's producer passes 3 (it never refused a short script before 21 Nov 2026; a Short's own length rules stay in scriptgen)."""
    lines = data.get("lines") or []
    bad = [i + 1 for i, l in enumerate(lines) if not str(l.get("text", "")).strip()]
    starts = [c.get("start_line", -1) for c in data.get("chapters") or []]
    problems = ([f"only {len(lines)} lines"] if len(lines) < min_lines else []) + ([f"empty lines {bad[:5]}"] if bad else [])
    if starts and (starts != sorted(set(starts)) or starts[0] != 0 or starts[-1] >= len(lines)):
        problems.append(f"chapter starts {starts[:12]} do not fit {len(lines)} lines")
    return problems, {"lines": len(lines), "words": sum(len(str(l.get("text", "")).split()) for l in lines), "chapters": len(starts)}


def _check_voice(data: dict, narration=None, durations=None, **_) -> tuple[list[str], dict]:
    d, n = list(durations or []), len(data.get("lines") or [])
    problems = []
    if not narration or not Path(narration).is_file() or Path(narration).stat().st_size == 0:
        problems.append("no narration file")
    if len(d) != n:
        problems.append(f"{len(d)} line timings for {n} lines")
    if any(not isinstance(x, (int, float)) or x <= 0 for x in d):
        problems.append("a line with no length")
    return problems, {"seconds": round(sum(x for x in d if isinstance(x, (int, float))), 1), "lines": len(d)}


def _check_visuals(data: dict, clips=None, min_share: float | None = None, **_) -> tuple[list[str], dict]:
    """Every scene has a picture file (a film). `min_share` (a Short): a scene may be a plain colour background as before (footage.enough_footage), but
    at least that share must have a picture, and every picture named must exist."""
    c, n = list(clips or []), len(data.get("lines") or [])
    gone = [i + 1 for i, p in enumerate(c) if p and not Path(p).exists()]
    empty = [i + 1 for i, p in enumerate(c) if not p]
    problems = [f"{len(c)} pictures for {n} lines"] if len(c) != n else []
    missing = sorted(gone + (empty if min_share is None else []))
    if missing:
        problems.append(f"scenes without a picture file: {missing[:8]}")
    if min_share is not None and c and (len(c) - len(empty)) / len(c) < min_share:
        problems.append(f"only {len(c) - len(empty)} of {len(c)} scenes have a picture")
    return problems, {"scenes": len(c), "unique": len({str(p) for p in c if p}), "colour_scenes": len(empty)}


def _check_render(data: dict, video=None, durations=None, probe=None, **_) -> tuple[list[str], dict]:
    if not video or not Path(video).is_file() or Path(video).stat().st_size == 0:
        return ["no video file"], {}
    try:
        if probe is None:
            import videoinspect

            probe = videoinspect.duration_of
        secs = float(probe(Path(video)))
    except Exception as e:
        return [f"the video cannot be read ({type(e).__name__})"], {}
    want = sum(durations or [])
    problems = [f"the video is {secs:.1f} s but the narration is {want:.1f} s"] if want and abs(secs - want) > max(3.0, 0.05 * want) else []
    return problems, {"seconds": round(secs, 1)}


STAGES = {  # stage: (from, to, check)
    "script": ("creator", "voice", _check_script),
    "voice": ("voice", "visuals", _check_voice),
    "visuals": ("visuals", "render", _check_visuals),
    "render": ("render", "reviewer", _check_render),
}


CONTRACTS = {  # what the receiving stage needs from the hand-over: the expected output of the sending stage
    "script": "lines[] with text (at least 6), chapters[] whose start_line ascends from 0 inside the script",
    "voice": "one narration file that is not empty, and one positive timing per line",
    "visuals": "one picture or clip per line, each file present (a Short may show a plain colour on at most 40% of its scenes)",
    "render": "one video file that decodes, as long as the narration (within 3 s or 5%)",
}


def _artifact(value) -> dict | None:
    """A reference to a file a stage made: its name, size and, for a small file, its SHA-256 (a 1 GB film is not hashed again here)."""
    try:
        p = Path(value)
        if not p.is_file():
            return {"name": p.name, "exists": False}
        size = p.stat().st_size
        ref = {"name": p.name, "bytes": size}
        if size <= 50_000_000:
            ref["sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
        return ref
    except (TypeError, OSError):
        return None


def _models(data: dict, stage: str) -> list[str]:
    if stage == "script":
        return [str(m) for m in (data.get("script_writers") or [data.get("script_model")]) if m][:4]
    if stage == "voice":
        return [str(data["voice_used"])] if data.get("voice_used") else []
    return []


def handoff(data: dict, stage: str, now=None, job: str | None = None, work=None, **facts) -> dict:
    """Check what a stage produced before the next stage may start, and record the hand-over in the video's record (data["handoffs"]).
    Raises HandoffError with the reasons when the result is not usable: the orchestrator verifies files and numbers, it does not take a stage's word.
    Each row carries the job (the video's folder), a task id (job/stage/attempt), the contract the receiver expects, references to the files handed over,
    the checkpoint's finished stages, the models that made the stage's output, and the validation result with its reasons (21 Nov 2026).
    These hand-overs are checks the orchestrator runs inside one production process, recorded as data; they are not messages between processes."""
    sender, receiver, check = STAGES[stage]
    problems, measured = check(data, **facts)
    attempt = 1 + sum(1 for h in data.get("handoffs") or [] if h.get("stage") == stage)
    files = {k: _artifact(v) for k, v in facts.items() if k in ("narration", "video") and v}
    if facts.get("clips") is not None:
        files["clips"] = {"count": len(facts["clips"]), "present": sum(1 for p in facts["clips"] if p and Path(p).exists())}
    stages = []
    if work is not None:
        try:
            stages = sorted(json.loads((Path(work) / "checkpoint.json").read_text()).get("stages") or {})
        except (OSError, ValueError):
            stages = []
    row = {"stage": stage, "from": sender, "to": receiver, "at": _iso(_now(now)), "ok": not problems, "measured": measured, "problems": problems,
           "job": job or "", "task": f"{job or 'video'}/{stage}/{attempt}", "expects": CONTRACTS[stage], "artifacts": files,
           "checkpoint": stages, "models": _models(data, stage), "validation": "passed" if not problems else "refused: " + "; ".join(problems)[:300]}
    data.setdefault("handoffs", []).append(row)
    if problems:
        raise HandoffError(f"{stage} hand-over refused: " + "; ".join(problems))
    return row
