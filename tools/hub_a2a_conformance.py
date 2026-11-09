#!/usr/bin/env python3
"""Does the hub speak A2A 1.0 to the OFFICIAL client? Runs the hub's real server on a free port and drives it with the `a2a-sdk` Python client (card discovery, SendMessage,
streaming, GetTask, ListTasks, CancelTask, the INPUT_REQUIRED round trip, an unauthorized call and a wrong-version call).

Needs the SDK, which the studio does not install: create a scratch environment and run it there, e.g.
  python3 -m venv /tmp/a2av && /tmp/a2av/bin/pip install "a2a-sdk[http-server]==1.3.0"
  /tmp/a2av/bin/python tools/hub_a2a_conformance.py
The test tests/test_hub_conformance.py runs it when HUB_A2A_SDK_PYTHON names such an interpreter. Prints one line per check; exit code 1 if any failed."""
import asyncio
import re
import sys
import tempfile
import threading
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))  # last, not first: the repo has its own packaging.py that would hide the real library the SDK needs

import httpx  # noqa: E402
from google.protobuf import json_format  # noqa: E402
from google.protobuf.struct_pb2 import Value  # noqa: E402
from a2a.client import ClientConfig, create_client  # noqa: E402
from a2a.types.a2a_pb2 import (CancelTaskRequest, GetTaskRequest, ListTasksRequest, Message, Part, Role, SendMessageConfiguration,  # noqa: E402
                               SendMessageRequest, TaskState)

from hub import a2a, agents, auth, db, server  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))


def question(agent_handler):
    return a2a.Agent("quiz", "Quiz", "Asks a follow-up question, then answers.", [{"id": "quiz", "name": "Quiz", "description": "Two-step conversation", "tags": ["test"]}], agent_handler)


def quiz(ctx):
    if len(ctx.history) <= 1:
        return {"state": "input_required", "text": "Which platform?"}
    return {"state": "completed", "text": f"Plan for {ctx.text}", "artifacts": [{"name": "plan", "text": f"Plan for {ctx.text}", "data": {"platform": ctx.text}}]}


def msg(text: str, **kw) -> Message:
    return Message(message_id=kw.pop("message_id", "m-" + text[:8]), role=Role.ROLE_USER, parts=[Part(text=text)], **kw)


async def run(base: str, token: str) -> None:
    http = httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=20)
    for streaming in (False, True):
        client = await create_client(f"{base}/a2a/publisher", ClientConfig(httpx_client=http, streaming=streaming))
        card = await client.get_extended_agent_card(__import__("a2a.types.a2a_pb2", fromlist=["x"]).GetExtendedAgentCardRequest())
        check(f"card parsed by the SDK (streaming={streaming})", card.name == "Publisher" and len(card.skills) == 1)
        value = json_format.ParseDict({"platform": "tiktok", "approved_by_creator": True, "title": "T"}, Value())
        req = SendMessageRequest(message=Message(message_id="m1", role=Role.ROLE_USER, parts=[Part(data=value)]))
        events = [ev async for ev in client.send_message(req)]
        last_task = [e.task for e in events if e.HasField("task")]
        states = [e.status_update.status.state for e in events if e.HasField("status_update")]
        arts = [e.artifact_update for e in events if e.HasField("artifact_update")]
        final = (last_task[-1].status.state if last_task else (states[-1] if states else None))
        if not streaming:
            check("SendMessage returns a completed task with an artifact", final == TaskState.TASK_STATE_COMPLETED and last_task[-1].artifacts, str([str(e)[:80] for e in events]))
        else:
            check("SendStreamingMessage: task, working, artifact, completed", TaskState.TASK_STATE_WORKING in states and states[-1] == TaskState.TASK_STATE_COMPLETED and len(arts) == 1, f"{states} {len(arts)}")
        await client.close()
    quiz_client = await create_client(f"{base}/a2a/quiz", ClientConfig(httpx_client=http, streaming=False))
    first = [e async for e in quiz_client.send_message(SendMessageRequest(message=msg("plan my week")))][-1].task
    check("INPUT_REQUIRED is reported", first.status.state == TaskState.TASK_STATE_INPUT_REQUIRED)
    second = [e async for e in quiz_client.send_message(SendMessageRequest(message=msg("tiktok", message_id="m2", task_id=first.id, context_id=first.context_id)))][-1].task
    check("the same task continues to COMPLETED", second.id == first.id and second.status.state == TaskState.TASK_STATE_COMPLETED and len(second.history) >= 4)
    got = await quiz_client.get_task(GetTaskRequest(id=first.id))
    check("GetTask", got.id == first.id and got.status.state == TaskState.TASK_STATE_COMPLETED)
    lst = await quiz_client.list_tasks(ListTasksRequest(context_id=first.context_id))
    check("ListTasks by context", lst.total_size == 1)
    waiting = [e async for e in quiz_client.send_message(SendMessageRequest(message=msg("another one", message_id="m3")))][-1].task
    canceled = await quiz_client.cancel_task(CancelTaskRequest(id=waiting.id))
    check("CancelTask", canceled.status.state == TaskState.TASK_STATE_CANCELED)
    bg = [e async for e in quiz_client.send_message(SendMessageRequest(message=msg("later", message_id="m4"), configuration=SendMessageConfiguration(return_immediately=True)))][-1].task
    check("returnImmediately gives a task id at once", bool(bg.id))
    await quiz_client.close()
    raw = await httpx.AsyncClient().post(f"{base}/a2a/publisher", json={"jsonrpc": "2.0", "id": 1, "method": "ListTasks"})
    check("no credentials gives 401", raw.status_code == 401)
    raw = await http.post(f"{base}/a2a/publisher", json={"jsonrpc": "2.0", "id": 1, "method": "ListTasks"}, headers={"A2A-Version": "0.3"})
    check("a wrong A2A-Version is refused with -32009", raw.json().get("error", {}).get("code") == -32009)
    await http.aclose()


def main() -> int:
    tmp = Path(tempfile.mkdtemp())
    db.PATH = tmp / "hub.db"
    auth.SECRET_FILE = tmp / "secret"
    import os
    os.environ["HUB_INSECURE_DEV"] = "1"
    server.Hub.agents = {**agents.AGENTS, "quiz": question(quiz)}

    class Capture:
        body = ""

        def send(self, to, subject, body):
            Capture.body = body

    auth.request_code("sdk@example.com", "127.0.0.1", mailer=Capture())
    token = auth.verify_code("sdk@example.com", re.search(r"\b(\d{8})\b", Capture.body).group(1), "127.0.0.1")["token"]
    srv = server.make_server("127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        asyncio.run(run(f"http://127.0.0.1:{srv.server_address[1]}", token))
    except Exception as e:  # a crash is a failed run, with its reason
        check("the run completed", False, f"{type(e).__name__}: {e}"[:300])
    finally:
        srv.shutdown()
    failed = [r for r in RESULTS if not r[1]]
    print(f"{len(RESULTS) - len(failed)} passed, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
