import json
import os
from datetime import datetime, timezone

import pytest

import config
import llm

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "CONFIG_FILE", tmp_path / "llm.json")
    monkeypatch.setattr(llm, "USAGE_FILE", tmp_path / "usage.json")
    monkeypatch.setattr(llm, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)


def enable(monkeypatch, **over):
    cfg = {**llm.DEFAULTS, "enabled": True, "models": {"script": "vendor/writer", "review": "vendor/checker", "cheap": "vendor/small"}, **over}
    llm.save_config(cfg)
    llm.SETTINGS_FILE.write_text(json.dumps({"openrouter_key": "sk-test"}))


def reply(content, cost=0.002, tin=1000, tout=200):
    return {"choices": [{"message": {"content": content}}], "usage": {"prompt_tokens": tin, "completion_tokens": tout, "cost": cost}}


LOCAL = lambda prompt: {"from": "local"}


def test_defaults_are_off_and_local():
    assert llm.load_config()["enabled"] is False
    assert llm.chat("hi", "script", fallback=LOCAL, now=NOW) == {"from": "local"}


def test_uses_openrouter_when_enabled_and_records_spend(monkeypatch):
    enable(monkeypatch)
    sent = []
    monkeypatch.setattr(llm, "_post", lambda payload, key: sent.append((payload, key)) or reply('{"ok": 1}'))
    assert llm.chat("write it", "script", fallback=LOCAL, now=NOW) == {"ok": 1}
    payload, key = sent[0]
    assert payload["model"] == "vendor/writer" and payload["max_tokens"] == 6000 and payload["response_format"] == {"type": "json_object"}
    assert key == "sk-test"
    assert llm.spent_today(NOW) == pytest.approx(0.002)
    day = json.loads(llm.USAGE_FILE.read_text())["2026-10-19"]
    assert day["calls"] == 1 and day["by_role"]["script"]["usd"] == pytest.approx(0.002)


def test_local_when_key_missing_or_role_model_empty(monkeypatch):
    enable(monkeypatch)
    llm.SETTINGS_FILE.write_text("{}")
    monkeypatch.setattr(llm, "_post", lambda *a: pytest.fail("must not call"))
    assert llm.chat("x", "script", fallback=LOCAL, now=NOW) == {"from": "local"}
    enable(monkeypatch, models={"script": "", "review": "b", "cheap": "c"})
    assert llm.chat("x", "script", fallback=LOCAL, now=NOW) == {"from": "local"}


def test_budget_reached_uses_local_without_calling(monkeypatch):
    enable(monkeypatch, daily_budget_usd=0.05)
    monkeypatch.setattr(llm, "_post", lambda *a: reply("{}", cost=0.05))
    llm.chat("x", "cheap", fallback=LOCAL, now=NOW)
    monkeypatch.setattr(llm, "_post", lambda *a: pytest.fail("cap reached, must not call"))
    assert llm.chat("x", "cheap", fallback=LOCAL, now=NOW) == {"from": "local"}


def test_new_day_starts_at_zero(monkeypatch):
    enable(monkeypatch)
    monkeypatch.setattr(llm, "_post", lambda *a: reply("{}", cost=0.5))
    llm.chat("x", "cheap", fallback=LOCAL, now=NOW)
    assert llm.spent_today(NOW.replace(day=20)) == 0


def test_parses_json_in_code_fences_and_chatter(monkeypatch):
    enable(monkeypatch)
    monkeypatch.setattr(llm, "_post", lambda *a: reply('Sure!\n```json\n{"a": [1, 2]}\n```\nDone.'))
    assert llm.chat("x", "cheap", fallback=LOCAL, now=NOW) == {"a": [1, 2]}


def test_bad_json_twice_falls_back_and_records_reason(monkeypatch):
    enable(monkeypatch)
    calls = []
    monkeypatch.setattr(llm, "_post", lambda *a: calls.append(1) or reply("not json at all"))
    assert llm.chat("x", "cheap", fallback=LOCAL, now=NOW) == {"from": "local"}
    assert len(calls) == 2
    assert "invalid JSON" in json.loads(llm.USAGE_FILE.read_text())["2026-10-19"]["fallbacks"][0]


def test_http_error_falls_back_never_raises(monkeypatch):
    enable(monkeypatch)
    def boom(*a):
        raise ConnectionError("network down")
    monkeypatch.setattr(llm, "_post", boom)
    assert llm.chat("x", "cheap", fallback=LOCAL, now=NOW) == {"from": "local"}
    assert "network down" in json.loads(llm.USAGE_FILE.read_text())["2026-10-19"]["fallbacks"][0]


def test_missing_cost_is_estimated_from_prices(monkeypatch):
    enable(monkeypatch)
    monkeypatch.setattr(llm, "model_prices", lambda: {"vendor/small": (1.0, 5.0)})
    body = {"choices": [{"message": {"content": "{}"}}], "usage": {"prompt_tokens": 1_000_000, "completion_tokens": 100_000}}
    monkeypatch.setattr(llm, "_post", lambda *a: body)
    llm.chat("x", "cheap", fallback=LOCAL, now=NOW)
    assert llm.spent_today(NOW) == pytest.approx(1.5)


def test_validate_config_rules():
    ok = llm.validate_config({"enabled": True, "daily_budget_usd": 2.5, "models": {"script": "anthropic/claude-sonnet-5.5"}})
    assert ok["models"]["script"] == "anthropic/claude-sonnet-5.5"
    for bad in ({"daily_budget_usd": 0}, {"daily_budget_usd": 1000}, {"enabled": "yes"}, {"max_output_tokens": 10},
                {"models": {"script": "has spaces"}}, {"models": {"nope": "a/b"}}, {"surprise": 1}):
        with pytest.raises(ValueError):
            llm.validate_config(bad)


def test_review_model_must_differ_from_writer():
    llm.save_config({**llm.DEFAULTS, "models": {"script": "a/b", "review": "", "cheap": ""}})
    with pytest.raises(ValueError, match="differ"):
        llm.validate_config({"models": {"review": "a/b"}})


def test_api_key_from_env_or_settings(monkeypatch):
    assert llm.api_key() == ""
    llm.SETTINGS_FILE.write_text(json.dumps({"openrouter_key": "from-file"}))
    assert llm.api_key() == "from-file"
    monkeypatch.setenv("OPENROUTER_API_KEY", "from-env")
    assert llm.api_key() == "from-env"


def test_estimate_costs_from_prices():
    prices = {"script": (2.0, 10.0), "review": (4.0, 20.0), "cheap": (0.1, 0.5)}
    e = llm.estimate(prices, docs_per_day=1, shorts_per_day=1, days=30)
    doc = e["per_doc_usd"]
    # doc: script 13000 in / 3000 out, review 2000/100, cheap 1700/450
    assert doc == pytest.approx(13000 * 2 / 1e6 + 3000 * 10 / 1e6 + 2000 * 4 / 1e6 + 100 * 20 / 1e6 + 1700 * 0.1 / 1e6 + 450 * 0.5 / 1e6)
    assert e["per_month_usd"] == pytest.approx((e["per_doc_usd"] + e["per_short_usd"]) * 30 + e["weekly_usd"] * 30 / 7)
    assert set(e["by_role"]) == {"script", "review", "cheap"}


def test_decide_normalises_probabilities(monkeypatch):
    monkeypatch.setattr(llm, "chat", lambda prompt, role="cheap", fallback=None, now=None: {"probs": {"yes": 3, "no": 1, "extra": 5}})
    d = llm.decide("Does the title match?", "state", ["yes", "no"])
    assert d["choice"] == "yes" and d["probs"] == {"yes": 0.75, "no": 0.25} and d["confidence"] == 0.75


def test_test_call_shows_real_error_without_fallback(monkeypatch):
    enable(monkeypatch)
    def boom(*a):
        raise ConnectionError("401 unauthorized")
    monkeypatch.setattr(llm, "_post", boom)
    r = llm.test_call("cheap")
    assert r["ok"] is False and "401" in r["error"]
    monkeypatch.setattr(llm, "_post", lambda *a: reply('{"ok": true}', cost=0.0001))
    r = llm.test_call("cheap")
    assert r["ok"] is True and r["model"] == "vendor/small" and r["usd"] == pytest.approx(0.0001)


def test_env_file_is_read_without_overriding_real_environment(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_text('# comment\nOPENROUTER_API_KEY="sk-or-test"\nOTHER=keep\nexport YT_X = spaced \n\nbad line\n')
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("OTHER", "already")
    monkeypatch.delenv("YT_X", raising=False)
    config.load_env(f)
    assert os.environ["OPENROUTER_API_KEY"] == "sk-or-test"
    assert os.environ["OTHER"] == "already"          # a real environment variable wins
    assert os.environ["YT_X"] == "spaced"
    config.load_env(tmp_path / "missing")            # no file: no error


def test_claude_ids_go_to_anthropic_and_come_back_openrouter_shaped(monkeypatch):
    sent = {}

    class R:
        def raise_for_status(self): pass
        def json(self): return {"content": [{"type": "text", "text": '{"ok": 1}'}], "usage": {"input_tokens": 12, "output_tokens": 5}}

    monkeypatch.setattr(llm.requests, "post", lambda url, **kw: sent.update(url=url, **kw) or R())
    body = llm._post({"model": "claude-sonnet-5-5", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 50, "response_format": {"type": "json_object"}}, "sk-ant-test")
    assert sent["url"] == "https://api.anthropic.com/v1/messages" and sent["headers"]["x-api-key"] == "sk-ant-test"
    assert "JSON" in sent["json"]["messages"][0]["content"]
    assert body["choices"][0]["message"]["content"] == '{"ok": 1}' and body["usage"] == {"prompt_tokens": 12, "completion_tokens": 5}


def test_claude_model_uses_anthropic_key_and_openrouter_ids_do_not(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-key-123456")
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key-123456")
    assert llm.key_for("claude-sonnet-5-5") == "ant-key-123456"
    assert llm.key_for("anthropic/claude-sonnet-4.5") == "or-key-123456"
    assert llm.is_claude("claude-opus-5-5") and not llm.is_claude("anthropic/claude-opus-5-5")


def test_claude_price_lookup_matches_openrouter_dots(monkeypatch):
    monkeypatch.setattr(llm, "model_prices", lambda: {"anthropic/claude-sonnet-4.5": (3.0, 15.0)})
    assert llm._usd("claude-sonnet-4-5", 1_000_000, 0) == 3.0
    assert llm._usd("claude-unknown-9", 1_000_000, 0) == llm.UNKNOWN_PRICE[0]  # an unknown model is priced high on purpose


def test_no_local_model_by_default_raises_model_unavailable(monkeypatch):
    monkeypatch.setitem(llm.DEFAULTS, "local_fallback", False)
    monkeypatch.setattr(llm, "CONFIG_FILE", llm.CONFIG_FILE)
    with pytest.raises(llm.ModelUnavailable):
        llm.chat("hi", "script", fallback=lambda p: {"from": "local"}, now=NOW)


def test_local_model_only_when_switched_on(monkeypatch):
    monkeypatch.setitem(llm.DEFAULTS, "local_fallback", True)
    assert llm.chat("hi", "script", fallback=lambda p: {"from": "local"}, now=NOW) == {"from": "local"}
