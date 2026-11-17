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


# ---- 17 Nov 2026: the pooled free tiers answer 429 often; a script was lost because every model sat in a ten-minute cooldown and the call gave up at once ----
import datetime as dt

NOW = dt.datetime(2026, 11, 17, 1, 0, tzinfo=dt.timezone.utc)


def test_a_429_busies_a_provider_model_for_its_retry_after_or_a_short_default_and_openrouter_keeps_ten_minutes(tmp_path, monkeypatch):
    monkeypatch.setattr(freemodels, "FILE", tmp_path / "free.json")
    freemodels.record("extra:gemini-3.5-flash", False, NOW, status=429, retry_after=30)
    assert not freemodels.available("extra:gemini-3.5-flash", NOW + dt.timedelta(seconds=20))
    assert freemodels.available("extra:gemini-3.5-flash", NOW + dt.timedelta(seconds=31))
    freemodels.record("extra:glm", False, NOW, status=429)                              # no header: a short default, not ten minutes
    assert freemodels.available("extra:glm", NOW + dt.timedelta(seconds=freemodels.EXTRA_BUSY_SECONDS + 1))
    freemodels.record("or/x:free", False, NOW, status=429)
    assert not freemodels.available("or/x:free", NOW + dt.timedelta(minutes=5))        # unchanged for OpenRouter
    freemodels.record("extra:hog", False, NOW, status=429, retry_after=99999)
    assert freemodels.available("extra:hog", NOW + dt.timedelta(seconds=freemodels.MAX_RETRY_AFTER + 1))  # a silly header cannot park a model for a day


def test_soonest_free_reports_the_wait_for_busy_models_only(tmp_path, monkeypatch):
    monkeypatch.setattr(freemodels, "FILE", tmp_path / "free.json")
    assert freemodels.soonest_free(["extra:a"], NOW) is None
    freemodels.record("extra:a", False, NOW, status=429, retry_after=40)
    freemodels.record("extra:b", False, NOW, status=429, retry_after=15)
    assert freemodels.soonest_free(["extra:a", "extra:b"], NOW) == 15
    assert freemodels.soonest_free(["extra:a"], NOW + dt.timedelta(seconds=50)) is None  # already free again


def test_free_chat_waits_for_a_busy_model_instead_of_giving_up(tmp_path, monkeypatch):
    import requests
    monkeypatch.setattr(freemodels, "FILE", tmp_path / "free.json")
    _settings(tmp_path, monkeypatch, extra_llm_models={"script": "only-model", "review": "only-model"})
    monkeypatch.setattr(freemodels, "refresh", lambda now: None)
    monkeypatch.setattr(freemodels, "choose", lambda *a, **k: [])
    monkeypatch.setattr(freemodels, "remaining", lambda *a, **k: 500)
    monkeypatch.setattr(freemodels, "requests_today", lambda *a, **k: 0)
    monkeypatch.setattr(freemodels, "count_request", lambda *a: None)
    slept, calls = [], []
    monkeypatch.setattr(llm.time, "sleep", lambda s: slept.append(s))

    def post(payload, key):
        calls.append(payload["model"])
        if len(calls) == 1:
            r = requests.Response()
            r.status_code = 429
            r.headers["Retry-After"] = "7"
            raise requests.HTTPError("429", response=r)
        return {"choices": [{"message": {"content": '{"ok": true}'}}], "usage": {}}

    monkeypatch.setattr(llm, "_post", post)
    out = llm._free_chat("p", "script", llm.load_config(), "KEY", NOW)
    assert out == {"ok": True} and len(calls) == 2
    assert any(7 <= s <= 12 for s in slept)                                            # it waited about the Retry-After, not ten minutes and not zero


def test_free_chat_does_not_wait_longer_than_the_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(freemodels, "FILE", tmp_path / "free.json")
    _settings(tmp_path, monkeypatch, extra_llm_models={"script": "only-model", "review": "only-model"})
    monkeypatch.setattr(freemodels, "refresh", lambda now: None)
    monkeypatch.setattr(freemodels, "choose", lambda *a, **k: [])
    monkeypatch.setattr(freemodels, "remaining", lambda *a, **k: 500)
    monkeypatch.setattr(freemodels, "requests_today", lambda *a, **k: 0)
    monkeypatch.setattr(freemodels, "count_request", lambda *a: None)
    slept = []
    monkeypatch.setattr(llm.time, "sleep", lambda s: slept.append(s))
    freemodels.record("extra:only-model", False, NOW, status=429, retry_after=freemodels.MAX_RETRY_AFTER)
    monkeypatch.setattr(llm, "_post", lambda payload, key: (_ for _ in ()).throw(AssertionError("must not be asked while busy for longer than the wait limit")))
    assert llm._free_chat("p", "script", llm.load_config(), "KEY", NOW) is None
    assert all(s <= llm.FREE_WAIT_LIMIT + 1 for s in slept)


def test_calls_to_the_same_provider_model_are_spaced_by_the_gap(tmp_path, monkeypatch):
    _settings(tmp_path, monkeypatch, extra_llm_gap_s=6)
    clock = [100.0]
    slept = []
    monkeypatch.setattr(llm.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(llm.time, "sleep", lambda s: (slept.append(s), clock.__setitem__(0, clock[0] + s)))
    llm._extra_last.clear()
    llm._pace_extra("extra:m")
    assert slept == []                                                                 # the first call goes at once
    clock[0] += 2
    llm._pace_extra("extra:m")
    assert slept and 3.9 <= slept[0] <= 4.1                                            # 6 s gap minus the 2 s already passed
    llm._pace_extra("extra:other")
    assert len(slept) == 1                                                             # another model has its own limit
    _settings(tmp_path, monkeypatch, extra_llm_gap_s=0)
    llm._extra_last.clear()
    llm._pace_extra("extra:m")
    llm._pace_extra("extra:m")
    assert len(slept) == 1                                                             # 0 switches the spacing off
