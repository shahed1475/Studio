"""The per-account AI key store. The keys in these tests are fake strings of the right shape."""
import os
import stat

import pytest

from hub import auth, db, keystore

KEY = "sk-or-v1-" + "a1b2c3d4" * 8
MODEL = "vendor/some-model"


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "PATH", tmp_path / "hub" / "hub.db")
    monkeypatch.setattr(auth, "SECRET_FILE", tmp_path / "hub" / "secret")
    monkeypatch.setattr(keystore, "MASTER_FILE", tmp_path / "hub" / "keystore.key")
    monkeypatch.delenv("HUB_KEYSTORE_KEY", raising=False)


def account(email="a@example.com"):
    with db.tx() as con:
        return auth._account_for_email(con, email, 1000.0)


def test_roundtrip():
    a = account()
    keystore.set_key(a, KEY, MODEL, now=5.0)
    assert keystore.get(a) == {"key": KEY, "model": MODEL}


def test_database_file_holds_no_plaintext():
    a = account()
    keystore.set_key(a, KEY, MODEL)
    raw = b"".join(p.read_bytes() for p in db.PATH.parent.glob("hub.db*"))
    assert KEY.encode() not in raw and KEY[10:30].encode() not in raw


def test_ciphertext_copied_to_another_account_does_not_decrypt():
    a, b = account("a@example.com"), account("b@example.com")
    keystore.set_key(a, KEY, MODEL)
    keystore.set_key(b, "sk-or-v1-" + "f" * 64, MODEL)
    with db.tx() as con:
        token = con.execute("select token from account_keys where account_id=?", (a,)).fetchone()["token"]
        con.execute("update account_keys set token=? where account_id=?", (token, b))
    assert keystore.get(b) is None and keystore.get(a)["key"] == KEY


def test_wrong_master_key_returns_none_not_a_crash(tmp_path):
    a = account()
    keystore.set_key(a, KEY, MODEL)
    keystore.MASTER_FILE.unlink()  # a new master key is made on next use: the old keys cannot be read
    assert keystore.get(a) is None
    assert keystore.status(a)["set"] is True  # the row exists; the creator is asked to add the key again by the caller


@pytest.mark.parametrize("raw", ["  " + KEY + "\n", '"' + KEY + '"', "'" + KEY + "'"])
def test_whitespace_and_quotes_are_trimmed(raw):
    a = account()
    keystore.set_key(a, raw, MODEL)
    assert keystore.get(a)["key"] == KEY


@pytest.mark.parametrize("bad", ["", "hello", "sk-or-short","sk-ant-" + "x" * 40, KEY + " extra", "sk-or-v1-" + "a" * 300, "sk-or-v1-abc\ndef" + "x" * 30])
def test_bad_key_shapes_are_refused_without_echoing_them(bad):
    with pytest.raises(ValueError) as ex:
        keystore.set_key(account(), bad, MODEL)
    assert not bad.strip() or bad.strip() not in str(ex.value)  # the message names the rule, never the text that was pasted


@pytest.mark.parametrize("bad", ["", "nomodelslash", "a/b c", "x/" + "y" * 200, "../etc/passwd/x"])
def test_model_shape_is_checked(bad):
    with pytest.raises(ValueError):
        keystore.set_key(account(), KEY, bad)


def test_status_never_contains_the_key():
    a = account()
    assert keystore.status(a) == {"set": False, "model": "", "added_at": None}
    keystore.set_key(a, KEY, MODEL, now=7.0)
    s = keystore.status(a)
    assert s == {"set": True, "model": MODEL, "added_at": 7.0} and KEY not in str(s)


def test_audit_rows_never_contain_the_key():
    a = account()
    keystore.set_key(a, KEY, MODEL)
    keystore.remove(a)
    with db.read() as con:
        rows = [tuple(r) for r in con.execute("select * from audit")]
    assert any("key_set" in str(r) for r in rows) and any("key_removed" in str(r) for r in rows) and KEY not in str(rows)


def test_remove_and_account_delete_cascade():
    a, b = account("a@example.com"), account("b@example.com")
    keystore.set_key(a, KEY, MODEL)
    keystore.set_key(b, KEY, MODEL)
    assert keystore.remove(a) is True and keystore.get(a) is None and keystore.remove(a) is False
    with db.tx() as con:
        con.execute("delete from accounts where id=?", (b,))
        assert con.execute("select count(*) from account_keys").fetchone()[0] == 0


def test_setting_again_replaces_the_key():
    a = account()
    keystore.set_key(a, KEY, MODEL)
    keystore.set_key(a, "sk-or-v1-" + "9" * 64, "other/model")
    assert keystore.get(a) == {"key": "sk-or-v1-" + "9" * 64, "model": "other/model"}


def test_master_key_file_is_private_and_made_once():
    a = account()
    keystore.set_key(a, KEY, MODEL)
    assert stat.S_IMODE(os.stat(keystore.MASTER_FILE).st_mode) == 0o600
    first = keystore.MASTER_FILE.read_bytes()
    keystore.set_key(a, KEY, MODEL)
    assert keystore.MASTER_FILE.read_bytes() == first


def test_master_key_can_come_from_the_environment(monkeypatch):
    from cryptography.fernet import Fernet

    monkeypatch.setenv("HUB_KEYSTORE_KEY", Fernet.generate_key().decode())
    a = account()
    keystore.set_key(a, KEY, MODEL)
    assert keystore.get(a)["key"] == KEY and not keystore.MASTER_FILE.exists()
