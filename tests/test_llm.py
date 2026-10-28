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
    assert llm.api_key() == "from-file"  # the dashboard's saved key wins
    llm.SETTINGS_FILE.write_text("{}")
    assert llm.api_key() == "from-env"


def test_estimate_costs_from_prices():
    prices = {"script": (2.0, 10.0), "review": (4.0, 20.0), "cheap": (0.1, 0.5)}
    e = llm.estimate(prices, docs_per_day=1, shorts_per_day=1, days=30)
    doc = e["per_doc_usd"]
    t = llm.TOKENS["doc"]
    assert doc == pytest.approx(t["script"][0] * 2 / 1e6 + t["script"][1] * 10 / 1e6 + t["review"][0] * 4 / 1e6 + t["review"][1] * 20 / 1e6 + t["cheap"][0] * 0.1 / 1e6 + t["cheap"][1] * 0.5 / 1e6)
    with_art = llm.estimate(prices, docs_per_day=1, shorts_per_day=1, days=30, art=(0.544, 0.204))
    assert with_art["per_doc_usd"] == pytest.approx(doc + 0.544) and with_art["art_per_doc_usd"] == 0.544 and with_art["per_day_usd"] > e["per_day_usd"]
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


def test_the_fact_checker_is_asked_with_no_randomness_and_the_writer_with_some(monkeypatch):
    enable(monkeypatch)
    sent = []
    monkeypatch.setattr(llm, "_post", lambda payload, key: sent.append(payload) or reply('{"ok": 1}'))
    for role in ("review", "script", "cheap"):
        llm.chat(f"prompt for {role}", role, fallback=LOCAL, now=NOW)
    assert {p["model"]: p["temperature"] for p in sent} == {"vendor/checker": 0.0, "vendor/writer": 0.7, "vendor/small": 0.3}


def test_spend_inside_a_cost_scope_is_added_to_that_video_and_the_outer_scope_wins(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    enable(monkeypatch)
    monkeypatch.setattr(llm, "_post", lambda payload, key: reply('{"ok": 1}', cost=0.25))
    llm.chat("outside any video", "script", fallback=LOCAL, now=NOW)
    assert llm.video_cost("doc-a") == 0.0
    with llm.cost_scope("doc-a"):
        llm.chat("one", "script", fallback=LOCAL, now=NOW)
        with llm.cost_scope("doc-b"):  # a nested job (a review inside a repair) is part of the repair's video
            llm.chat("two", "review", fallback=LOCAL, now=NOW)
    assert llm.video_cost("doc-a") == pytest.approx(0.5) and llm.video_cost("doc-b") == 0.0
    assert llm.spent_today(NOW) == pytest.approx(0.75)  # the daily total still counts everything


def test_two_writers_of_the_usage_file_do_not_lose_each_others_calls(monkeypatch):
    import threading
    enable(monkeypatch)
    threads = [threading.Thread(target=lambda: [llm.record(NOW, "script", "m", 1, 1, 0.01) for _ in range(20)]) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert json.loads(llm.USAGE_FILE.read_text())["2026-10-19"]["calls"] == 80


def test_charges_to_decorator_and_merge_cost(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    enable(monkeypatch)
    monkeypatch.setattr(llm, "_post", lambda payload, key: reply('{"ok": 1}', cost=0.1))

    @llm.charges_to(lambda slug, *a, **k: slug)
    def job(slug):
        llm.chat("x", "script", fallback=LOCAL, now=NOW)

    job("doc-z")
    assert llm.video_cost("doc-z") == pytest.approx(0.1)
    with llm.cost_scope("pending:The Topic"):
        llm.chat("script", "script", fallback=LOCAL, now=NOW)
    llm.merge_cost("pending:The Topic", "doc-z")
    assert llm.video_cost("doc-z") == pytest.approx(0.2) and llm.video_cost("pending:The Topic") == 0.0


def test_a_make_function_charges_its_spend_to_the_new_videos_folder(monkeypatch, tmp_path):
    import run
    monkeypatch.setattr(config, "ROOT", tmp_path)
    enable(monkeypatch)
    monkeypatch.setattr(llm, "_post", lambda payload, key: reply('{"ok": 1}', cost=0.3))

    def make(topic):
        llm.chat("write the script", "script", fallback=LOCAL, now=NOW)
        return tmp_path / "output" / "doc-new-video"

    folder = run._charged(make, "A topic")
    assert folder.name == "doc-new-video" and llm.video_cost("doc-new-video") == pytest.approx(0.3)


# ---- prompt caching (28 Oct 2026) ----
BIG = "SOURCE ARTICLE. " * 200  # about 3,200 characters: over the cache minimum


def test_a_long_repeated_part_is_sent_as_a_cache_block_with_the_rest_after_it(monkeypatch):
    enable(monkeypatch, models={"script": "anthropic/claude-sonnet-5.5", "review": "anthropic/claude-haiku-5.5", "cheap": "anthropic/claude-haiku-5.5"})
    sent = []
    monkeypatch.setattr(llm, "_post", lambda payload, key: sent.append(payload) or reply('{"ok": 1}'))
    assert llm.chat(llm.cached(BIG, "Write chapter 3."), "script", fallback=LOCAL, now=NOW) == {"ok": 1}
    blocks = sent[0]["messages"][0]["content"]
    assert blocks[0] == {"type": "text", "text": BIG, "cache_control": {"type": "ephemeral"}}
    assert blocks[1]["text"].endswith("Write chapter 3.") and "cache_control" not in blocks[1]
    assert llm.CACHE_MARK not in json.dumps(blocks)


def test_the_acting_agents_playbook_goes_after_the_cached_part_so_every_agent_shares_one_cache(monkeypatch):
    import playbook
    enable(monkeypatch, models={"script": "anthropic/claude-sonnet-5.5", "review": "anthropic/claude-haiku-5.5", "cheap": "anthropic/claude-haiku-5.5"})
    sent = []
    monkeypatch.setattr(llm, "_post", lambda payload, key: sent.append(payload) or reply('{"ok": 1}'))
    for agent in ("seo", "fixer"):
        with playbook.acting_as(agent):
            llm.chat(llm.cached(BIG, "task"), "script", fallback=LOCAL, now=NOW)
    first, second = (s["messages"][0]["content"] for s in sent)
    assert first[0] == second[0] == {"type": "text", "text": BIG, "cache_control": {"type": "ephemeral"}}
    assert "Playbook of the" in first[1]["text"] and first[1]["text"] != second[1]["text"]


def test_a_short_part_or_a_model_that_is_not_anthropic_is_sent_as_plain_text(monkeypatch):
    enable(monkeypatch)  # vendor/writer
    sent = []
    monkeypatch.setattr(llm, "_post", lambda payload, key: sent.append(payload) or reply('{"ok": 1}'))
    llm.chat(llm.cached(BIG, "rest"), "script", fallback=LOCAL, now=NOW)
    assert sent[-1]["messages"][0]["content"] == BIG + "rest"
    enable(monkeypatch, models={"script": "anthropic/claude-sonnet-5.5", "review": "b/x", "cheap": "c/x"})
    llm.chat(llm.cached("short", "rest"), "script", fallback=LOCAL, now=NOW)
    assert sent[-1]["messages"][0]["content"] == "shortrest"


def test_the_mark_never_reaches_the_local_model_or_the_free_models(monkeypatch):
    seen = []
    assert llm.chat(llm.cached(BIG, "rest"), "script", fallback=lambda p: seen.append(p) or {"from": "local"}, now=NOW) == {"from": "local"}
    assert seen == [BIG + "rest"]
    enable(monkeypatch, free=True, models={"script": "", "review": "", "cheap": ""})
    free = []
    monkeypatch.setattr(llm, "_free_chat", lambda prompt, *a: free.append(prompt) or {"free": 1})
    llm.chat(llm.cached(BIG, "rest"), "cheap", now=NOW)
    assert free == [BIG + "rest"]


def test_cached_input_tokens_are_counted_next_to_the_real_cost(monkeypatch):
    enable(monkeypatch, models={"script": "anthropic/claude-sonnet-5.5", "review": "b/x", "cheap": "c/x"})
    body = reply('{"ok": 1}', cost=0.01)
    body["usage"]["prompt_tokens_details"] = {"cached_tokens": 800}
    monkeypatch.setattr(llm, "_post", lambda payload, key: body)
    llm.chat(llm.cached(BIG, "rest"), "script", fallback=LOCAL, now=NOW)
    day = json.loads(llm.USAGE_FILE.read_text())["2026-10-19"]
    assert day["by_role"]["script"]["cached_in"] == 800 and day["usd"] == pytest.approx(0.01)
