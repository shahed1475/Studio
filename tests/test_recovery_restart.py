"""Sub-plan 7 of the owner's 22 Nov 2026 master mission: recovery after a killed worker, a lost network and restarts (23 Nov 2026).

Two live drills came first (reports/RECOVERY_TESTS_2026-11-23.md). Drill 4 (tools/recovery_drill.py container-start / container-after) killed the
worker CONTAINER in the middle of a render: two scenes kept, six rendered on resume, nothing trusted half-written. The offline drill ran the hourly
jobs in a `--network none` container on a reflink copy of the studio: no record changed and no model was marked bad, but the YouTube login check told
the owner to "Reconnect YouTube" when only the network was down. Reading the scheduler and the settings code found three files written in place.
These tests pin each finding."""
import datetime as dt
import json
import os
import socket
from datetime import timedelta

import pytest
import requests

import agentlog
import autopilot
import config
import llm
import records
import risk
import safety
import worker
import ytlogin

NOW = dt.datetime(2026, 11, 23, 7, 0, tzinfo=dt.timezone.utc)


class Cut(BaseException):
    """The process dies here. A BaseException, so no `except Exception` in the code under test can swallow it."""


def _die(*a, **k):
    raise Cut()


# --- a cut in the middle of a save (worker killed, container restarted, power cut) ---------------------------------------------------------------


def test_a_cut_while_the_worker_saves_its_job_times_never_makes_every_job_due(tmp_path, monkeypatch):
    """worker_state.json was written in place: a cut mid-write left half a file, load_state() read {} and every job (the weekly learner, the
    trend scan's API units, the title test) ran at once on restart. It is now replaced only by a rename, and a file the disk lost falls back to
    the previous copy."""
    monkeypatch.setattr(worker, "STATE", tmp_path / "worker_state.json")
    old = {j["name"]: NOW.strftime(worker.TS) for j in worker.JOBS}
    worker.save_state(old)
    with monkeypatch.context() as m:
        m.setattr(os, "replace", _die)
        with pytest.raises(Cut):
            worker.save_state({**old, "autopilot": "2026-11-23T07:30:00Z"})
    assert worker.load_state() == old
    assert worker.due(NOW + timedelta(minutes=1), worker.load_state()) == []
    worker.save_state({**old, "autopilot": "2026-11-23T07:30:00Z"})
    (tmp_path / "worker_state.json").write_text('{"autop')  # the file system lost the last write
    assert worker.load_state() == old


@pytest.mark.parametrize("mod, key, first, second", [(autopilot, "pause_scheduling", True, False), (llm, "daily_budget_usd", 2.5, 4.0)])
def test_a_cut_while_a_settings_file_is_saved_leaves_the_owners_last_settings_whole(tmp_path, monkeypatch, mod, key, first, second):
    """autopilot.json and llm.json were written in place: a cut mid-write left a file json cannot read, and every Autopilot tick and settings page
    then crashed until someone repaired it by hand. A save now writes a temporary file and renames it: the owner's last settings or the new ones,
    never half. The layout the owner reads (two-space indent, the settings in their usual order) is kept."""
    monkeypatch.setattr(mod, "CONFIG_FILE", tmp_path / f"{mod.__name__}.json")
    cfg = {**mod.load_config(), key: first}
    mod.save_config(cfg)
    with monkeypatch.context() as m:
        m.setattr(os, "replace", _die)
        with pytest.raises(Cut):
            mod.save_config({**cfg, key: second})
    assert mod.load_config()[key] == first
    assert mod.CONFIG_FILE.read_text() == json.dumps({k: cfg[k] for k in mod.DEFAULTS}, indent=2)
    mod.CONFIG_FILE.chmod(0o600)  # how the owner's files are kept on the PC
    mod.save_config({**cfg, key: second})
    assert mod.load_config()[key] == second and mod.CONFIG_FILE.stat().st_mode & 0o777 == 0o600


class _Creds:
    def __init__(self, text):
        self.text = text

    def to_json(self):
        return self.text


def test_a_cut_while_the_login_is_refreshed_never_leaves_half_a_login(tmp_path, monkeypatch):
    """Every refresh rewrote token.json in place (hourly, and in any process whose access token had run out). A cut in that moment left a login the
    Google library cannot read: no upload, no check, until the owner reconnects in a browser. Now the old login stays whole, and a saved login is
    never readable by anyone but the owner, not even for a moment."""
    import upload

    tok = tmp_path / "token.json"
    monkeypatch.setattr(upload, "TOKEN", tok)
    upload.save_token(_Creds('{"refresh_token": "old"}'))
    assert tok.stat().st_mode & 0o777 == 0o600
    with monkeypatch.context() as m:
        m.setattr(os, "replace", _die)
        with pytest.raises(Cut):
            upload.save_token(_Creds('{"refresh_token": "new"}'))
    assert json.loads(tok.read_text()) == {"refresh_token": "old"}
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in tmp_path.glob("token.json*"))  # the leftover temporary copy is the owner's only too
    upload.save_token(_Creds('{"refresh_token": "new"}'))
    assert json.loads(tok.read_text()) == {"refresh_token": "new"}


def test_no_module_writes_the_login_file_in_place():
    from pathlib import Path

    for name in ("upload.py", "ytlogin.py", "dashboard.py", "ytweb.py"):
        text = (Path(config.__file__).parent / name).read_text()
        assert "TOKEN.write_text(" not in text, f"{name} writes token.json in place: use upload.save_token"


# --- a lost network is not a lost login ------------------------------------------------------------------------------------------------------------


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "OUT", tmp_path / "output")
    monkeypatch.setattr(ytlogin, "STATE", tmp_path / "data" / "youtube_login.json")
    monkeypatch.setattr(agentlog, "FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(agentlog.subprocess, "run", lambda *a, **k: None)
    (tmp_path / "output").mkdir()
    return tmp_path


def _offline_errors():
    out = [requests.ConnectionError("HTTPSConnectionPool(host='oauth2.googleapis.com', port=443): Max retries exceeded"),
           socket.gaierror(-3, "Temporary failure in name resolution"), TimeoutError("timed out"), ConnectionRefusedError(111, "Connection refused")]
    try:
        from google.auth.exceptions import TransportError

        out.append(TransportError("HTTPSConnectionPool(host='oauth2.googleapis.com', port=443): Max retries exceeded with url: /token "
                                  "(Caused by NameResolutionError(\"HTTPSConnection(host='oauth2.googleapis.com', port=443): Failed to resolve\"))"))
    except ImportError:
        pass
    return out


@pytest.mark.parametrize("err", _offline_errors(), ids=lambda e: type(e).__name__)
def test_a_lost_network_is_never_reported_as_a_lost_youtube_login(world, err):
    """The offline drill (23 Nov 2026): the hourly health check met 'Temporary failure in name resolution' and posted 'The YouTube login check failed.
    Reconnect YouTube: ...', and the Risks row went to act. The login had not been tested at all. Now the check says the network is down, asks the
    owner for nothing, keeps the last working check, and the Risks row follows the login's age as before."""
    ytlogin.stamp(NOW - timedelta(days=1), mode="testing")
    assert ytlogin.check(NOW - timedelta(hours=1), refresh=lambda: None)["ok"] is True

    def down():
        raise err
    r = ytlogin.check(NOW, refresh=down)
    assert r["ok"] is False and r.get("offline") is True and r["error"].startswith("offline")
    assert not [e for e in agentlog.recent() if "Reconnect" in e.get("detail", "") or "login" in e.get("title", "").lower()]
    row = risk.login(NOW)
    assert row["level"] == "ok", row
    assert "could not reach Google" in row["evidence"] and (NOW - timedelta(hours=1)).strftime(ytlogin.TS) in row["evidence"]


def test_a_real_expiry_is_still_reported_at_once_after_an_outage(world):
    ytlogin.stamp(NOW - timedelta(days=1))
    ytlogin.check(NOW - timedelta(hours=2), refresh=lambda: (_ for _ in ()).throw(socket.gaierror(-3, "Temporary failure in name resolution")))

    def expired():
        raise RuntimeError("invalid_grant: Token has been expired or revoked.")
    assert ytlogin.check(NOW, refresh=expired)["error"] == "expired"
    assert [e for e in agentlog.recent() if e["title"] == "The YouTube login expired"]
    assert risk.login(NOW)["level"] == "act"


def test_a_long_outage_turns_the_login_row_to_watch_because_nobody_can_vouch_for_it(world):
    ytlogin.stamp(NOW - timedelta(days=1), mode="production")
    ytlogin.check(NOW - timedelta(hours=30), refresh=lambda: None)
    ytlogin.check(NOW, refresh=lambda: (_ for _ in ()).throw(requests.ConnectionError("no route")))
    row = risk.login(NOW)
    assert row["level"] == "watch" and "could not reach Google" in row["evidence"]


def test_an_outage_tells_the_owner_once_a_day_that_youtube_could_not_be_reached(world, monkeypatch):
    """The hourly health check posted 'Could not reach YouTube to check published videos' as an alert every hour of an outage (within three days of a
    publish, when videos are due for their check). Once a day is enough: the next hours add nothing the owner can act on."""
    out = world / "output"
    f = out / "v"
    f.mkdir()
    records.save(f, {"video_id": "v1", "publish_at": (NOW - timedelta(hours=2)).strftime(safety.TS), "approved": True})
    monkeypatch.setattr(safety, "_service", lambda: (_ for _ in ()).throw(requests.ConnectionError("Temporary failure in name resolution")))
    monkeypatch.setattr(safety, "_pause_for_lost", lambda now: None)
    import reconcile

    monkeypatch.setattr(reconcile, "run", lambda now, yt=None: None)  # not under test here; in the full suite it could reuse another test's service
    for h in range(5):
        r = safety.check(NOW + timedelta(hours=h))
        assert r["checked"] == 0 and r["error"]
    seen = [e for e in agentlog.recent(200) if e["title"] == "Could not reach YouTube to check published videos"]
    assert len(seen) == 1
    safety.check(NOW + timedelta(hours=25))
    assert len([e for e in agentlog.recent(200) if e["title"] == "Could not reach YouTube to check published videos"]) == 2
