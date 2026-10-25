import pytest
import datetime as dt
import json
import tarfile

import backup
import config

NOW = dt.datetime(2026, 10, 25, 3, 30, tzinfo=dt.timezone.utc)


def build(root):
    (root / "output" / "v1").mkdir(parents=True)
    (root / "output" / "v1" / "meta.json").write_text(json.dumps({"title": "t", "video_id": "abc"}))
    (root / "output" / "v1" / "video.mp4").write_bytes(b"x" * 1000)
    (root / "data").mkdir()
    (root / "data" / "titletest.json").write_text('{"mode": "apply"}')
    (root / "autopilot.json").write_text('{"enabled": true}')
    (root / "settings.json").write_text('{"openrouter_key": "sk-secret"}')
    (root / "token.json").write_text('{"refresh_token": "secret"}')
    (root / ".env").write_text("KEY=secret")
    (root / "client_secret.json").write_text("{}")
    for name in ("auth.json", "auth_secret", "sessions.json", "tenants.json", "oauth_pending.json", "invites.json", "something_new.json"):
        (root / "data" / name).write_text("secret")  # the dashboard login, its signing secret, live sessions: never in a backup
    (root / "data" / "agent").mkdir()
    (root / "data" / "agent" / "events.jsonl").write_text("{}")
    (root / "data" / "agent" / "cookie_jar.json").write_text("secret")
    (root / "data" / "llm_usage.json").write_text("{}")


def test_backup_holds_the_records_and_settings_but_no_secrets_and_no_videos(tmp_path):
    build(tmp_path)
    out = backup.run(NOW, root=tmp_path, dest=tmp_path / "backups")
    with tarfile.open(out["path"]) as t:
        names = t.getnames()
    assert "output/v1/meta.json" in names and "data/titletest.json" in names and "autopilot.json" in names
    assert "data/agent/events.jsonl" in names and "data/llm_usage.json" in names
    assert not any(w in n for n in names for w in ("auth", "session", "tenant", "oauth", "invite", "something_new", "cookie"))  # an allowlist: new files are left out until named
    assert not any(n.endswith("video.mp4") or "token" in n or "settings.json" in n or ".env" in n or "client_secret" in n for n in names)


def test_only_the_newest_seven_backups_are_kept(tmp_path):
    build(tmp_path)
    for d in range(10):
        backup.run(NOW + dt.timedelta(days=d), root=tmp_path, dest=tmp_path / "backups")
    kept = sorted(p.name for p in (tmp_path / "backups").glob("backup-*.tar.gz"))
    assert len(kept) == 7 and kept[-1] == "backup-20261103.tar.gz"


def test_the_age_of_the_newest_backup_is_reported(tmp_path):
    build(tmp_path)
    assert backup.newest_age_hours(NOW, dest=tmp_path / "backups") is None
    backup.run(NOW, root=tmp_path, dest=tmp_path / "backups")
    assert backup.newest_age_hours(NOW + dt.timedelta(hours=5), dest=tmp_path / "backups") == 5.0


def test_the_risk_card_has_a_backup_row_that_turns_to_watch_when_none_is_recent(tmp_path):
    import risk
    assert risk.backups(NOW, tmp_path / "b")["level"] == "watch"
    build(tmp_path)
    backup.run(NOW, root=tmp_path, dest=tmp_path / "b")
    (tmp_path / "b" / backup.PUSH_MARKER).write_text(NOW.strftime("%Y-%m-%dT%H:%M:%SZ") + " backup-20261030.tar.gz\n")
    assert risk.backups(NOW + dt.timedelta(hours=5), tmp_path / "b")["level"] == "ok"
    assert risk.backups(NOW + dt.timedelta(hours=60), tmp_path / "b")["level"] == "watch"


def test_a_backup_never_pushed_off_the_server_is_a_watch_and_says_so(tmp_path):
    import risk
    build(tmp_path)
    backup.run(NOW, root=tmp_path, dest=tmp_path / "b")
    row = risk.backups(NOW + dt.timedelta(hours=5), tmp_path / "b")
    assert row["level"] == "watch" and "off the server yet" in row["evidence"]


def test_the_off_server_copy_turns_to_watch_after_30_hours_and_to_act_after_72(tmp_path):
    import risk
    build(tmp_path)
    b = tmp_path / "b"
    backup.run(NOW + dt.timedelta(days=5), root=tmp_path, dest=b)  # the local copy stays fresh; only the push ages
    (b / backup.PUSH_MARKER).write_text(NOW.strftime("%Y-%m-%dT%H:%M:%SZ") + " backup-20261030.tar.gz\n")
    fresh = NOW + dt.timedelta(hours=20)
    assert backup.pushed_age_hours(fresh, b) == 20.0
    (b / backup.PUSH_MARKER).write_text((NOW - dt.timedelta(hours=40)).strftime("%Y-%m-%dT%H:%M:%SZ") + " x\n")
    assert risk.backups(NOW, b)["level"] != "ok" and "40 hours old" in risk.backups(NOW, b)["evidence"]
    (b / backup.PUSH_MARKER).write_text((NOW - dt.timedelta(hours=80)).strftime("%Y-%m-%dT%H:%M:%SZ") + " x\n")
    assert risk.backups(NOW, b)["level"] == "act"


@pytest.mark.parametrize("text", ["", "garbage", "2026-13-45T00:00:00Z x", "2099-01-01T00:00:00Z x"])
def test_an_unreadable_or_future_push_marker_counts_as_never_pushed(tmp_path, text):
    (tmp_path / backup.PUSH_MARKER).write_text(text)
    assert backup.pushed_age_hours(NOW, tmp_path) is None


def test_the_archive_and_its_folder_are_private(tmp_path):
    import stat
    build(tmp_path)
    out = backup.run(NOW, root=tmp_path, dest=tmp_path / "backups")
    assert stat.S_IMODE((tmp_path / "backups").stat().st_mode) == 0o700
    assert stat.S_IMODE(__import__("pathlib").Path(out["path"]).stat().st_mode) == 0o600
