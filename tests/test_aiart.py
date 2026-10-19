import base64
import io

import aiart
import config
import llm
import pytest
from PIL import Image


@pytest.fixture
def art(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "CONFIG_FILE", tmp_path / "llm.json")
    monkeypatch.setattr(llm, "USAGE_FILE", tmp_path / "usage.json")
    monkeypatch.setattr(llm, "api_key", lambda: "k")
    monkeypatch.setattr(config, "CACHE", tmp_path / "cache")
    aiart._off_until.clear()
    llm.save_config({**llm.load_config(), "ai_art": True, "daily_budget_usd": 1.0})


def png_body(cost=0.034):
    buf = io.BytesIO()
    Image.new("RGB", (64, 36), (200, 150, 90)).save(buf, "PNG")
    url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    return {"choices": [{"message": {"images": [{"image_url": {"url": url}}]}}], "usage": {"prompt_tokens": 20, "completion_tokens": 1100, "cost": cost}}


def test_a_scene_is_drawn_cached_credited_and_counted_in_the_daily_spend(art, monkeypatch):
    calls = []
    monkeypatch.setattr(llm, "_post", lambda payload, key: calls.append(payload) or png_body())
    got = aiart.generate("The piper led the children away.", "piper", "Pied Piper", vertical=False)
    assert got[0].exists() and got[1] == aiart.CREDIT and calls[0]["modalities"] == ["image", "text"]
    assert "16:9" in calls[0]["messages"][0]["content"] and "no text" in calls[0]["messages"][0]["content"]
    assert round(llm.spent_today(), 3) == 0.034
    assert aiart.generate("The piper led the children away.", "piper", "Pied Piper")[0] == got[0] and len(calls) == 1  # the second time comes from the cache


def test_shorts_ask_for_a_vertical_picture():
    assert "9:16" in aiart.prompt_for("l", "v", "t", True) and "16:9" in aiart.prompt_for("l", "v", "t", False)


def test_off_by_default_without_a_key_over_the_cap_and_after_a_402(art, monkeypatch):
    monkeypatch.setattr(llm, "_post", lambda p, k: (_ for _ in ()).throw(RuntimeError("402 Payment Required")))
    assert aiart.generate("a", "b", "c") is None and aiart.enabled() is False  # a 402 pauses drawing for the day
    aiart._off_until.clear()
    monkeypatch.setattr(llm, "spent_today", lambda now=None: 5.0)
    monkeypatch.setattr(llm, "_post", lambda p, k: pytest.fail("over the dollar cap"))
    assert aiart.generate("a", "b", "c") is None
    llm.save_config({**llm.load_config(), "ai_art": False})
    monkeypatch.setattr(llm, "spent_today", lambda now=None: 0.0)
    assert aiart.generate("a", "b", "c") is None  # the switch is off


def test_ai_art_setting_is_validated():
    assert llm.validate_config({"ai_art": True}) == {"ai_art": True}
    with pytest.raises(ValueError):
        llm.validate_config({"ai_art": "yes"})
