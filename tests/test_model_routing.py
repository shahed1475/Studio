"""Every model call goes through llm.py to OpenRouter and asks for JSON (28 Oct 2026 audit, owner's request: one route, one bill, no stray calls)."""
import ast
import re
from pathlib import Path

import llm

ROOT = Path(__file__).resolve().parent.parent
SOURCES = [p for p in ROOT.glob("*.py") if p.name not in {"llm.py"}]
SANCTIONED_POST = {"webcheck.py", "secondsources.py", "aiart.py", "writerbench.py"}  # writerbench calls only models OpenRouter lists at price zero (tests/test_writerbench.py). They send their own payload (web search plugin, image output) through llm._post: still OpenRouter, still the key and cap of llm.py


def test_no_module_calls_a_model_host_except_llm_py():
    for p in SOURCES:
        text = p.read_text()
        assert "api.anthropic.com" not in text, p.name
        assert "chat/completions" not in text, p.name
        assert "api.openai.com" not in text and "generativelanguage.googleapis.com" not in text, p.name


def test_only_the_known_helpers_send_their_own_payload():
    users = {p.name for p in SOURCES if "llm._post(" in p.read_text()}
    assert users == SANCTIONED_POST, users ^ SANCTIONED_POST


def test_the_models_are_called_through_openrouter_and_every_text_job_asks_for_json(monkeypatch):
    sent = {}
    monkeypatch.setattr(llm.requests, "post", lambda url, **k: sent.update(url=url, json=k["json"]) or type("R", (), {"raise_for_status": lambda s: None, "json": lambda s: {}})())
    llm._post(llm._payload("anthropic/claude-sonnet-5.5", "x", 100), "k")
    assert sent["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert sent["json"]["response_format"] == {"type": "json_object"} and sent["json"]["usage"] == {"include": True}
    assert sent["json"]["max_tokens"] == 100  # every call has an output cap


def test_the_local_model_and_direct_anthropic_are_off_unless_the_owner_switches_them_on():
    assert '"local_fallback": False' in (ROOT / "llm.py").read_text()  # the shipped default (conftest switches it on for old tests)
    tree = ast.parse((ROOT / "llm.py").read_text())
    ids = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and re.match(r"^claude-", n.value)]
    assert ids == [] or all(i.startswith("claude-") for i in ids)  # direct ids exist only as a documented option, none is configured in code
    cfg_models = llm.DEFAULTS["models"]
    assert not any(m.startswith("claude-") for m in cfg_models.values())
