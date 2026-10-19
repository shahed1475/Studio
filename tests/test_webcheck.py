import pytest

import llm
import webcheck


@pytest.fixture
def paid(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "CONFIG_FILE", tmp_path / "llm.json")
    monkeypatch.setattr(llm, "USAGE_FILE", tmp_path / "usage.json")
    monkeypatch.setattr(llm, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(llm, "api_key", lambda: "k")
    llm.save_config({**llm.load_config(), "enabled": True, "models": {"script": "anthropic/claude-sonnet-5.5", "review": "anthropic/claude-haiku-5.5", "cheap": "anthropic/claude-haiku-5.5"}})


def body(text, urls=(), cost=0.012):
    return {"choices": [{"message": {"content": text, "annotations": [{"type": "url_citation", "url_citation": {"url": u}} for u in urls]}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "cost": cost}}


def test_a_supported_claim_comes_back_with_its_pages(paid, monkeypatch):
    seen = []
    monkeypatch.setattr(llm, "_post", lambda payload, key: seen.append(payload) or body('{"verdict": "supported", "explanation": "x"}', ["https://a.org/x", "https://a.org/x", "http://insecure"]))
    r = webcheck.verify("French diggers arrived in 1893.", "Delphi")
    assert r == {"verdict": "supported", "fact": "", "urls": ["https://a.org/x"]}
    assert seen[0]["plugins"] == [{"id": "web", "max_results": 3}] and "untrusted" in seen[0]["messages"][0]["content"]


def test_a_wrong_claim_comes_back_corrected(paid, monkeypatch):
    monkeypatch.setattr(llm, "_post", lambda p, k: body('{"verdict": "contradicted", "fact": "The removals began in 1801."}', ["https://a.org/e"]))
    r = webcheck.verify("In 1799 Elgin took them.")
    assert r["verdict"] == "contradicted" and r["fact"] == "The removals began in 1801."


def test_supported_without_a_page_to_show_is_only_uncertain(paid, monkeypatch):
    monkeypatch.setattr(llm, "_post", lambda p, k: body('{"verdict": "supported"}', []))
    assert webcheck.verify("x")["verdict"] == "uncertain"


def test_no_credit_no_key_or_a_failed_call_never_raises_and_says_uncertain(paid, monkeypatch):
    def boom(p, k):
        raise RuntimeError("402 no credit")

    monkeypatch.setattr(llm, "_post", boom)
    assert webcheck.verify("x")["verdict"] == "uncertain"
    monkeypatch.setattr(llm, "api_key", lambda: "")
    monkeypatch.setattr(llm, "_post", lambda p, k: pytest.fail("no key: no call"))
    assert webcheck.verify("x")["verdict"] == "uncertain"


def test_the_daily_dollar_cap_stops_web_checks(paid, monkeypatch):
    monkeypatch.setattr(llm, "spent_today", lambda now=None: 999)
    monkeypatch.setattr(llm, "_post", lambda p, k: pytest.fail("cap reached"))
    assert webcheck.verify("x")["verdict"] == "uncertain"
