"""The Agent2Agent (A2A) protocol, version 1.0, JSON-RPC binding. Standard library only.

What this follows (read on 10 Nov 2026 from a2a-protocol.org/latest/specification and from the official Python SDK 1.3.0's own type definitions and error table):
method names SendMessage, SendStreamingMessage, GetTask, ListTasks, CancelTask, SubscribeToTask, GetExtendedAgentCard (push-notification methods answer "not supported");
task states TASK_STATE_* with COMPLETED, FAILED, CANCELED and REJECTED terminal; results in Artifacts; error codes -32001 task not found, -32002 not cancelable, -32003 push not
supported, -32004 unsupported operation, -32009 version not supported, plus the JSON-RPC ones. A request that names a version other than 1.0 in `A2A-Version` is refused;
a request without the header is served as 1.0 (the spec asks clients to send it; being lenient here costs nothing).
Not implemented, said plainly: gRPC and HTTP+JSON bindings, push notifications, signed Agent Cards, tenants, the card's authenticated-extension model beyond one extended card.

Tasks live in the hub's SQLite file and belong to one account. A task of another account is "not found", never "forbidden" (the spec says not to reveal that a resource exists).
An agent is a handler `handler(ctx) -> {"state", "text", "artifacts"}`; an exception becomes a FAILED task with a generic message (details go to the audit table, not to the caller)."""
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from . import db

VERSION = "1.0"
PAGE_DEFAULT, PAGE_MAX = 50, 100
MAX_TEXT, MAX_PARTS = 20000, 20
WIRE = {"submitted": "TASK_STATE_SUBMITTED", "working": "TASK_STATE_WORKING", "completed": "TASK_STATE_COMPLETED", "failed": "TASK_STATE_FAILED",
        "canceled": "TASK_STATE_CANCELED", "rejected": "TASK_STATE_REJECTED", "input_required": "TASK_STATE_INPUT_REQUIRED", "auth_required": "TASK_STATE_AUTH_REQUIRED"}
FROM_WIRE = {v: k for k, v in WIRE.items()}
TERMINAL = {"completed", "failed", "canceled", "rejected"}
NOT_FOUND, NOT_CANCELABLE, PUSH_UNSUPPORTED, UNSUPPORTED, BAD_VERSION = -32001, -32002, -32003, -32004, -32009
PARSE, BAD_REQUEST, NO_METHOD, BAD_PARAMS, INTERNAL = -32700, -32600, -32601, -32602, -32603
PUSH_METHODS = {"CreateTaskPushNotificationConfig", "GetTaskPushNotificationConfig", "ListTaskPushNotificationConfigs", "DeleteTaskPushNotificationConfig"}


class RpcError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code, self.message = code, message


@dataclass
class Agent:
    id: str
    name: str
    description: str
    skills: list
    handler: Callable
    version: str = "1.0.0"


@dataclass
class Ctx:
    """What a handler is given. `text` and `data` are the person's (or another agent's) message and are untrusted input."""
    account_id: str
    agent: str
    context_id: str
    task_id: str
    text: str
    data: dict | None
    history: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    llm: Callable | None = None


def _iso(t: float) -> str:
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def agent_card(agent: Agent, base_url: str) -> dict:
    base = base_url.rstrip("/")
    return {
        "name": agent.name, "description": agent.description, "version": agent.version,
        "supportedInterfaces": [{"url": f"{base}/a2a/{agent.id}", "protocolBinding": "JSONRPC", "protocolVersion": VERSION}],
        "provider": {"organization": "Creator Hub", "url": base},
        "capabilities": {"streaming": True, "pushNotifications": False},
        "securitySchemes": {"hubSession": {"httpAuthSecurityScheme": {"scheme": "Bearer", "description": "A signed-in session token from the hub (cookie or Authorization header)."}}},
        "securityRequirements": [{"schemes": {"hubSession": {"list": []}}}],
        "defaultInputModes": ["text/plain", "application/json"], "defaultOutputModes": ["text/plain", "application/json"],
        "skills": agent.skills,
    }


def _agent_message(text: str, context_id: str, task_id: str) -> dict:
    return {"messageId": uuid.uuid4().hex, "role": "ROLE_AGENT", "contextId": context_id, "taskId": task_id, "parts": [{"text": text}]}


def _task_json(row, history_length: int | None = None) -> dict:
    status = {"state": WIRE[row["state"]], "timestamp": _iso(row["updated_at"])}
    if row["status_text"]:
        status["message"] = _agent_message(row["status_text"], row["context_id"], row["id"])
    hist = json.loads(row["history"])
    if history_length is not None:
        hist = hist[-history_length:] if history_length > 0 else []
    out = {"id": row["id"], "contextId": row["context_id"], "status": status, "artifacts": json.loads(row["artifacts"])}
    if hist:
        out["history"] = hist
    return out


def _load(con, account_id: str, task_id) -> "sqlite3.Row":
    row = con.execute("select * from tasks where id=? and account_id=?", (str(task_id or ""), account_id)).fetchone()
    if not row:
        raise RpcError(NOT_FOUND, "Task not found")
    return row


def _parts_of(message) -> tuple[str, dict | None]:
    if not isinstance(message, dict) or not isinstance(message.get("messageId"), str) or not message["messageId"] or message.get("role") != "ROLE_USER":
        raise RpcError(BAD_PARAMS, "message needs a messageId and role ROLE_USER")
    parts = message.get("parts")
    if not isinstance(parts, list) or not parts or len(parts) > MAX_PARTS:
        raise RpcError(BAD_PARAMS, f"message needs 1 to {MAX_PARTS} parts")
    texts, data = [], None
    for p in parts:
        if not isinstance(p, dict):
            raise RpcError(BAD_PARAMS, "bad part")
        if isinstance(p.get("text"), str):
            texts.append(p["text"])
        elif isinstance(p.get("data"), dict) and data is None:
            data = p["data"]
    text = "\n".join(texts)
    if len(text) > MAX_TEXT or len(json.dumps(data or {})) > MAX_TEXT:
        raise RpcError(BAD_PARAMS, f"message is longer than {MAX_TEXT} characters")
    if not text and data is None:
        raise RpcError(BAD_PARAMS, "message has no text or data")
    return text, data


def _artifact(a: dict) -> dict:
    parts = []
    if a.get("text"):
        parts.append({"text": str(a["text"])})
    if isinstance(a.get("data"), dict):
        parts.append({"data": a["data"]})
    return {"artifactId": uuid.uuid4().hex, "name": str(a.get("name") or "result")[:80], "parts": parts or [{"text": ""}]}


def _set(account_id: str, task_id: str, state: str, status_text: str = "", add_history: list | None = None, artifacts: list | None = None, now: float | None = None) -> None:
    now = time.time() if now is None else now
    with db.tx() as con:
        row = _load(con, account_id, task_id)
        hist = json.loads(row["history"]) + (add_history or [])
        arts = json.loads(row["artifacts"]) + (artifacts or [])
        con.execute("update tasks set state=?, status_text=?, updated_at=?, history=?, artifacts=? where id=?", (state, status_text, now, json.dumps(hist), json.dumps(arts), task_id))


def _execute(agents: dict, account_id: str, agent_id: str, params: dict, llm=None):
    """Run one message through an agent, yielding StreamResponse dicts in order: task, statusUpdate(working), artifactUpdate*, statusUpdate(final)."""
    agent = agents.get(agent_id)
    if not agent:
        raise RpcError(NO_METHOD, "Unknown agent")
    message = (params or {}).get("message")
    text, data = _parts_of(message)
    now = time.time()
    task_id, context_id = message.get("taskId"), str(message.get("contextId") or "")[:64] or uuid.uuid4().hex
    user_msg = {"messageId": message["messageId"][:64], "role": "ROLE_USER", "parts": message["parts"]}
    with db.tx() as con:
        if task_id:
            row = _load(con, account_id, task_id)
            if row["agent"] != agent_id or row["state"] != "input_required":
                raise RpcError(UNSUPPORTED, "Task is not waiting for input")
            context_id, history = row["context_id"], json.loads(row["history"])
            con.execute("update tasks set state='working', updated_at=? where id=?", (now, task_id))
        else:
            task_id, history = uuid.uuid4().hex, []
            con.execute("insert into tasks(id,account_id,agent,context_id,state,created_at,updated_at,history) values(?,?,?,?,?,?,?,?)",
                        (task_id, account_id, agent_id, context_id, "submitted", now, now, "[]"))
        row = _load(con, account_id, task_id)
    _set(account_id, task_id, row["state"], "", [{**user_msg, "contextId": context_id, "taskId": task_id}], now=now)
    with db.read() as con:
        first = _task_json(_load(con, account_id, task_id))
    yield {"task": first}  # no connection is held across a yield: a background run continues in another thread
    _set(account_id, task_id, "working")
    yield {"statusUpdate": {"taskId": task_id, "contextId": context_id, "status": {"state": WIRE["working"], "timestamp": _iso(time.time())}}}
    ctx = Ctx(account_id, agent_id, context_id, task_id, text, data, history, message.get("metadata") if isinstance(message.get("metadata"), dict) else {}, llm)
    try:
        res = agent.handler(ctx)
        state = res.get("state") if res.get("state") in WIRE else "failed"
        reply = str(res.get("text") or "")[:MAX_TEXT]
        arts = [_artifact(a) for a in (res.get("artifacts") or [])[:10] if isinstance(a, dict)]
    except Exception as ex:  # the caller gets a generic line; the type goes to the audit table
        with db.tx() as con:
            con.execute("insert into audit(at,account_id,event,outcome,detail) values(?,?,?,?,?)", (time.time(), account_id, "agent_error", "failed", f"{agent_id}:{type(ex).__name__}"))
        state, reply, arts = "failed", "The agent could not finish this task.", []
    if state in ("submitted", "working"):
        state = "failed"
    for a in arts:
        yield {"artifactUpdate": {"taskId": task_id, "contextId": context_id, "artifact": a, "lastChunk": True}}
    _set(account_id, task_id, state, reply, [_agent_message(reply, context_id, task_id)] if reply else [], arts)
    yield {"statusUpdate": {"taskId": task_id, "contextId": context_id, "status": {"state": WIRE[state], "timestamp": _iso(time.time()),
                                                                                  **({"message": _agent_message(reply, context_id, task_id)} if reply else {})}}}


def send(agents: dict, account_id: str, agent_id: str, params: dict, llm=None) -> dict:
    """SendMessage: run to the end (or in the background with returnImmediately) and return the task."""
    gen = _execute(agents, account_id, agent_id, params, llm)
    first = next(gen)["task"]
    cfg = (params or {}).get("configuration") or {}
    if cfg.get("returnImmediately") is True:
        threading.Thread(target=lambda: [None for _ in gen], daemon=True).start()
        return first
    for _ in gen:
        pass
    with db.read() as con:
        return _task_json(_load(con, account_id, first["id"]), cfg.get("historyLength") if isinstance(cfg.get("historyLength"), int) else None)


def _list(account_id: str, p: dict) -> dict:
    size = p.get("pageSize", PAGE_DEFAULT)
    size = PAGE_DEFAULT if not isinstance(size, int) or size < 1 else min(size, PAGE_MAX)
    try:
        offset = int(p.get("pageToken") or 0)
    except (TypeError, ValueError):
        raise RpcError(BAD_PARAMS, "bad pageToken")
    where, args = "account_id=?", [account_id]
    if p.get("contextId"):
        where += " and context_id=?"
        args.append(str(p["contextId"]))
    if p.get("status") in FROM_WIRE:
        where += " and state=?"
        args.append(FROM_WIRE[p["status"]])
    with db.read() as con:
        total = con.execute(f"select count(*) from tasks where {where}", args).fetchone()[0]
        rows = con.execute(f"select * from tasks where {where} order by updated_at desc, id limit ? offset ?", [*args, size, max(offset, 0)]).fetchall()
    nxt = str(offset + size) if offset + size < total else ""
    return {"tasks": [_task_json(r, p.get("historyLength") if isinstance(p.get("historyLength"), int) else 0) for r in rows], "nextPageToken": nxt, "pageSize": size, "totalSize": total}


def _cancel(account_id: str, task_id) -> dict:
    with db.tx() as con:
        row = _load(con, account_id, task_id)
        if row["state"] in TERMINAL:
            raise RpcError(NOT_CANCELABLE, "Task is already finished")
        con.execute("update tasks set state='canceled', updated_at=? where id=?", (time.time(), row["id"]))
        return _task_json(_load(con, account_id, task_id))


def handle(agents: dict, agent_id: str, account_id: str, body, version: str | None, llm=None, base_url: str = ""):
    """One JSON-RPC request from a signed-in account. Returns a response dict, or (for SendStreamingMessage and SubscribeToTask) a generator of response dicts."""
    rid = body.get("id") if isinstance(body, dict) else None
    err = lambda code, msg: {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": msg}}
    ok = lambda result: {"jsonrpc": "2.0", "id": rid, "result": result}
    if not isinstance(body, dict) or body.get("jsonrpc") != "2.0" or not isinstance(body.get("method"), str) or not (rid is None or isinstance(rid, (str, int))):
        return err(BAD_REQUEST, "Invalid Request")
    if version is not None and str(version).strip() != VERSION:
        return err(BAD_VERSION, f"Version not supported; this server speaks {VERSION}")
    if agent_id not in agents:
        return err(NO_METHOD, "Unknown agent")
    method, params = body["method"], body.get("params") or {}
    if not isinstance(params, dict):
        return err(BAD_PARAMS, "params must be an object")
    try:
        if method == "SendMessage":
            return ok({"task": send(agents, account_id, agent_id, params, llm)})
        if method == "SendStreamingMessage":
            def stream():
                try:
                    for ev in _execute(agents, account_id, agent_id, params, llm):
                        yield ok(ev)
                except RpcError as e:
                    yield err(e.code, e.message)
            first_check = _parts_of(params.get("message"))  # a bad request answers once, not as a stream
            del first_check
            return stream()
        if method == "GetTask":
            with db.read() as con:
                return ok(_task_json(_load(con, account_id, params.get("id")), params.get("historyLength") if isinstance(params.get("historyLength"), int) else None))
        if method == "ListTasks":
            return ok(_list(account_id, params))
        if method == "CancelTask":
            return ok(_cancel(account_id, params.get("id")))
        if method == "SubscribeToTask":
            with db.read() as con:
                row = _load(con, account_id, params.get("id"))
            if row["state"] in TERMINAL:
                raise RpcError(UNSUPPORTED, "Task is finished; use GetTask")
            return iter([ok({"task": _task_json(row)})])
        if method == "GetExtendedAgentCard":
            return ok(agent_card(agents[agent_id], base_url or "https://hub.invalid"))
        if method in PUSH_METHODS:
            raise RpcError(PUSH_UNSUPPORTED, "Push notifications are not supported")
        raise RpcError(NO_METHOD, "Method not found")
    except RpcError as e:
        return err(e.code, e.message)
