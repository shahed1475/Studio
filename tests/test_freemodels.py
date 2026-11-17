import datetime as dt

import freemodels
import llm
import pytest

NOW = dt.datetime(2026, 10, 19, 12, 0, tzinfo=dt.timezone.utc)


def model(mid, ctx=65536, prompt="0", completion="0", params=("response_format",), out=("text",)):
    return {"id": mid, "context_length": ctx, "pricing": {"prompt": prompt, "completion": completion},
            "architecture": {"output_modalities": list(out)}, "supported_parameters": list(params)}


class Resp:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return {"data": self.data}


@pytest.fixture(autouse=True)
def iso(tmp_path, monkeypatch):
    monkeypatch.setattr(freemodels, "FILE", tmp_path / "free.json")


def test_refresh_keeps_only_free_text_models_with_enough_context_best_first():
    data = [model("a/paid", prompt="0.001"), model("b/free-small", ctx=8000), model("c/image-gen:free", out=("image",)),
            model("google/gemma-4-31b:free"), model("x/plain:free", params=()), model("openrouter/auto", prompt="-1", completion="-1"),
            model("d/embed-text:free")]
    got = freemodels.refresh(NOW, get=lambda *a, **k: Resp(data))
    assert [m["id"] for m in got] == ["google/gemma-4-31b:free", "x/plain:free"]


def test_refresh_skips_music_and_video_generators():
    got = freemodels.refresh(NOW, get=lambda *a, **k: Resp([model("google/lyria-3-clip-preview"), model("x/video-maker:free"), model("g/ok:free")]))
    assert [m["id"] for m in got] == ["g/ok:free"]


def test_refresh_uses_cache_for_a_day_and_survives_network_failure():
    calls = []

    def get(*a, **k):
        calls.append(1)
        return Resp([model("a/m:free")])

    freemodels.refresh(NOW, get=get)
    freemodels.refresh(NOW + dt.timedelta(hours=3), get=get)
    assert len(calls) == 1

    def boom(*a, **k):
        raise OSError("offline")

    got = freemodels.refresh(NOW + dt.timedelta(days=2), get=boom)
    assert [m["id"] for m in got] == ["a/m:free"]


def test_failing_model_gets_a_cooldown_and_recovers():
    freemodels.refresh(NOW, get=lambda *a, **k: Resp([model("a/m1:free"), model("b/m2:free")]))
    first = freemodels.choose("cheap", NOW)[0]
    for _ in range(3):
        freemodels.record(first, False, NOW)
    assert first not in freemodels.choose("cheap", NOW)
    assert first in freemodels.choose("cheap", NOW + dt.timedelta(hours=7))
    freemodels.record(first, True, NOW + dt.timedelta(hours=7))
    assert first in freemodels.choose("cheap", NOW + dt.timedelta(hours=7))


def test_script_needs_32k_context_and_review_avoids_writer():
    freemodels.refresh(NOW, get=lambda *a, **k: Resp([model("a/small:free", ctx=20000), model("b/big:free", ctx=131072), model("c/big2:free", ctx=131072)]))
    assert "a/small:free" not in freemodels.choose("script", NOW)
    assert "a/small:free" in freemodels.choose("cheap", NOW)
    writer = freemodels.choose("script", NOW)[0]
    assert writer not in freemodels.choose("review", NOW, avoid=writer)


def test_request_counter_is_per_day():
    assert freemodels.requests_today(NOW) == 0
    freemodels.count_request(NOW)
    freemodels.count_request(NOW)
    assert freemodels.requests_today(NOW) == 2
    assert freemodels.requests_today(NOW + dt.timedelta(days=1)) == 0


# ---- the router uses it ----
@pytest.fixture
def router(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "CONFIG_FILE", tmp_path / "llm.json")
    monkeypatch.setattr(llm, "USAGE_FILE", tmp_path / "usage.json")
    monkeypatch.setattr(llm, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(llm, "api_key", lambda: "k")
    llm.save_config({**llm.load_config(), "free": True})
    freemodels.refresh(NOW, get=lambda *a, **k: Resp([model("a/m1:free"), model("b/m2:free")]))
    llm._last_free.clear()


def reply(text):
    return {"choices": [{"message": {"content": text}}], "usage": {"prompt_tokens": 5, "completion_tokens": 7}}


def test_free_default_is_off_and_validated(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "CONFIG_FILE", tmp_path / "none.json")
    assert llm.load_config()["free"] is False and llm.load_config()["free_daily_limit"] == 900
    assert llm.validate_config({"free": True, "free_daily_limit": 900}) == {"free": True, "free_daily_limit": 900}
    for bad in ({"free": "yes"}, {"free_daily_limit": 0}, {"free_daily_limit": 5000}):
        with pytest.raises(ValueError):
            llm.validate_config(bad)


def test_free_chain_falls_through_to_next_model_and_counts_requests(router, monkeypatch):
    seen = []

    def post(payload, key):
        seen.append(payload["model"])
        if len(seen) == 1:
            raise OSError("429")
        return reply('{"ok": 1}')

    monkeypatch.setattr(llm, "_post", post)
    got = llm.chat("p", "cheap", fallback=lambda p: pytest.fail("must not fall back"), now=NOW)
    assert got == {"ok": 1} and len(set(seen)) == 2
    assert freemodels.requests_today(NOW) == 2


def test_free_retries_without_json_mode_on_400(router, monkeypatch):
    import requests

    modes = []

    def post(payload, key):
        modes.append("response_format" in payload)
        if payload.get("response_format"):
            r = requests.Response()
            r.status_code = 400
            raise requests.HTTPError(response=r)
        return reply('chatter {"ok": 2} done')

    monkeypatch.setattr(llm, "_post", post)
    assert llm.chat("p", "cheap", fallback=lambda p: pytest.fail("no"), now=NOW) == {"ok": 2}
    assert modes[:2] == [True, False]


def test_daily_limit_and_no_key_use_local(router, monkeypatch):
    monkeypatch.setattr(llm, "_post", lambda *a: pytest.fail("must not call"))
    llm.save_config({**llm.load_config(), "free_daily_limit": 1})
    freemodels.count_request(NOW)
    assert llm.chat("p", "cheap", fallback=lambda p: {"local": 1}, now=NOW) == {"local": 1}
    monkeypatch.setattr(llm, "api_key", lambda: "")
    assert llm.chat("p", "cheap", fallback=lambda p: {"local": 2}, now=NOW) == {"local": 2}


def test_all_free_models_failing_falls_back_to_local(router, monkeypatch):
    def boom(*a):
        raise OSError("down")

    monkeypatch.setattr(llm, "_post", boom)
    assert llm.chat("p", "cheap", fallback=lambda p: {"local": 3}, now=NOW) == {"local": 3}


def test_free_models_never_judge_a_video(router, monkeypatch):
    monkeypatch.setattr(llm, "_post", lambda payload, key: reply("{}"))
    assert llm.chat("p", "script", fallback=None, now=NOW) == {}
    with pytest.raises(llm.ModelUnavailable):
        llm.chat("p", "review", fallback=None, now=NOW)  # the reviewer waits for Claude instead of asking a free model


def test_dashboard_view_shows_free_status(tmp_path, monkeypatch):
    import dashboard

    monkeypatch.setattr(llm, "CONFIG_FILE", tmp_path / "llm.json")
    monkeypatch.setattr(llm, "USAGE_FILE", tmp_path / "usage.json")
    monkeypatch.setattr(llm, "model_prices", lambda: {})
    monkeypatch.setattr(llm, "_now", lambda: NOW)
    freemodels.refresh(NOW, get=lambda *a, **k: Resp([model("a/m1:free")]))
    view = dashboard.llm_view()
    assert view["free"] == {"on": False, "limit": 900, "requests_today": 0, "openrouter": None, "chain": ["a/m1:free"]}


def test_dashboard_refuses_free_without_key(tmp_path, monkeypatch):
    import dashboard

    monkeypatch.setattr(llm, "CONFIG_FILE", tmp_path / "llm.json")
    monkeypatch.setattr(llm, "api_key", lambda: "")
    with pytest.raises(ValueError, match="key"):
        dashboard.H.route(object(), "/api/llm/config", {"free": True})


def test_busy_429_skips_a_model_for_ten_minutes_but_does_not_ban_it(tmp_path, monkeypatch):
    monkeypatch.setattr(freemodels, "FILE", tmp_path / "free.json")
    freemodels.refresh(NOW, get=lambda *a, **k: Resp([model("a/m1:free"), model("b/m2:free")]))
    first = freemodels.choose("cheap", NOW)[0]
    freemodels.record(first, False, NOW, status=429)
    assert first not in freemodels.choose("cheap", NOW + dt.timedelta(minutes=5))
    assert first in freemodels.choose("cheap", NOW + dt.timedelta(minutes=11))


def test_models_that_answered_before_are_asked_first(tmp_path, monkeypatch):
    monkeypatch.setattr(freemodels, "FILE", tmp_path / "free.json")
    freemodels.refresh(NOW, get=lambda *a, **k: Resp([model("a/m1:free"), model("b/m2:free")]))
    second = freemodels.choose("cheap", NOW)[1]
    freemodels.record(second, True, NOW)
    assert freemodels.choose("cheap", NOW)[0] == second


def test_remaining_trusts_openrouters_own_count_with_a_reserve(tmp_path, monkeypatch):
    monkeypatch.setattr(freemodels, "FILE", tmp_path / "free.json")
    monkeypatch.setattr(freemodels, "quota", lambda key: {"used": 990, "limit": 1000, "remaining": 10})
    assert freemodels.remaining(NOW, "k", 900) == 10 - freemodels.RESERVE
    monkeypatch.setattr(freemodels, "quota", lambda key: None)
    assert freemodels.remaining(NOW, "k", 900) == 900


def _paid(router_cfg):
    llm.save_config({**llm.load_config(), "enabled": True, "free": True, "daily_budget_usd": 1.0,
                     "models": {"script": "anthropic/claude-sonnet-5.5", "review": "anthropic/claude-haiku-5.5", "cheap": "anthropic/claude-haiku-5.5"}})


def test_paid_claude_runs_first_then_free_models_when_credit_is_gone(router, monkeypatch):
    _paid(None)
    seen = []

    def post(payload, key):
        seen.append(payload["model"])
        if payload["model"].startswith("anthropic/"):
            err = requests.HTTPError("402 Payment Required")
            err.response = type("R", (), {"status_code": 402})()
            raise err
        return reply('{"ok": 1}')

    monkeypatch.setattr(llm, "_post", post)
    got = llm.chat("p", "script", fallback=lambda p: pytest.fail("no local model"), now=NOW)
    assert got == {"ok": 1}
    assert seen[0] == "anthropic/claude-sonnet-5.5" and seen[-1].endswith(":free")


def test_paid_claude_is_used_while_credit_lasts(router, monkeypatch):
    _paid(None)
    monkeypatch.setattr(llm, "_post", lambda payload, key: {**reply('{"paid": 1}'), "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.001}})
    assert llm.chat("p", "script", now=NOW) == {"paid": 1}
    assert freemodels.requests_today(NOW) == 0  # no free request was spent


def test_daily_dollar_cap_sends_the_job_to_free_models(router, monkeypatch):
    _paid(None)
    llm.save_config({**llm.load_config(), "daily_budget_usd": 0.05})
    monkeypatch.setattr(llm, "spent_today", lambda now=None: 0.05)
    monkeypatch.setattr(llm, "_post", lambda payload, key: reply('{"free": 1}') if payload["model"].endswith(":free") else pytest.fail("cap reached, must not call paid"))
    assert llm.chat("p", "script", now=NOW) == {"free": 1}


def test_the_review_may_spend_a_little_past_the_daily_cap_but_other_jobs_may_not(router, monkeypatch):
    calls = []
    monkeypatch.setattr(llm, "load_config", lambda: {**llm.DEFAULTS, "enabled": True, "models": {"script": "m/s", "review": "m/r", "cheap": "m/c"}, "daily_budget_usd": 1.0, "free": False})
    monkeypatch.setattr(llm, "api_key", lambda: "k")
    monkeypatch.setattr(llm, "spent_today", lambda now=None: 1.2)
    monkeypatch.setattr(llm, "_post", lambda payload, key: calls.append(payload["model"]) or reply("{}"))
    monkeypatch.setattr(llm, "_account", lambda *a, **k: None)
    llm.chat("p", "review", now=NOW)
    with pytest.raises(llm.ModelUnavailable):
        llm.chat("p", "script", now=NOW)
    assert calls == ["m/r"]


# ---- 17 Nov 2026, plan Task 1: rank the free models by what they measurably did, per role ----
def _roster(*ids, ctx=131072):
    freemodels.refresh(NOW, get=lambda *a, **k: Resp([model(i, ctx=ctx) for i in ids]))


def _many(mid, role, ok, bad, seconds=10.0, reason="json"):
    for _ in range(ok):
        freemodels.record(mid, True, NOW, role=role, seconds=seconds)
    for _ in range(bad):
        freemodels.record(mid, False, NOW, role=role, seconds=seconds, reason=reason)


def test_choose_prefers_the_model_that_answered_valid_json_fast():
    _roster("a/plain:free", "gemma/flaky:free")                               # the family bonus puts gemma first before anything is measured
    assert freemodels.choose("script", NOW)[0] == "gemma/flaky:free"          # before any measurement the family bonus decides
    _many("a/plain:free", "script", ok=9, bad=1, seconds=20)
    _many("gemma/flaky:free", "script", ok=3, bad=7, seconds=20)
    # keep the cool-down out of it: a run of failures that ended with a success is not cooling
    freemodels.record("gemma/flaky:free", True, NOW, role="script", seconds=20)
    assert freemodels.choose("script", NOW)[0] == "a/plain:free"


def test_unknown_model_is_neutral_and_still_tried():
    _roster("a/good:free", "b/new:free", "c/bad:free")
    _many("a/good:free", "script", ok=8, bad=0)
    _many("c/bad:free", "script", ok=1, bad=6)
    freemodels.record("c/bad:free", True, NOW, role="script", seconds=10)
    got = freemodels.choose("script", NOW)
    assert got == ["a/good:free", "b/new:free", "c/bad:free"]
    assert freemodels.reliability("b/new:free", "script") == 0.5


def test_a_429_is_busy_not_unreliable():
    _roster("a/m1:free", "b/m2:free")
    freemodels.record("a/m1:free", False, NOW, status=429, role="script", seconds=1.0)
    assert freemodels.reliability("a/m1:free", "script") == 0.5               # unchanged: it was busy, not wrong
    h = freemodels._load()["health"]["a/m1:free"]
    assert h["fails"] == 0 and not h.get("roles", {}).get("script", {}).get("bad")
    assert "a/m1:free" in freemodels.choose("script", NOW + dt.timedelta(minutes=11))


def test_reliability_is_kept_per_role():
    _roster("a/m1:free")
    _many("a/m1:free", "script", ok=9, bad=0)
    _many("a/m1:free", "review", ok=0, bad=2)
    freemodels.record("a/m1:free", True, NOW, role="review", seconds=5)       # not cooling: the last answer was good
    assert freemodels.reliability("a/m1:free", "script") > 0.85
    assert freemodels.reliability("a/m1:free", "review") < 0.5


def test_speed_breaks_a_tie_between_equally_reliable_models():
    _roster("a/slow:free", "b/fast:free")
    _many("a/slow:free", "script", ok=4, bad=0, seconds=80)
    _many("b/fast:free", "script", ok=4, bad=0, seconds=12)
    assert freemodels.choose("script", NOW)[0] == "b/fast:free"
    assert freemodels.median_seconds("b/fast:free", "script") == 12


def test_an_older_health_file_without_roles_still_loads_and_ranks():
    _roster("a/m1:free", "b/m2:free")
    d = freemodels._load()
    d["health"] = {"b/m2:free": {"fails": 0, "ok": 4}}
    freemodels._save(d)
    assert freemodels.choose("script", NOW)[0] == "b/m2:free"
    assert freemodels.reliability("b/m2:free", "script") > 0.5


def test_a_cut_off_json_answer_is_counted_with_its_finish_reason():
    _roster("a/m1:free")
    freemodels.record("a/m1:free", False, NOW, role="script", seconds=60, reason="json", finish="length")
    freemodels.record("a/m1:free", False, NOW, role="script", seconds=30, reason="json", finish="stop")
    c = freemodels.failure_report()
    assert c["a/m1:free"]["script"]["json_bad"] == 2 and c["a/m1:free"]["script"]["finish"] == {"length": 1, "stop": 1}


def test_free_chat_times_each_call_and_records_why_a_reply_was_not_json(router, monkeypatch):
    stamps = [100.0, 142.0, 200.0, 207.0]                                     # call one took 42 s, call two took 7 s
    monkeypatch.setattr(llm.time, "monotonic", lambda: stamps.pop(0) if len(stamps) > 1 else stamps[0])
    seen = []

    def post(payload, key):
        seen.append(payload["model"])
        if len(seen) == 1:
            return {"choices": [{"message": {"content": '{"lines": [{"n": 1, "text": "cut'}, "finish_reason": "length"}], "usage": {}}
        return reply('{"ok": 1}')

    monkeypatch.setattr(llm, "_post", post)
    assert llm._free_chat("p", "script", llm.load_config(), "k", NOW) == {"ok": 1}
    rep = freemodels.failure_report()
    first, second = seen[0], seen[1]
    assert rep[first]["script"]["finish"] == {"length": 1} and rep[first]["script"]["json_bad"] == 1
    assert freemodels.median_seconds(second, "script") == 7.0                 # the second call took 207 - 200 seconds
