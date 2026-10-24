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


def test_backup_holds_the_records_and_settings_but_no_secrets_and_no_videos(tmp_path):
    build(tmp_path)
    out = backup.run(NOW, root=tmp_path, dest=tmp_path / "backups")
    with tarfile.open(out["path"]) as t:
        names = t.getnames()
    assert "output/v1/meta.json" in names and "data/titletest.json" in names and "autopilot.json" in names
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
    assert risk.backups(NOW + dt.timedelta(hours=5), tmp_path / "b")["level"] == "ok"
    assert risk.backups(NOW + dt.timedelta(hours=60), tmp_path / "b")["level"] == "watch"
