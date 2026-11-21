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
            "extra_llm_models": {"script": "deepseek-chat, glm-4.6", "review": "qwen-judge"}}
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
    assert llm.extra_models("review") == ["extra:qwen-judge"]
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
    assert calls[-1] == "or/model:free"                                                # the OpenRouter free model was the fallback after both extras failed
    assert set(calls[:2]) == {"extra:deepseek-chat", "extra:glm-4.6"}                   # both of the owner's models were asked first; for a script they are raced, so their order is not fixed
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
    monkeypatch.setitem(llm._last_free, "script", "extra:qwen-judge")
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
    assert st["key"] == "saved" and KEY not in json.dumps(st) and KEY not in json.dumps(dashboard.H.route(None, "/api/extra-llm/save", {"on": True, "url": "http://127.0.0.1:31415/v1", "local": True, "script": "auto", "review": "judge-1"}))
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


# ---- 20 Nov 2026: the writer and the judge, the provider's own model status, and plain errors (diagnosis of the 429 on gemini-3.5-flash) ----
import requests as _rq


def _fm_quiet(monkeypatch, choose=None):
    monkeypatch.setattr(freemodels, "refresh", lambda now: None)
    monkeypatch.setattr(freemodels, "choose", choose or (lambda *a, **k: []))
    monkeypatch.setattr(freemodels, "remaining", lambda *a, **k: 500)
    monkeypatch.setattr(freemodels, "requests_today", lambda *a, **k: 0)
    monkeypatch.setattr(freemodels, "count_request", lambda *a, **k: None)
    monkeypatch.setattr(freemodels, "record", lambda *a, **k: None)
    monkeypatch.setattr(freemodels, "available", lambda mid, now: True)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    monkeypatch.setattr(llm, "_last_free", {})


def _catalog(monkeypatch, rows, calls=None):
    class R:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": rows}

    def get(url, key):
        if calls is not None:
            calls.append(url)
        return R()

    monkeypatch.setattr(llm, "_catalog_get", get)
    llm._catalog.clear()


def _http_error(code, message, retry_after=None):
    r = _rq.Response()
    r.status_code = code
    r._content = json.dumps({"error": {"message": message, "type": "rate_limit_error"}}).encode()
    if retry_after is not None:
        r.headers["Retry-After"] = str(retry_after)
    return _rq.HTTPError(str(code), response=r)


def _answer(asked, served=None):
    def post(payload, key):
        asked.append(payload["model"])
        name = (served or {}).get(payload["model"], payload["model"].replace("extra:", ""))
        return {"model": name, "choices": [{"message": {"content": '{"ok": true}'}}], "usage": {}}
    return post


def test_model_identity_sees_one_model_under_several_names():
    assert llm.model_identity("extra:gemini-3.6-flash") == llm.model_identity("google/gemini-3.6-flash") == llm.model_identity("gemini-3.6-flash:free") == "gemini-3.6-flash"
    assert llm.model_identity("extra:nemotron-3-ultra-550b") != llm.model_identity("gemini-3.6-flash")


def test_a_judge_is_never_a_router_or_a_script_model_when_saved_or_when_the_file_was_edited_by_hand(tmp_path, monkeypatch):
    f = _settings(tmp_path, monkeypatch)

    def save(script, review):
        return dashboard.H.route(None, "/api/extra-llm/save", {"on": True, "url": "http://127.0.0.1:31415/v1", "local": True, "script": script, "review": review})

    with pytest.raises(ValueError, match="both lists"):
        save("gemini-3.5-flash, gemini-3.6-flash, auto", "gemini-3.6-flash, auto")     # the owner's lists of 20 Nov 2026
    with pytest.raises(ValueError, match="choose the model"):
        save("gemini-3.5-flash", "auto")
    with pytest.raises(ValueError, match="both lists"):
        save("google/gemma-4-31b-it:free", "gemma-4-31b-it")                          # one model under two names
    assert save("gemini-3.5-flash, gemini-3-flash-preview, minimaxaiminimax-m3.1-flash", "gemini-3.6-flash, nemotron-3-ultra-550b")["ok"] is True
    assert json.loads(f.read_text())["extra_llm_key"] == KEY                           # saving the lists keeps the key
    _settings(tmp_path, monkeypatch, extra_llm_models={"script": "w1, auto", "review": "w1, auto, j1"})
    assert llm.extra_models("review") == ["extra:j1"]                                  # a hand-edited file: the writer and the router are dropped as judges
    assert llm.extra_models("script") == ["extra:w1", "extra:auto"]                     # writing may still use them


def test_a_review_in_another_process_avoids_the_recorded_writers_also_under_other_names(tmp_path, monkeypatch):
    _settings(tmp_path, monkeypatch, extra_llm_models={"script": "w1, auto", "review": "j2, j3"})
    _fm_quiet(monkeypatch)
    asked = []
    monkeypatch.setattr(llm, "_post", _answer(asked, {"extra:auto": "j2"}))
    llm.begin_script()
    llm._free_chat("p", "script", llm.load_config(), "KEY", NOW, avoid={"extra:w1"})   # "auto" writes, and the proxy serves it with j2
    assert llm.writers() == ["extra:auto", "j2"]
    llm._last_free.clear()
    llm._WRITERS.clear()                                                               # a later process knows only the video's record
    monkeypatch.setattr(freemodels, "choose", lambda *a, **k: ["vendor/j2:free", "or/other:free"])
    asked.clear()
    assert llm._free_chat("p", "review", llm.load_config(), "KEY", NOW, avoid={"extra:auto", "j2"}) == {"ok": True}
    llm.settle(10)                                                                     # the raced loser may still be answering
    assert "extra:j2" not in asked and "vendor/j2:free" not in asked                   # j2 wrote it (as "auto"), so it never judges it, under any name
    assert set(asked) <= {"extra:j3", "or/other:free"} and asked


def test_a_script_records_its_real_writers_and_the_reviewer_passes_them_on(monkeypatch):
    import reviewer
    import scriptgen

    llm._WRITERS.add("left-over-from-another-script")
    llm._served["extra:auto"] = "j2"

    def write(prompt):
        llm._answered("script", "extra:auto")
        return {"title": "The quiet light", "lines": [{"text": f"Line {i} tells one calm part of the story in plain words."} for i in range(10)]}

    monkeypatch.setattr(scriptgen, "_script_chat", write)
    meta = scriptgen.script("a quiet lighthouse")
    assert meta["script_writers"] == ["extra:auto", "j2"]                              # what really wrote it; the previous script's writer is forgotten
    seen = {}
    monkeypatch.setattr(scriptgen, "_review_chat", lambda p, avoid=None: seen.update(avoid=avoid) or {"invented_facts_risk": 1, "policy_risk": 0, "misleading_title": False, "issues": []})
    reviewer.llm_review(meta)
    assert seen["avoid"] == ["extra:auto", "j2"]
    reviewer.llm_review({"title": "T", "lines": [{"text": "A line."}]})
    assert seen["avoid"] is None                                                       # an older video without the record: as before
    calls = []
    monkeypatch.undo()                                                                 # the real scriptgen._review_chat again
    monkeypatch.setattr(llm, "chat", lambda prompt, role="cheap", fallback=None, now=None, strict=False, **k: calls.append(k) or {})
    scriptgen._review_chat("p", avoid=["j2"])
    scriptgen._review_chat("p")
    assert calls == [{"avoid": ["j2"]}, {}]                                            # the writers ride along only when there are some


def test_exhausted_models_are_not_asked_and_come_back_when_the_provider_says_ready(tmp_path, monkeypatch):
    _settings(tmp_path, monkeypatch, extra_llm_models={"script": "w1, w2", "review": "j1"})
    _fm_quiet(monkeypatch, choose=lambda *a, **k: ["or/x:free"])
    gets, asked = [], []
    _catalog(monkeypatch, [{"id": "w1", "available": True, "execution_status": "exhausted"}, {"id": "w2", "available": True, "execution_status": "ready"},
                           {"id": "j1", "available": False, "execution_status": "needsKey"}], gets)
    monkeypatch.setattr(llm, "_post", _answer(asked))
    llm._free_chat("p", "script", llm.load_config(), "KEY", NOW)
    llm.settle(10)                                                                     # w2 and or/x are raced: wait for the loser too
    assert "extra:w1" not in asked and "extra:w2" in asked                            # the provider said w1's quota is used up: it is not asked
    assert llm.extra_status("extra:j1") == "needsKey" and llm.extra_status("w2") == "ready" and llm.extra_status("extra:nope") is None
    assert len(gets) == 1                                                              # the list is read once a minute, not once per model or call
    _catalog(monkeypatch, [{"id": "w1", "available": True, "execution_status": "ready"}], gets)  # Google's 08:00 UTC reset
    asked.clear()
    llm.begin_script()  # a later job writes a new script (within one script its own writer, w2, is asked first since 20 Nov 2026)
    llm._free_chat("p", "script", llm.load_config(), "KEY", NOW)
    llm.settle(10)
    assert "extra:w1" in asked


def test_an_unreadable_model_list_changes_nothing(tmp_path, monkeypatch):
    _settings(tmp_path, monkeypatch)                                                   # conftest makes every model list unreadable
    assert llm.extra_catalog() is None and llm.extra_status("extra:deepseek-chat") is None


def test_errors_tell_a_used_up_quota_from_a_rate_limit_and_when_to_try_again(tmp_path, monkeypatch):
    _settings(tmp_path, monkeypatch)
    monkeypatch.setattr(llm, "_now", lambda: dt.datetime(2026, 11, 20, 4, 26, 44, tzinfo=dt.timezone.utc))
    real = ("All models exhausted: 1 route checked (1 rate-limited or on cooldown). Add more API keys or wait for rate limits to reset. Soonest reset ~4h.")
    t = llm.extra_error(_http_error(429, real, 12796))                                  # the proxy's real answer of 20 Nov 2026, 04:26 UTC
    assert t.startswith("quota used up (HTTP 429)") and "Try again after 08:00 UTC" in t
    assert llm.extra_error(_http_error(429, "All models rate-limited after 1 attempt. Soonest cooldown reset ~87s.", 88)).startswith("rate limited (HTTP 429)")
    assert KEY not in llm.extra_error(_http_error(401, f"Invalid API key {KEY}"))
    assert llm.extra_error(RuntimeError("down")).startswith("RuntimeError")


def test_the_test_button_asks_one_writer_and_one_judge_skips_exhausted_models_and_explains_a_429(tmp_path, monkeypatch):
    _settings(tmp_path, monkeypatch, extra_llm_models={"script": "w1, w2", "review": "j1"})
    _catalog(monkeypatch, [{"id": "w1", "available": True, "execution_status": "exhausted"}])
    asked = []
    monkeypatch.setattr(llm, "_post", lambda payload, key: (asked.append(payload["model"]), {"choices": [{"message": {"content": "pong"}}], "usage": {}})[1])
    r = dashboard.H.route(None, "/api/extra-llm/test", {})
    assert asked == ["extra:w2", "extra:j1"]                                            # one writer and one judge; the exhausted model was not asked
    assert r["ok"] is True and [x["model"] for x in r["rows"]] == ["w1", "w2", "j1"] and "exhausted" in r["rows"][0]["detail"]
    assert KEY not in json.dumps(r)

    def busy(payload, key):
        raise _http_error(429, f"All models exhausted. Soonest reset ~4h. key={KEY}", 12796)

    monkeypatch.setattr(llm, "_post", busy)
    r = dashboard.H.route(None, "/api/extra-llm/test", {})
    assert r["ok"] is False and "quota used up" in r["detail"] and "Try again after" in r["detail"] and KEY not in json.dumps(r)


def test_agenteval_judge_case_passes_and_fails_when_a_rule_is_broken(monkeypatch):
    import agenteval

    case = agenteval.case_a_judge_is_never_the_writer_even_through_the_owners_provider
    assert case in agenteval.CASES
    ok, detail = case()
    assert ok, detail
    monkeypatch.setattr(llm, "model_identity", lambda m: str(m))                       # mutation: names compared as typed, so the writer under another name may judge
    ok, detail = case()
    assert not ok and "avoided=False" in detail
    monkeypatch.undo()
    monkeypatch.setattr(llm, "extra_status", lambda mid: None)                         # mutation: the provider's "exhausted" is ignored
    ok, detail = case()
    assert not ok and "discovered=False" in detail
    monkeypatch.undo()

    def unfiltered(role):                                                              # mutation: a writer or a router may sit on the judge list
        cfg = llm.extra_cfg()
        return [llm.EXTRA_PREFIX + m for m in cfg["review" if role == "review" else "script"]] if cfg else []

    monkeypatch.setattr(llm, "extra_models", unfiltered)
    ok, detail = case()
    assert not ok and "filtered=False" in detail
    monkeypatch.undo()

    def forgetful(role, mid):                                                          # mutation: what the provider served is not recorded as a writer
        llm._last_free[role] = mid
        if role == "script":
            llm._WRITERS.add(mid)

    monkeypatch.setattr(llm, "_answered", forgetful)
    ok, detail = case()
    assert not ok and "avoided=False" in detail


def test_a_429_from_the_owners_provider_falls_back_to_a_free_model_only_and_records_who_answered(tmp_path, monkeypatch):
    _settings(tmp_path, monkeypatch, extra_llm_models={"script": "gemini-3.5-flash", "review": "gemini-3.6-flash"})
    _fm_quiet(monkeypatch, choose=lambda *a, **k: ["or/free-writer:free"])
    monkeypatch.setattr(llm, "load_config", lambda: {**llm.DEFAULTS, "enabled": False, "free": True, "free_review": True, "models": {"script": "anthropic/claude-paid"}})
    monkeypatch.setattr(llm, "api_key", lambda: "OR-KEY")
    sent, busy = [], []
    monkeypatch.setattr(freemodels, "record", lambda mid, ok, now, status=None, **k: busy.append((mid, status)) if status == 429 else None)

    def post(payload, key):
        sent.append(payload["model"])
        if payload["model"].startswith("extra:"):
            raise _http_error(429, "All models exhausted: 1 route checked. Soonest reset ~4h.", 12796)
        return {"model": payload["model"], "choices": [{"message": {"content": '{"lines": ["ok"]}'}}], "usage": {}}

    monkeypatch.setattr(llm, "_post", post)
    llm.begin_script()
    assert llm.chat("write", "script") == {"lines": ["ok"]}
    llm.settle(10)
    assert sent.count("extra:gemini-3.5-flash") == 1                                    # asked once, never in a loop
    assert busy == [("extra:gemini-3.5-flash", 429)]                                    # the failure is recorded as busy, not broken
    assert "anthropic/claude-paid" not in sent and all(m.startswith("extra:") or m.endswith(":free") for m in sent)  # no paid model
    assert llm.writers() == ["or/free-writer:free"]                                     # the job records the model that really wrote


def test_when_every_free_model_fails_the_job_stops_with_a_plain_error_not_a_paid_model(tmp_path, monkeypatch):
    _settings(tmp_path, monkeypatch, extra_llm_models={"script": "gemini-3.5-flash", "review": "gemini-3.6-flash"})
    _fm_quiet(monkeypatch, choose=lambda *a, **k: ["or/free-writer:free"])
    monkeypatch.setattr(llm, "load_config", lambda: {**llm.DEFAULTS, "enabled": False, "free": True, "local_fallback": False, "models": {"script": "anthropic/claude-paid"}})
    monkeypatch.setattr(llm, "api_key", lambda: "OR-KEY")
    sent = []
    monkeypatch.setattr(llm, "_post", lambda payload, key: (sent.append(payload["model"]), (_ for _ in ()).throw(_http_error(429, "rate-limited", 30)))[1])
    with pytest.raises(llm.ModelUnavailable):
        llm.chat("write", "script")
    llm.settle(10)
    assert "anthropic/claude-paid" not in sent and len(sent) <= 2 * llm.ROUNDS * 2      # bounded, and never the paid model


def test_a_router_judge_answered_by_the_scripts_writer_is_not_used_and_another_judge_is_asked(tmp_path, monkeypatch):
    """21 Nov 2026 audit: OpenRouter's own router (openrouter/free) answered 73 reviews on 20 Nov; it picks any free model, the writer included. What it
    served is read from the reply, and a judgement the writer made is thrown away; the next judge is asked."""
    _settings(tmp_path, monkeypatch, extra_llm_models={"script": "", "review": ""})
    _fm_quiet(monkeypatch)
    asked = []
    monkeypatch.setattr(llm, "_post", _answer(asked, {"openrouter/free": "nvidia/nemotron-3.5-super-vl:free"}))
    monkeypatch.setattr(freemodels, "choose", lambda *a, **k: ["openrouter/free", "or/other:free", "or/third:free"])
    monkeypatch.setattr(llm, "RACE_ROLES", ())  # one judge at a time, so the order is fixed
    llm._last_free.clear()
    llm._WRITERS.clear()
    got = llm._free_chat("p", "review", llm.load_config(), "KEY", NOW, avoid={"nvidia/nemotron-3.5-super-vl:free"})
    assert got == {"ok": True} and asked[:2] == ["openrouter/free", "or/other:free"] and llm._last_free["review"] == "or/other:free"
    asked.clear()
    llm._last_free.clear()
    monkeypatch.setattr(llm, "_post", _answer(asked, {"openrouter/free": "somebody/else:free"}))
    assert llm._free_chat("p", "review", llm.load_config(), "KEY", NOW, avoid={"nvidia/nemotron-3.5-super-vl:free"}) == {"ok": True}
    assert asked == ["openrouter/free"] and llm._last_free["review"] == "openrouter/free"  # a router that served another model is a fair judge


def test_what_a_router_served_as_a_writer_is_recorded_so_it_never_judges_the_same_script(tmp_path, monkeypatch):
    _settings(tmp_path, monkeypatch, extra_llm_models={"script": "", "review": ""})
    _fm_quiet(monkeypatch)
    asked = []
    monkeypatch.setattr(llm, "_post", _answer(asked, {"openrouter/free": "vendor/writer-x:free"}))
    monkeypatch.setattr(freemodels, "choose", lambda *a, **k: ["openrouter/free"])
    llm.begin_script()
    llm._free_chat("p", "script", llm.load_config(), "KEY", NOW)
    assert "vendor/writer-x:free" in llm.writers() and "openrouter/free" in llm.writers()


def test_refused_connections_to_the_owners_provider_never_bench_its_models_for_six_hours(tmp_path, monkeypatch):
    """21 Nov 2026: FreeLLMAPI did not start after a power cut; each refused connection counted as a failure and after three all five owner models were
    benched for six hours, so they stayed unused for hours after the app was back. A refused connection only skips the model for a minute."""
    monkeypatch.setattr(freemodels, "FILE", tmp_path / "free.json")
    for _ in range(5):
        freemodels.record("extra:gemini-3.5-flash", False, NOW, role="script", reason="unreachable")
    assert not freemodels.available("extra:gemini-3.5-flash", NOW + dt.timedelta(seconds=30))
    assert freemodels.available("extra:gemini-3.5-flash", NOW + dt.timedelta(seconds=freemodels.UNREACHABLE_SECONDS + 1))
    assert freemodels._load()["health"]["extra:gemini-3.5-flash"]["fails"] == 0          # not a failure of the model
    for _ in range(3):
        freemodels.record("extra:broken", False, NOW, role="script", reason="json")      # a real bad answer still counts
    assert not freemodels.available("extra:broken", NOW + dt.timedelta(hours=1))


def test_when_the_owners_provider_is_down_an_openrouter_free_model_answers_in_the_same_call(tmp_path, monkeypatch):
    """The live failure of 21 Nov 2026: three own models listed first, each refused, and each ended its round, so all three rounds were used on them and
    `llm.chat(..., "cheap")` raised ModelUnavailable while an OpenRouter free model would have answered at once."""
    _settings(tmp_path, monkeypatch, extra_llm_models={"script": "gemini-3.5-flash, gemini-3-flash-preview, minimax-m3", "review": "gemini-3.6-flash"})
    _fm_quiet(monkeypatch, choose=lambda *a, **k: ["or/free-writer:free"])
    monkeypatch.setattr(llm, "load_config", lambda: {**llm.DEFAULTS, "enabled": False, "free": True, "models": {"cheap": "anthropic/claude-paid"}})
    monkeypatch.setattr(llm, "api_key", lambda: "OR-KEY")
    recorded, sent, slept = [], [], []
    monkeypatch.setattr(freemodels, "record", lambda mid, ok, now, **k: recorded.append((mid, ok, k.get("reason"))))
    monkeypatch.setattr(llm.time, "sleep", lambda s: slept.append(s))
    monkeypatch.setattr(llm, "_extra_last", {})                                        # no pacing left over from another test

    def post(payload, key):
        sent.append(payload["model"])
        if payload["model"].startswith("extra:"):
            raise _rq.ConnectionError("[Errno 111] Connection refused")
        return {"model": payload["model"], "choices": [{"message": {"content": '{"ok": true}'}}], "usage": {}}

    monkeypatch.setattr(llm, "_post", post)
    assert llm.chat("x", "cheap") == {"ok": True}
    assert sent == ["extra:gemini-3.5-flash", "extra:gemini-3-flash-preview", "extra:minimax-m3", "or/free-writer:free"]  # one round, no wait
    assert slept == [] and "anthropic/claude-paid" not in sent
    assert [r for r in recorded if r[0].startswith("extra:")] == [(m, False, "unreachable") for m in sent[:3]]  # skipped for a minute, not benched
