"""The doctor watches disk space (asks the owner to look, never deletes) and reports how many free models can be asked (20 Nov 2026)."""
import datetime as dt
from types import SimpleNamespace

import doctor
import freemodels
import llm

NOW = dt.datetime(2026, 11, 20, 12, tzinfo=dt.timezone.utc)


def test_low_disk_space_is_a_setup_request_that_never_deletes(monkeypatch):
    monkeypatch.setattr(doctor, "free_gb", lambda usage=None: 8.0)
    got = {n["need"]: n for n in doctor.needs(200, NOW)}
    assert "disk space" in got and "8 GB" in got["disk space"]["why"]
    text = " ".join(got["disk space"]["commands"]).lower()
    assert "rm " not in text and "never deletes" in text
    monkeypatch.setattr(doctor, "free_gb", lambda usage=None: 250.0)
    assert "disk space" not in {n["need"] for n in doctor.needs(200, NOW)}


def test_free_gb_reads_the_disk_and_survives_an_error():
    assert doctor.free_gb(lambda p: SimpleNamespace(free=42e9)) == 42.0
    def broken(p):
        raise OSError("gone")
    assert doctor.free_gb(broken) is None


def test_provider_status_counts_what_can_be_asked_now(monkeypatch):
    monkeypatch.setattr(llm, "extra_models", lambda role: ["extra:a", "extra:b"])
    monkeypatch.setattr(freemodels, "roster_ids", lambda: ["x/m:free", "y/n:free", "z/o:free"])
    monkeypatch.setattr(freemodels, "available", lambda m, now: m in ("extra:a", "y/n:free"))
    got = doctor.provider_status(NOW)
    assert got["own_provider"] == {"models": 2, "available": 1} and got["openrouter_free"] == {"models": 3, "available": 1}
    assert got["paid_allowed"] is False  # the shipped default: paid models off


def test_the_doctor_asks_the_owner_to_open_the_provider_app_when_it_does_not_answer(monkeypatch):
    import llm

    monkeypatch.setattr(llm, "extra_cfg", lambda: {"url": "http://127.0.0.1:31415/v1", "key": "k", "script": [], "review": []})
    down = {n["need"]: n for n in doctor.needs(200, NOW, reach=lambda url: False)}
    assert "own model provider" in down and "FreeLLMAPI" in down["own model provider"]["why"]
    assert any("31415/v1/models" in c for c in down["own model provider"]["commands"])
    assert "own model provider" not in {n["need"] for n in doctor.needs(200, NOW, reach=lambda url: True)}
    asked = []
    monkeypatch.setattr(llm, "extra_cfg", lambda: {"url": "https://api.example.com/v1", "key": "k", "script": [], "review": []})
    assert "own model provider" not in {n["need"] for n in doctor.needs(200, NOW, reach=lambda url: asked.append(url) or False)}
    assert asked == []                                                                  # a remote provider is not an app on this PC: never probed here
    monkeypatch.setattr(llm, "extra_cfg", lambda: None)
    assert "own model provider" not in {n["need"] for n in doctor.needs(200, NOW, reach=lambda url: False)}


def test_provider_answers_counts_any_http_reply_and_not_a_refused_connection():
    import requests

    assert doctor.provider_answers("http://127.0.0.1:1/v1", get=lambda *a, **k: object()) is True
    def refused(*a, **k):
        raise requests.ConnectionError("refused")
    assert doctor.provider_answers("http://127.0.0.1:1/v1", get=refused) is False
