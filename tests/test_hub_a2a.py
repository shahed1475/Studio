import time

import pytest

from hub import a2a, auth, db


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "PATH", tmp_path / "hub" / "hub.db")
    monkeypatch.setattr(auth, "SECRET_FILE", tmp_path / "hub" / "secret")


def mk_account(email):
    with db.tx() as con:
        aid = auth.uuid.uuid4().hex
        con.execute("insert into accounts(id,email,created_at) values(?,?,?)", (aid, email, 1.0))
    return aid


def echo(ctx):
    if ctx.text == "need more":
        return {"state": "input_required", "text": "Tell me more."}
    if ctx.text == "no":
        return {"state": "rejected", "text": "I will not do that."}
    if ctx.text == "boom":
        raise RuntimeError("secret internal detail /home/x")
    return {"state": "completed", "text": f"echo: {ctx.text}", "artifacts": [{"name": "answer", "text": ctx.text.upper(), "data": {"n": len(ctx.text)}}]}


AGENTS = {"echo": a2a.Agent("echo", "Echo", "Repeats what it is told.", [{"id": "echo", "name": "Echo", "description": "Repeat text", "tags": ["test"]}], echo)}


def rpc(account, method, params=None, agent="echo", version=None, rid=1):
    return a2a.handle(AGENTS, agent, account, {"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}}, version)


def msg(text, **kw):
    return {"message": {"messageId": "m1", "role": "ROLE_USER", "parts": [{"text": text}], **kw}}


def test_card_has_the_fields_a_client_needs():
    c = a2a.agent_card(AGENTS["echo"], "https://hub.example")
    i = c["supportedInterfaces"][0]
    assert i == {"url": "https://hub.example/a2a/echo", "protocolBinding": "JSONRPC", "protocolVersion": "1.0"}
    assert c["capabilities"]["streaming"] is True and c["capabilities"]["pushNotifications"] is False
    s = c["skills"][0]
    assert all(s[k] for k in ("id", "name", "description", "tags")) and c["securityRequirements"] and "hubSession" in c["securitySchemes"]


def test_send_message_runs_the_agent_and_stores_the_task_for_that_account_only():
    a, b = mk_account("a@x.com"), mk_account("b@x.com")
    r = rpc(a, "SendMessage", msg("hello"))
    t = r["result"]["task"]
    assert t["status"]["state"] == "TASK_STATE_COMPLETED" and t["artifacts"][0]["parts"][0]["text"] == "HELLO"
    assert t["status"]["message"]["parts"][0]["text"] == "echo: hello" and t["status"]["message"]["role"] == "ROLE_AGENT"
    got = rpc(a, "GetTask", {"id": t["id"]})["result"]
    assert got["id"] == t["id"] and len(got["history"]) == 2
    assert rpc(b, "GetTask", {"id": t["id"]})["error"]["code"] == -32001  # someone else's task looks like no task
    assert rpc(b, "ListTasks")["result"]["tasks"] == []
    assert rpc(a, "GetTask", {"id": "nope"})["error"]["code"] == -32001


def test_input_required_then_continue_and_rejected_and_failed_do_not_leak():
    a = mk_account("a@x.com")
    t = rpc(a, "SendMessage", msg("need more"))["result"]["task"]
    assert t["status"]["state"] == "TASK_STATE_INPUT_REQUIRED"
    done = rpc(a, "SendMessage", msg("here it is", taskId=t["id"], contextId=t["contextId"]))["result"]["task"]
    assert done["id"] == t["id"] and done["status"]["state"] == "TASK_STATE_COMPLETED" and len(done["history"]) == 4
    assert rpc(a, "SendMessage", msg("again", taskId=t["id"]))["error"]["code"] == -32004  # a finished task takes no more messages
    assert rpc(a, "SendMessage", msg("no"))["result"]["task"]["status"]["state"] == "TASK_STATE_REJECTED"
    f = rpc(a, "SendMessage", msg("boom"))["result"]["task"]
    assert f["status"]["state"] == "TASK_STATE_FAILED" and "secret" not in str(f) and "/home" not in str(f)


def test_errors_use_the_codes_clients_expect():
    a = mk_account("a@x.com")
    assert rpc(a, "Nope")["error"]["code"] == -32601
    assert rpc(a, "SendMessage", {"message": {"role": "ROLE_USER", "parts": []}})["error"]["code"] == -32602
    assert rpc(a, "SendMessage", {"message": {"messageId": "m", "role": "ROLE_USER", "parts": [{"text": "x" * 30000}]}})["error"]["code"] == -32602
    assert rpc(a, "CreateTaskPushNotificationConfig", {})["error"]["code"] == -32003
    assert a2a.handle(AGENTS, "echo", a, "not a dict", None)["error"]["code"] == -32600
    assert a2a.handle(AGENTS, "echo", a, {"jsonrpc": "1.0", "id": 1, "method": "GetTask"}, None)["error"]["code"] == -32600
    assert rpc(a, "SendMessage", msg("x"), agent="ghost")["error"]["code"] == -32601
    assert rpc(a, "SendMessage", msg("x"), version="0.3")["error"]["code"] == -32009
    assert rpc(a, "SendMessage", msg("x"), version="1.0")["result"]
    assert "result" in rpc(a, "SendMessage", msg("x"), version=None)


def test_cancel_and_list():
    a = mk_account("a@x.com")
    done = rpc(a, "SendMessage", msg("hi"))["result"]["task"]
    waiting = rpc(a, "SendMessage", msg("need more", contextId="ctx-1"))["result"]["task"]
    assert rpc(a, "CancelTask", {"id": done["id"]})["error"]["code"] == -32002
    assert rpc(a, "CancelTask", {"id": waiting["id"]})["result"]["status"]["state"] == "TASK_STATE_CANCELED"
    ls = rpc(a, "ListTasks", {"contextId": "ctx-1"})["result"]
    assert [t["id"] for t in ls["tasks"]] == [waiting["id"]] and ls["totalSize"] == 1
    allt = rpc(a, "ListTasks", {"pageSize": 1})["result"]
    assert len(allt["tasks"]) == 1 and allt["nextPageToken"]
    nxt = rpc(a, "ListTasks", {"pageSize": 1, "pageToken": allt["nextPageToken"]})["result"]
    assert nxt["tasks"][0]["id"] != allt["tasks"][0]["id"]
    assert rpc(a, "ListTasks", {"pageSize": 1000})["result"]["pageSize"] == a2a.PAGE_MAX


def test_streaming_events_come_in_order():
    a = mk_account("a@x.com")
    events = list(a2a.handle(AGENTS, "echo", a, {"jsonrpc": "2.0", "id": 7, "method": "SendStreamingMessage", "params": msg("stream me")}, None))
    kinds = [next(iter(e["result"])) for e in events]
    assert kinds == ["task", "statusUpdate", "artifactUpdate", "statusUpdate"]
    assert events[0]["result"]["task"]["status"]["state"] == "TASK_STATE_SUBMITTED"
    assert events[1]["result"]["statusUpdate"]["status"]["state"] == "TASK_STATE_WORKING"
    assert events[-1]["result"]["statusUpdate"]["status"]["state"] == "TASK_STATE_COMPLETED" and all(e["id"] == 7 for e in events)
    tid = events[0]["result"]["task"]["id"]
    assert a2a.handle(AGENTS, "echo", a, {"jsonrpc": "2.0", "id": 8, "method": "SubscribeToTask", "params": {"id": tid}}, None)["error"]["code"] == -32004  # finished tasks cannot be subscribed to


def test_return_immediately_gives_a_task_that_finishes_later():
    a = mk_account("a@x.com")
    r = rpc(a, "SendMessage", {**msg("later"), "configuration": {"returnImmediately": True}})["result"]["task"]
    assert r["status"]["state"] in ("TASK_STATE_SUBMITTED", "TASK_STATE_WORKING", "TASK_STATE_COMPLETED")
    for _ in range(50):
        if rpc(a, "GetTask", {"id": r["id"]})["result"]["status"]["state"] == "TASK_STATE_COMPLETED":
            break
        time.sleep(0.05)
    else:
        raise AssertionError("never finished")


def test_extended_card_is_served_to_a_signed_in_account():
    a = mk_account("a@x.com")
    assert rpc(a, "GetExtendedAgentCard")["result"]["name"] == "Echo"
