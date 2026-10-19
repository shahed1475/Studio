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


def test_review_uses_a_different_free_model_than_the_writer(router, monkeypatch):
    used = {}

    def post(payload, key):
        used.setdefault(post.role, payload["model"])
        return reply("{}")

    monkeypatch.setattr(llm, "_post", post)
    post.role = "script"
    llm.chat("p", "script", fallback=None, now=NOW)
    post.role = "review"
    llm.chat("p", "review", fallback=None, now=NOW)
    assert used["script"] != used["review"]


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
