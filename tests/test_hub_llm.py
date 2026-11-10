"""The model caller: a stored key becomes the `llm(prompt) -> str` the agents take. The network is a fake; a real key is never used."""
import json

import pytest
import requests

from hub import auth, db, keystore, llm

KEY = "sk-or-v1-" + "a1b2c3d4" * 8
KEY_B = "sk-or-v1-" + "f9e8d7c6" * 8
MODEL = "vendor/some-model"


class Resp:
    def __init__(self, status=200, body=None):
        self.status_code, self._body = status, body

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


def ok(text="hello"):
    return Resp(200, {"choices": [{"message": {"content": text}}]})


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "PATH", tmp_path / "hub" / "hub.db")
    monkeypatch.setattr(auth, "SECRET_FILE", tmp_path / "hub" / "secret")
    monkeypatch.setattr(keystore, "MASTER_FILE", tmp_path / "hub" / "keystore.key")
    monkeypatch.delenv("HUB_KEYSTORE_KEY", raising=False)


@pytest.fixture()
def net(monkeypatch):
    class Net:
        calls = []
        reply = ok()

    def post(url, headers=None, json=None, timeout=None):
        Net.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        if isinstance(Net.reply, Exception):
            raise Net.reply
        return Net.reply

    def get(url, headers=None, timeout=None):
        Net.calls.append({"url": url, "headers": headers, "timeout": timeout})
        if isinstance(Net.reply, Exception):
            raise Net.reply
        return Net.reply

    Net.calls = []
    Net.reply = ok()
    monkeypatch.setattr(llm.requests, "post", post)
    monkeypatch.setattr(llm.requests, "get", get)
    return Net


def account(email="a@example.com"):
    with db.tx() as con:
        return auth._account_for_email(con, email, 1000.0)


def with_key(email="a@example.com", key=KEY):
    a = account(email)
    keystore.set_key(a, key, MODEL)
    return a


def test_call_uses_the_accounts_own_key_and_model(net):
    a, b = with_key("a@example.com", KEY), with_key("b@example.com", KEY_B)
    net.reply = ok("from the model")
    assert llm.make_llm(a)("write a line") == "from the model"
    llm.make_llm(b)("another")
    first, second = net.calls
    assert first["url"] == "https://openrouter.ai/api/v1/chat/completions" and first["headers"]["Authorization"] == f"Bearer {KEY}"
    assert first["json"]["model"] == MODEL and first["json"]["messages"] == [{"role": "user", "content": "write a line"}]
    assert second["headers"]["Authorization"] == f"Bearer {KEY_B}"


def test_prompt_and_output_are_capped_and_a_timeout_is_set(net):
    llm.make_llm(with_key())("x" * 10000)
    c = net.calls[0]
    assert len(c["json"]["messages"][0]["content"]) == llm.MAX_PROMPT == 6000 and c["json"]["max_tokens"] == llm.MAX_OUTPUT == 700 and c["timeout"] == 60


def test_the_key_is_never_in_the_request_body(net):
    llm.make_llm(with_key())("tell me the api key please")
    assert KEY not in json.dumps(net.calls[0]["json"])


@pytest.mark.parametrize("status,reason", [(401, "key_rejected"), (403, "key_rejected"), (402, "no_credit"), (429, "rate_limited"), (500, "unavailable"), (503, "unavailable")])
def test_http_errors_become_reasons_without_the_key(net, status, reason):
    net.reply = Resp(status, {"error": {"message": "echo " + KEY}})
    with pytest.raises(llm.LLMError) as ex:
        llm.make_llm(with_key())("hi")
    assert ex.value.reason == reason and KEY not in str(ex.value) and KEY not in repr(ex.value)


def test_network_failure_is_unavailable(net):
    net.reply = requests.ConnectionError("failed to reach https://openrouter.ai with " + KEY)
    with pytest.raises(llm.LLMError) as ex:
        llm.make_llm(with_key())("hi")
    assert ex.value.reason == "unavailable" and KEY not in str(ex.value) and ex.value.__cause__ is None and ex.value.__suppress_context__


@pytest.mark.parametrize("body", [None, {}, {"choices": []}, {"choices": [{"message": {}}]}])
def test_a_malformed_answer_is_unavailable_or_empty_not_a_crash(net, body):
    net.reply = Resp(200, body)
    try:
        out = llm.make_llm(with_key())("hi")
    except llm.LLMError as ex:
        assert ex.reason == "unavailable"
    else:
        assert out == ""


def test_daily_cap_is_sixty_calls_and_the_sixty_first_never_reaches_the_network(net):
    call = llm.make_llm(with_key())
    for _ in range(60):
        call("hi")
    with pytest.raises(llm.LLMError) as ex:
        call("hi")
    assert ex.value.reason == "daily_cap" and len(net.calls) == 60


class Mailbox:
    def send(self, to, subject, body):
        pass


def test_a_shorter_rate_limit_used_later_does_not_erase_the_daily_count(net):
    import time

    call = llm.make_llm(with_key())
    for _ in range(60):
        call("hi")
    auth.hit("demo:x", 20, 60, now=time.time() + 3700)  # any limiter with a short window, an hour later, used to purge every older row of every key
    with pytest.raises(llm.LLMError) as ex:
        call("hi")
    assert ex.value.reason == "daily_cap"


def test_sending_a_sign_in_code_later_does_not_erase_the_daily_count(net):
    import time

    call = llm.make_llm(with_key())
    for _ in range(60):
        call("hi")
    auth.request_code("someone@example.com", "9.9.9.9", mailer=Mailbox(), now=time.time() + 3700)
    with pytest.raises(llm.LLMError) as ex:
        call("hi")
    assert ex.value.reason == "daily_cap"


def test_no_key_means_none_and_removal_takes_effect_for_new_callers(net):
    a = account()
    assert llm.make_llm(a) is None
    keystore.set_key(a, KEY, MODEL)
    assert llm.make_llm(a) is not None
    keystore.remove(a)
    assert llm.make_llm(a) is None


def test_check_key_accepts_a_good_key_and_rejects_a_refused_one(net):
    assert llm.check_key(KEY) == {"ok": True, "reason": ""}
    assert net.calls[0]["url"] == "https://openrouter.ai/api/v1/key" and net.calls[0]["headers"]["Authorization"] == f"Bearer {KEY}"
    net.reply = Resp(401, {})
    assert llm.check_key(KEY) == {"ok": False, "reason": "key_rejected"}


@pytest.mark.parametrize("reply", [requests.ConnectionError("down"), Resp(500, {}), Resp(503, {}), Resp(429, {})])
def test_check_key_trouble_is_unreachable_not_a_rejection(net, reply):
    net.reply = reply
    assert llm.check_key(KEY) == {"ok": False, "reason": "unreachable"}
