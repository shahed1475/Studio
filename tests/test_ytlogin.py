import datetime as dt

import agentlog
import config
import pytest
import risk
import ytlogin

NOW = dt.datetime(2026, 10, 21, 12, 0, tzinfo=dt.timezone.utc)


@pytest.fixture(autouse=True)
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "OUT", tmp_path / "output")
    monkeypatch.setattr(ytlogin, "STATE", tmp_path / "data" / "youtube_login.json")
    monkeypatch.setattr(agentlog, "FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(agentlog.subprocess, "run", lambda *a, **k: None)
    (tmp_path / "output").mkdir()
    return tmp_path


def test_without_a_recorded_consent_the_status_says_so_and_asks_to_watch():
    s = ytlogin.status(NOW)
    assert s["level"] == "watch" and s["consented_at"] is None and "no consent date" in s["detail"]


def test_in_testing_mode_the_login_runs_out_seven_days_after_consent():
    ytlogin.stamp(NOW - dt.timedelta(days=2), estimate=True)
    s = ytlogin.status(NOW)
    assert s["mode"] == "testing" and s["estimate"] is True and round(s["days_left"], 1) == 5.0 and s["level"] == "ok"
    ytlogin.stamp(NOW - dt.timedelta(days=5.5))
    assert ytlogin.status(NOW)["level"] == "watch"
    ytlogin.stamp(NOW - dt.timedelta(days=6.5))
    assert ytlogin.status(NOW)["level"] == "act"
    ytlogin.stamp(NOW - dt.timedelta(days=8))
    s = ytlogin.status(NOW)
    assert s["level"] == "act" and s["days_left"] < 0


def test_in_production_mode_age_alone_never_raises_a_flag():
    ytlogin.stamp(NOW - dt.timedelta(days=40), mode="production")
    s = ytlogin.status(NOW)
    assert s["mode"] == "production" and s["days_left"] is None and s["level"] == "ok"
    ytlogin.stamp(NOW)  # a new consent keeps the mode
    assert ytlogin.status(NOW)["mode"] == "production"


def test_a_failed_refresh_is_reported_at_once_with_the_steps_and_only_once_a_day():
    def expired():
        raise RuntimeError("invalid_grant: Token has been expired or revoked.")
    r = ytlogin.check(NOW, refresh=expired)
    assert r["ok"] is False and r["error"] == "expired"
    events = [e for e in agentlog.recent() if e["title"] == "The YouTube login expired"]
    assert len(events) == 1 and "Publish app" in events[0]["detail"] and "token.json" in events[0]["detail"]
    ytlogin.check(NOW + dt.timedelta(hours=3), refresh=expired)
    assert len([e for e in agentlog.recent() if e["title"] == "The YouTube login expired"]) == 1
    ytlogin.check(NOW + dt.timedelta(days=1), refresh=expired)
    assert len([e for e in agentlog.recent() if e["title"] == "The YouTube login expired"]) == 2


def test_a_working_refresh_is_recorded_and_a_missing_login_is_said_plainly():
    assert ytlogin.check(NOW, refresh=lambda: None)["ok"] is True and ytlogin.status(NOW)["last_check"]["ok"] is True
    def missing():
        raise FileNotFoundError("token.json")
    r = ytlogin.check(NOW, refresh=missing)
    assert r["ok"] is False and r["error"] == "not connected"


def test_the_risks_row_goes_to_act_on_a_failed_refresh_and_follows_the_age_otherwise(world):
    ytlogin.stamp(NOW - dt.timedelta(days=1))
    row = risk.login(NOW)
    assert row["id"] == "login" and row["level"] == "ok" and "6" in row["evidence"] and row["controls"]
    ytlogin.check(NOW, refresh=lambda: (_ for _ in ()).throw(RuntimeError("invalid_grant")))
    assert risk.login(NOW)["level"] == "act"


def test_connecting_stamps_the_consent_time(tmp_path, monkeypatch):
    import dashboard

    class Creds:
        def to_json(self):
            return "{}"

    class Flow:
        def run_local_server(self, **k):
            return Creds()
    import google_auth_oauthlib.flow as flow

    monkeypatch.setattr(flow.InstalledAppFlow, "from_client_secrets_file", classmethod(lambda cls, *a, **k: Flow()))
    monkeypatch.setattr(dashboard, "TOKEN", tmp_path / "token.json")
    monkeypatch.setattr(dashboard, "SECRET", tmp_path / "client_secret.json")
    dashboard.yt_connect()
    assert ytlogin.status(dt.datetime.now(dt.timezone.utc))["consented_at"] is not None and (tmp_path / "token.json").exists()
