"""The owner's own OpenAI-compatible model provider (a FreeLLMAPI proxy, DeepSeek, GLM...): settings, routing, safety, fallback."""
import json
import socket

import pytest

import dashboard
import freemodels
import llm

KEY = "freellmapi-SECRET-0123456789abcdef"


def _settings(tmp_path, monkeypatch, **extra):
    f = tmp_path / "settings.json"
    base = {"extra_llm_on": True, "extra_llm_url": "http://127.0.0.1:31415/v1", "extra_llm_local": True, "extra_llm_key": KEY,
            "extra_llm_models": {"script": "deepseek-chat, glm-4.6", "review": "glm-4.6"}}
    f.write_text(json.dumps({**base, **extra}))
    monkeypatch.setattr(llm, "SETTINGS_FILE", f)
    monkeypatch.setattr(dashboard, "SETTINGS", f)
    return f


def _resolve(monkeypatch, ip):
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, *a, **k: [(socket.AF_INET, 0, 0, "", (ip, 443))])


def test_url_rules_https_public_only_and_local_http_only_when_ticked(monkeypatch):
    _resolve(monkeypatch, "93.184.216.34")
    assert llm.extra_url_ok("https://api.example.com/v1", False)[0] is True
    assert llm.extra_url_ok("http://api.example.com/v1", False)[0] is False            # plain http to the internet
    assert llm.extra_url_ok("http://api.example.com/v1", True)[0] is False             # the local box option never opens the internet over http
    assert llm.extra_url_ok("http://127.0.0.1:31415/v1", False)[0] is False            # a local proxy needs the tick
    assert llm.extra_url_ok("http://127.0.0.1:31415/v1", True)[0] is True
    assert llm.extra_url_ok("http://localhost:3001/v1", True)[0] is True
    assert llm.extra_url_ok("https://user:pw@api.example.com/v1", False)[0] is False   # no credentials in the address
    assert llm.extra_url_ok("ftp://api.example.com/v1", False)[0] is False
    _resolve(monkeypatch, "10.0.0.5")
    assert llm.extra_url_ok("https://api.example.com/v1", False)[0] is False           # a name that points at a private address


def test_models_by_role_and_off_means_none(tmp_path, monkeypatch):
    _settings(tmp_path, monkeypatch)
    assert llm.extra_models("script") == ["extra:deepseek-chat", "extra:glm-4.6"]
    assert llm.extra_models("review") == ["extra:glm-4.6"]
    assert llm.extra_models("cheap") == ["extra:deepseek-chat", "extra:glm-4.6"]       # small jobs use the writer list
    _settings(tmp_path, monkeypatch, extra_llm_on=False)
    assert llm.extra_models("script") == []
    _settings(tmp_path, monkeypatch, extra_llm_key="")
    assert llm.extra_models("script") == []                                            # no key, no provider
    _settings(tmp_path, monkeypatch, extra_llm_url="http://evil.example.com/v1")
    assert llm.extra_models("script") == []                                            # an address the rules refuse is not used


def test_post_goes_to_the_extra_address_with_its_own_key_and_no_openrouter_fields(tmp_path, monkeypatch):
    _settings(tmp_path, monkeypatch)
    seen = {}

    class R:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "{}"}}], "usage": {"prompt_tokens": 3, "completion_tokens": 2}}

    def fake_post(url, json=None, headers=None, timeout=None, allow_redirects=True, **k):
        seen.update(url=url, json=json, headers=headers, redirects=allow_redirects)
        return R()

    monkeypatch.setattr(llm.requests, "post", fake_post)
    llm._post({"model": "extra:deepseek-chat", "messages": [], "usage": {"include": True}, "max_tokens": 10}, "OPENROUTER-KEY")
    assert seen["url"] == "http://127.0.0.1:31415/v1/chat/completions"
    assert seen["headers"]["Authorization"] == f"Bearer {KEY}" and "OPENROUTER-KEY" not in json.dumps(seen["headers"])
    assert seen["json"]["model"] == "deepseek-chat" and "usage" not in seen["json"]
    assert seen["redirects"] is False                                                  # a redirect could lead to an internal address


def test_free_chat_tries_the_extra_models_first_then_falls_back_and_counts_only_openrouter(tmp_path, monkeypatch):
    import datetime as dt
    _settings(tmp_path, monkeypatch)
    calls, counted = [], []
    monkeypatch.setattr(freemodels, "refresh", lambda now: None)
    monkeypatch.setattr(freemodels, "choose", lambda role, now, avoid=None, n=4: ["or/model:free"])
    monkeypatch.setattr(freemodels, "remaining", lambda *a, **k: 500)
    monkeypatch.setattr(freemodels, "requests_today", lambda *a, **k: 0)
    monkeypatch.setattr(freemodels, "count_request", lambda now, role: counted.append(role))
    monkeypatch.setattr(freemodels, "record", lambda *a, **k: None)
    monkeypatch.setattr(freemodels, "available", lambda mid, now: True)

    def fake_post(payload, key):
        calls.append(payload["model"])
        if payload["model"].startswith("extra:"):
            raise RuntimeError("provider down")
        return {"choices": [{"message": {"content": '{"ok": true}'}}], "usage": {}}

    monkeypatch.setattr(llm, "_post", fake_post)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    out = llm._free_chat("p", "script", llm.load_config(), "KEY", dt.datetime.now(dt.timezone.utc))
    assert out == {"ok": True}
    assert calls[0] == "extra:deepseek-chat" and calls[-1] == "or/model:free"
    assert counted == ["script"]                                                       # only the OpenRouter request used the OpenRouter allowance


def test_the_writer_family_is_not_asked_to_review_its_own_script(tmp_path, monkeypatch):
    import datetime as dt
    _settings(tmp_path, monkeypatch)
    asked = []
    monkeypatch.setattr(freemodels, "refresh", lambda now: None)
    monkeypatch.setattr(freemodels, "choose", lambda role, now, avoid=None, n=4: ["or/x:free"])
    monkeypatch.setattr(freemodels, "remaining", lambda *a, **k: 500)
    monkeypatch.setattr(freemodels, "requests_today", lambda *a, **k: 0)
    monkeypatch.setattr(freemodels, "count_request", lambda *a: None)
    monkeypatch.setattr(freemodels, "record", lambda *a, **k: None)
    monkeypatch.setattr(freemodels, "available", lambda mid, now: True)
    monkeypatch.setattr(llm, "_post", lambda payload, key: (asked.append(payload["model"]), {"choices": [{"message": {"content": "{}"}}], "usage": {}})[1])
    monkeypatch.setitem(llm._last_free, "script", "extra:glm-4.6")
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    llm._free_chat("p", "review", llm.load_config(), "KEY", dt.datetime.now(dt.timezone.utc))
    assert asked == ["or/x:free"]                                      # the model that just wrote is never the judge


def test_the_key_is_saved_but_never_returned_and_the_rest_is_validated(tmp_path, monkeypatch):
    f = tmp_path / "settings.json"
    f.write_text("{}")
    monkeypatch.setattr(llm, "SETTINGS_FILE", f)
    monkeypatch.setattr(dashboard, "SETTINGS", f)
    assert dashboard.H.route(None, "/api/key/save", {"which": "extra_llm", "value": KEY}) == {"ok": True}
    assert json.loads(f.read_text())["extra_llm_key"] == KEY
    assert (f.stat().st_mode & 0o777) == 0o600
    st = dashboard.extra_llm_status()
    assert st["key"] == "saved" and KEY not in json.dumps(st) and KEY not in json.dumps(dashboard.H.route(None, "/api/extra-llm/save", {"on": True, "url": "http://127.0.0.1:31415/v1", "local": True, "script": "auto", "review": "auto"}))
    assert json.loads(f.read_text())["extra_llm_url"] == "http://127.0.0.1:31415/v1"
    with pytest.raises(ValueError):
        dashboard.H.route(None, "/api/extra-llm/save", {"on": True, "url": "http://evil.example.com/v1", "local": True, "script": "auto", "review": "auto"})
    with pytest.raises(ValueError):
        dashboard.H.route(None, "/api/extra-llm/save", {"on": True, "url": "http://127.0.0.1:31415/v1", "local": True, "script": "bad name; rm -rf", "review": "auto"})


def test_the_test_button_reports_speed_and_never_the_key(tmp_path, monkeypatch):
    _settings(tmp_path, monkeypatch)
    monkeypatch.setattr(llm, "_post", lambda payload, key: {"choices": [{"message": {"content": "pong"}}], "usage": {}})
    r = dashboard.H.route(None, "/api/extra-llm/test", {})
    assert r["ok"] is True and "seconds" in r and KEY not in json.dumps(r)

    def boom(payload, key):
        raise RuntimeError(f"401 for key {KEY}")

    monkeypatch.setattr(llm, "_post", boom)
    r = dashboard.H.route(None, "/api/extra-llm/test", {})
    assert r["ok"] is False and KEY not in json.dumps(r)                              # an error message that quotes the key is cleaned


def test_the_key_never_reaches_the_usage_log_or_the_fallback_notes(tmp_path, monkeypatch):
    import datetime as dt
    _settings(tmp_path, monkeypatch)
    monkeypatch.setattr(freemodels, "refresh", lambda now: None)
    monkeypatch.setattr(freemodels, "choose", lambda *a, **k: [])
    monkeypatch.setattr(freemodels, "remaining", lambda *a, **k: 500)
    monkeypatch.setattr(freemodels, "requests_today", lambda *a, **k: 0)
    monkeypatch.setattr(freemodels, "count_request", lambda *a: None)
    monkeypatch.setattr(freemodels, "record", lambda *a, **k: None)
    monkeypatch.setattr(freemodels, "available", lambda mid, now: True)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)

    def boom(payload, key):
        raise RuntimeError(f"bad key {KEY}")

    monkeypatch.setattr(llm, "_post", boom)
    llm._free_chat("p", "script", llm.load_config(), "KEY", dt.datetime.now(dt.timezone.utc))
    assert KEY not in llm.USAGE_FILE.read_text() if llm.USAGE_FILE.exists() else True


def test_agenteval_case_passes_and_fails_when_a_rule_is_broken(monkeypatch):
    import agenteval

    name = "case_the_owners_own_model_provider_key_never_leaves_the_settings_file_and_its_address_is_checked"
    case = getattr(agenteval, name)
    assert case in agenteval.CASES
    ok, detail = case()
    assert ok, detail
    real_scrub = llm.scrub
    monkeypatch.setattr(llm, "scrub", lambda text: str(text))  # mutation: errors are no longer cleaned of the key
    ok, detail = case()
    assert not ok and "cleaned=False" in detail
    monkeypatch.undo()
    real_ok = llm.extra_url_ok
    monkeypatch.setattr(llm, "extra_url_ok", lambda url, local: (True, ""))  # mutation: every address is accepted
    ok, detail = case()
    assert not ok and "refused=False" in detail
    monkeypatch.undo()
    real_post = llm._post_extra

    def leaky(payload):  # mutation: the OpenRouter key is sent to the other provider as well
        import requests
        cfg = llm.extra_cfg()
        requests.post(cfg["url"] + "/chat/completions", json=payload, headers={"Authorization": "Bearer or-key-0123456789"}, allow_redirects=False)
        return {}

    monkeypatch.setattr(llm, "_post_extra", leaky)
    ok, detail = case()
    assert not ok and "routed=False" in detail
