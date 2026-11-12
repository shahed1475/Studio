import base64
import datetime as dt
import io
import json

import aiart
import config
import freeart
import llm
import pytest
import tenantmode
from PIL import Image

NOW = dt.datetime(2026, 11, 13, 10, 0, tzinfo=dt.timezone.utc)


def jpeg():
    buf = io.BytesIO()
    Image.new("RGB", (64, 36), (120, 90, 60)).save(buf, "JPEG")
    return buf.getvalue()


def ok(calls):
    def fetch(url, headers, body, ctype):
        calls.append((url, headers, body))
        return 200, json.dumps({"success": True, "result": {"image": base64.b64encode(jpeg()).decode()}}).encode()
    return fetch


@pytest.fixture
def free(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "CONFIG_FILE", tmp_path / "llm.json")
    monkeypatch.setattr(llm, "USAGE_FILE", tmp_path / "usage.json")
    monkeypatch.setattr(llm, "api_key", lambda: "")
    monkeypatch.setattr(config, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(freeart, "USAGE", tmp_path / "cf.json")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "SECRET-TOKEN")
    monkeypatch.setattr(tenantmode, "is_tenant", lambda: False)
    freeart._off.clear()
    aiart._off_until.clear()
    llm.save_config({**llm.load_config(), "free_art": True})


def test_off_by_default_even_with_keys(free):
    llm.save_config({**llm.load_config(), "free_art": False})
    assert freeart.available(now=NOW) is False and aiart.enabled(NOW) is False


def test_a_scene_is_drawn_free_credited_counted_and_cached(free, tmp_path):
    calls = []
    dest = tmp_path / "a.jpg"
    got = freeart.draw("a lighthouse", "film", dest, "photo", fetch=ok(calls), now=NOW)
    assert got[0] == dest and dest.exists() and "ai-generated" in got[1].lower() and "not real photographs" in got[1]
    assert calls[0][1]["Authorization"] == "Bearer SECRET-TOKEN" and b"1024" in calls[0][2] and b"576" in calls[0][2]
    assert freeart.used_today("2026-11-13") == pytest.approx(freeart.neurons(1024, 576)) == pytest.approx(104.2)


def test_aiart_generate_uses_the_free_account_and_never_the_paid_model(free, monkeypatch):
    monkeypatch.setattr(freeart, "_fetch", ok([]))
    monkeypatch.setattr(llm, "_post", lambda *a, **k: pytest.fail("the paid model must not be called"))
    got = aiart.generate("The piper led the children away.", "piper", "Pied Piper", vertical=True, now=NOW)
    assert got and got[0].exists() and "Cloudflare" in got[1]
    assert aiart.generate("The piper led the children away.", "piper", "Pied Piper", vertical=True, now=NOW)[0] == got[0]  # cached


def test_the_daily_allowance_stops_drawing(free):
    llm.save_config({**llm.load_config(), "free_art_cap": 100})
    calls = []
    assert freeart.draw("x", "film", config.CACHE / "x.jpg", fetch=ok(calls), now=NOW) is None and calls == []  # 104 Neurons would pass the 100 cap
    assert freeart.usable(now=NOW) is False


def test_a_busy_answer_pauses_and_a_bad_key_stops_the_day(free, tmp_path):
    busy = lambda *a: (429, b"{}")
    assert freeart.draw("x", "film", tmp_path / "x.jpg", fetch=busy, now=NOW) is None
    assert freeart.available(now=NOW) is False and freeart.available(now=NOW + dt.timedelta(minutes=11)) is True
    freeart._off.clear()
    denied = lambda *a: (403, b"{}")
    assert freeart.draw("x", "film", tmp_path / "x.jpg", fetch=denied, now=NOW) is None
    assert freeart.available(now=NOW + dt.timedelta(hours=3)) is False


def test_a_user_studio_never_uses_the_owners_account(free, monkeypatch):
    monkeypatch.setattr(tenantmode, "is_tenant", lambda: True)
    assert freeart.available(now=NOW) is False


def test_a_non_image_answer_is_a_failure_and_the_token_never_leaks(free, tmp_path):
    bad = lambda *a: (200, json.dumps({"success": True, "result": {"image": base64.b64encode(b"nope").decode()}}).encode())
    assert freeart.draw("x", "film", tmp_path / "x.jpg", fetch=bad, now=NOW) is None and not (tmp_path / "x.jpg").exists()
