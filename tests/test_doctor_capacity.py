"""The doctor watches disk space (asks the owner to look, never deletes) and reports how many free models can be asked (20 Nov 2026)."""
import datetime as dt
import json
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


def test_provider_status_counts_what_can_be_asked_now(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "extra_models", lambda role: ["extra:a", "extra:b"])
    monkeypatch.setattr(freemodels, "roster_ids", lambda: ["x/m:free", "y/n:free", "z/o:free"])
    monkeypatch.setattr(freemodels, "available", lambda m, now: m in ("extra:a", "y/n:free", "z/o:free"))
    f = tmp_path / "free_models.json"
    f.write_text(json.dumps({"health": {"extra:a": {"ok": 3, "last_ok": "2026-11-22T10:00:00Z"}, "y/n:free": {"ok": 9, "fails": 0},
                                        # z/o: its cool-down has run out, but it has failed since its last success: not counted (22 Nov 2026)
                                        "z/o:free": {"ok": 5, "fails": 4, "last_ok": "2026-11-21T10:00:00Z", "last_fail": "2026-11-22T09:00:00Z"}}}))
    monkeypatch.setattr(freemodels, "FILE", f)
    monkeypatch.setattr(llm, "openrouter_refused", lambda now=None, key=None: None)
    got = doctor.provider_status(NOW)
    assert got["own_provider"] == {"models": 2, "available": 1} and got["openrouter_free"] == {"models": 3, "available": 1}
    monkeypatch.setattr(llm, "openrouter_refused", lambda now=None, key=None: {"status": 401})
    assert doctor.provider_status(NOW)["openrouter_free"]["available"] == 0  # a refused key: no OpenRouter model can be asked
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


def test_the_key_check_says_what_it_saw_and_a_refused_key_stops_the_router(monkeypatch, tmp_path):
    """22 Nov 2026: the doctor reported 12/12 free models while OpenRouter refused the key, because it only checked that a key existed."""
    monkeypatch.setattr(llm, "USAGE_FILE", tmp_path / "llm_usage.json")
    monkeypatch.setattr(llm, "api_key", lambda: "sk-or-dead")
    import agentlog
    monkeypatch.setattr(agentlog, "event", lambda *a, **k: None)
    got = doctor.probe_openrouter_key(NOW, get=lambda url: 401)
    assert got["state"] == "FAILED" and got["source"].startswith("GET https://openrouter.ai") and got["checked_at"]
    assert llm.openrouter_refused(NOW, "sk-or-dead")                                    # the router now skips OpenRouter too
    assert "model key refused" in {n["need"] for n in doctor.needs(200, NOW, reach=lambda u: True)}
    assert doctor.probe_openrouter_key(NOW, get=lambda url: 200)["state"] == "HEALTHY"

    def boom(url):
        raise OSError("no network")
    assert doctor.probe_openrouter_key(NOW, get=boom)["state"] == "UNKNOWN"            # a check that could not run is never "healthy"
    monkeypatch.setattr(llm, "api_key", lambda: "")
    assert doctor.probe_openrouter_key(NOW, get=lambda url: 200)["state"] == "NOT_CONFIGURED"


def test_every_agent_row_carries_its_health_source_check_time_and_last_success():
    lines = ["2026-11-22T10:00:00Z backup python run.py backup -> exit 0", "2026-11-22T11:00:00Z backup python run.py backup -> exit 1",
             "2026-11-22T12:00:00Z backup python run.py backup -> exit 1"]
    rows = {r["agent"]: r for r in doctor.scan(NOW, state={"backup": "2026-11-22T12:00:00Z"}, lines=lines)}
    b = rows["backup"]
    assert b["health"] == "FAILED" and b["last_success"] == "2026-11-22T10:00:00Z" and b["failure_reason"] and b["checked_at"] and "worker.log" in b["source"]
    assert all(r["health"] in ("HEALTHY", "STALE", "FAILED", "NOT_TESTED") for r in rows.values())


def test_an_old_doctor_report_is_shown_as_stale_never_as_healthy(tmp_path):
    import risk
    ev, rep = tmp_path / "eval.json", tmp_path / "doctor.json"
    ev.write_text(json.dumps({"at": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"), "passed": 3, "failed": 0, "cases": []}))
    rep.write_text(json.dumps({"at": (NOW - dt.timedelta(hours=20)).strftime("%Y-%m-%dT%H:%M:%SZ"), "agents": [], "needs": []}))
    row = risk.agents_row(NOW, result=ev, bus=tmp_path / "bus.json", doctor_report=rep)
    assert row["level"] == "watch" and "STALE" in row["evidence"]
