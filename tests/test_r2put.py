import datetime as dt
import gzip
import os

import pytest

import r2put


def test_signing_key_matches_the_published_aws_example():
    k = r2put.signing_key("wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY", "20120215", "us-east-1", "iam")
    assert k.hex() == "f4780e2d9f65fa895f9c67b32ce1baf0b0d8a43505a000a1a9e090d414db404d"


def test_a_signed_put_names_the_bucket_and_never_carries_the_secret():
    now = dt.datetime(2026, 11, 11, 3, 40, tzinfo=dt.timezone.utc)
    url, h = r2put.sign_put("acct", "bk", "backup-20261111.tar.gz", b"x", "AKID", "SECRETVALUE", now)
    assert url == "https://acct.r2.cloudflarestorage.com/bk/backup-20261111.tar.gz"
    assert "SECRETVALUE" not in str(h) and h["Authorization"].startswith("AWS4-HMAC-SHA256 Credential=AKID/20261111/auto/s3/aws4_request")
    assert r2put.sign_put("acct", "bk", "backup-20261111.tar.gz", b"x", "AKID", "SECRETVALUE", now)[1] == h  # deterministic


def make(tmp_path, name="backup-20261111.tar.gz", payload=b"records"):
    (tmp_path / "backups").mkdir(exist_ok=True)
    p = tmp_path / "backups" / name
    with gzip.open(p, "wb") as f:
        f.write(payload)
    return p


def env(tmp_path):
    (tmp_path / ".env").write_text("R2_ACCOUNT_ID=a\nR2_BUCKET=b\nR2_ACCESS_KEY_ID=k\nR2_SECRET_ACCESS_KEY=s\nOTHER=1\n")


class Resp:
    def __init__(self, code):
        self.status_code = code


def at(p, seconds):
    return dt.datetime.fromtimestamp(p.stat().st_mtime + seconds, dt.timezone.utc)


def test_only_backup_named_valid_fresh_files_are_sent_and_a_marker_is_written(tmp_path):
    p = make(tmp_path)
    (tmp_path / "backups" / "notes.txt").write_text("no")
    env(tmp_path)
    calls = []
    assert r2put.run(tmp_path, now=at(p, 3600), put=lambda url, **kw: calls.append(url) or Resp(200)) == [p.name]
    assert len(calls) == 1 and calls[0].endswith("/b/" + p.name)
    assert (tmp_path / "backups" / "last_r2.txt").read_text().endswith(p.name + "\n")


def test_a_stale_corrupt_or_refused_backup_is_not_reported_as_sent(tmp_path):
    p = make(tmp_path)
    env(tmp_path)
    mt = p.stat().st_mtime
    with pytest.raises(SystemExit, match="hours old"):
        r2put.run(tmp_path, now=at(p, 40 * 3600), put=lambda *a, **k: Resp(200))
    with pytest.raises(SystemExit, match="HTTP 403"):
        r2put.run(tmp_path, now=at(p, 60), put=lambda *a, **k: Resp(403))
    assert not (tmp_path / "backups" / "last_r2.txt").exists()
    p.write_bytes(b"not gzip")
    os.utime(p, (mt, mt))
    with pytest.raises(SystemExit, match="valid gzip"):
        r2put.run(tmp_path, now=at(p, 60), put=lambda *a, **k: Resp(200))


def test_a_symlink_in_backups_is_never_followed_and_dry_run_sends_nothing(tmp_path):
    make(tmp_path, "real.dat")
    (tmp_path / "backups" / "backup-20261112.tar.gz").symlink_to(tmp_path / "backups" / "real.dat")
    with pytest.raises(SystemExit, match="no backup archive"):
        r2put.run(tmp_path)
    p = make(tmp_path)
    assert r2put.run(tmp_path, dry=True, now=at(p, 60), put=None) == [p.name]


def test_missing_settings_name_the_keys_but_never_a_value(tmp_path):
    (tmp_path / ".env").write_text("R2_BUCKET=b\nR2_SECRET_ACCESS_KEY=topsecret\n")
    with pytest.raises(SystemExit) as e:
        r2put.settings(tmp_path / ".env")
    assert "R2_ACCOUNT_ID" in str(e.value) and "topsecret" not in str(e.value)
