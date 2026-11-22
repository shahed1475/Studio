"""An OpenRouter 401 is the key being refused, not the model (22 Nov 2026: the FreeLLMAPI key sat in the OpenRouter field, 26 models answered 401,
each counted against its own health, and the fact-check was retried for a day with nobody told the key was the problem)."""
import datetime as dt
import json

import pytest
import requests

import agentlog
import dashboard
import freemodels
import llm
import scriptgen

NOW = dt.datetime(2026, 11, 22, 17, 0, tzinfo=dt.timezone.utc)


def _http(code, text):
    r = requests.Response()
    r.status_code = code
    r._content = text.encode()
    return requests.HTTPError(f"{code} error", response=r)


@pytest.fixture
def routed(tmp_path, monkeypatch):
    f = tmp_path / "settings.json"
    f.write_text(json.dumps({"extra_llm_on": True, "extra_llm_url": "http://127.0.0.1:31415/v1", "extra_llm_local": True, "extra_llm_key": "fl-KEY-0123456789",
                             "extra_llm_models": {"review": "own-judge"}}))
    monkeypatch.setattr(llm, "SETTINGS_FILE", f)
    monkeypatch.setattr(llm, "USAGE_FILE", tmp_path / "llm_usage.json")
    monkeypatch.setattr(llm, "gemini_key", lambda: "")
    monkeypatch.setattr(freemodels, "refresh", lambda now: None)
    monkeypatch.setattr(freemodels, "choose", lambda role, now, avoid=None, n=4: ["or/a:free", "or/b:free"])
    monkeypatch.setattr(freemodels, "remaining", lambda *a, **k: 500)
    monkeypatch.setattr(freemodels, "requests_today", lambda *a, **k: 0)
    monkeypatch.setattr(freemodels, "count_request", lambda *a, **k: None)
    monkeypatch.setattr(freemodels, "available", lambda mid, now: True)
    marks, alerts, calls = [], [], []
    monkeypatch.setattr(freemodels, "record", lambda mid, ok, *a, **k: marks.append((mid, ok)))
    monkeypatch.setattr(agentlog, "event", lambda kind, title, detail="", **k: alerts.append((kind, title, k.get("notify"))))
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)

    def fake_post(payload, key):
        calls.append(payload["model"])
        if payload["model"].startswith("extra:"):
            return {"choices": [{"message": {"content": '{"ok": true}'}}], "usage": {}}
        raise _http(401, '{"error":{"message":"User not found.","code":401}}')

    monkeypatch.setattr(llm, "_post", fake_post)
    return marks, alerts, calls


def test_a_401_marks_the_provider_refused_once_and_never_the_model(routed):
    marks, alerts, calls = routed
    assert llm._ask_free("or/a:free", "p", "review", llm.load_config(), "sk-or-dead", NOW) is None
    rec = llm.openrouter_refused(NOW, "sk-or-dead")
    assert rec and rec["status"] == 401 and "User not found" in rec["said"]
    assert ("or/a:free", False) not in marks                       # the model's own health is left alone: it was never the model
    assert [a for a in alerts if a[1] == "OpenRouter refused the studio's key" and a[2]]  # the owner is told, as an alert
    assert llm._ask_free("or/b:free", "p", "review", llm.load_config(), "sk-or-dead", NOW) is None
    assert calls == ["or/a:free"]                                   # the second OpenRouter model is not asked at all while the key stands refused
    assert len([a for a in alerts if a[1] == "OpenRouter refused the studio's key"]) == 1  # one alert, not one per model


def test_while_refused_the_round_goes_to_the_owners_own_models_without_asking_openrouter(routed):
    marks, alerts, calls = routed
    llm._openrouter_refused_now(NOW, "sk-or-dead", 401, "User not found.")
    out = llm._free_chat("p", "review", llm.load_config(), "sk-or-dead", NOW)
    assert out == {"ok": True}
    assert not [c for c in calls if c.startswith("or/")]


def test_a_new_key_is_not_held_to_the_old_keys_refusal_and_the_hold_expires(routed):
    llm._openrouter_refused_now(NOW, "sk-or-dead", 401, "User not found.")
    assert llm.openrouter_refused(NOW, "sk-or-new") is None
    assert llm.openrouter_refused(NOW + dt.timedelta(seconds=llm.OR_REFUSED_HOLD + 1), "sk-or-dead") is None


def test_the_refusal_record_never_holds_the_key(routed):
    llm._openrouter_refused_now(NOW, "sk-or-SECRETVALUE123", 401, "bad key sk-or-SECRETVALUE123")
    assert "SECRETVALUE" not in llm._or_auth_file().read_text()


def test_a_failed_fact_check_names_the_judges_that_were_asked_and_why(monkeypatch):
    def failing(prompt):
        llm._attempt("gemini:gemini-x", "answered")
        llm._attempt("extra:nemotron", "down (502)")
        raise llm.ModelUnavailable("no model")

    monkeypatch.setattr(scriptgen, "_review_chat", failing)
    with pytest.raises(ValueError) as e:
        scriptgen.unsupported([{"text": "Line one."}], "SOURCE TEXT")
    msg = str(e.value)
    assert "could not be fact-checked" in msg and "extra:nemotron: down (502)" in msg and "gemini:gemini-x: answered" in msg


def test_a_key_is_saved_only_in_its_own_services_field():
    with pytest.raises(ValueError, match="not an OpenRouter key"):
        dashboard._check_key_field({}, "openrouter_key", "fl-0123456789abcdef")
    with pytest.raises(ValueError, match="already saved as the extra model provider key"):
        dashboard._check_key_field({"extra_llm_key": "sk-or-v1-same"}, "openrouter_key", "sk-or-v1-same")
    with pytest.raises(ValueError, match="already saved as the OpenRouter key"):
        dashboard._check_key_field({"openrouter_key": "abcdef0123456789"}, "extra_llm_key", "abcdef0123456789")
    dashboard._check_key_field({"extra_llm_key": "other-key-0123"}, "openrouter_key", "sk-or-v1-fine")  # a real OpenRouter key passes


@pytest.mark.parametrize("reply", [{}, {"verdict": "fine"}, {"unsupported": "none"}, ["x"], None])
def test_a_judge_reply_without_the_verdict_never_passes_as_nothing_unsupported(monkeypatch, reply):
    monkeypatch.setattr(scriptgen, "_review_chat", lambda prompt: reply)
    with pytest.raises(ValueError, match="could not be fact-checked"):
        scriptgen.unsupported([{"text": "Line one."}], "SOURCE TEXT")


def test_an_empty_verdict_list_is_a_real_pass(monkeypatch):
    monkeypatch.setattr(scriptgen, "_review_chat", lambda prompt: {"unsupported": []})
    assert scriptgen.unsupported([{"text": "Line one."}], "SOURCE TEXT") == {}
