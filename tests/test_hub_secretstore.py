"""The private secrets file: where the hub's mail password and Google client id live. Everything here uses a temporary folder;
the real ~/.config/nightloom/hub.env is never read or written by a test."""
import os
import stat

import pytest

from hub import secretstore as ss

PW = "pa=ss#wo 'rd\" x"  # equals sign, hash, quotes and a space: all legal, all must come back unchanged


@pytest.fixture(autouse=True)
def never_the_real_file(tmp_path, monkeypatch):
    monkeypatch.setenv("HUB_SECRETS_FILE", str(tmp_path / "default" / "hub.env"))


def mode(p):
    return stat.S_IMODE(os.stat(p).st_mode)


def test_save_makes_private_file_and_folder(tmp_path):
    p = ss.save({"HUB_SMTP_USER": "me@gmail.com"}, tmp_path / "cfg" / "hub.env")
    assert mode(p) == 0o600 and mode(p.parent) == 0o700


def test_roundtrip_with_equals_hash_quotes_spaces(tmp_path):
    p = ss.save({"HUB_SMTP_PASSWORD": PW, "HUB_SMTP_USER": "me@gmail.com"}, tmp_path / "hub.env")
    env = {}
    assert ss.load(p, env)["loaded"] == ["HUB_SMTP_USER", "HUB_SMTP_PASSWORD"]  # always in the order of ALLOWED
    assert env["HUB_SMTP_PASSWORD"] == PW


@pytest.mark.parametrize("bad", ["a\nHUB_SMTP_HOST=evil", "a\rb", "a\x00b", "x" * 513])
def test_unsafe_value_refused_and_nothing_written(tmp_path, bad):
    with pytest.raises(ss.SecretError) as ex:
        ss.save({"HUB_SMTP_PASSWORD": bad}, tmp_path / "hub.env")
    assert not (tmp_path / "hub.env").exists() and "evil" not in str(ex.value)


def test_unknown_name_refused(tmp_path):
    with pytest.raises(ss.SecretError):
        ss.save({"PATH": "/tmp"}, tmp_path / "hub.env")


def test_save_merges_and_keeps_other_keys(tmp_path):
    p = tmp_path / "hub.env"
    ss.save({"HUB_SMTP_USER": "me@gmail.com", "HUB_SMTP_PASSWORD": "one"}, p)
    ss.save({"HUB_SMTP_PASSWORD": "two"}, p)
    env = {}
    ss.load(p, env)
    assert env == {"HUB_SMTP_USER": "me@gmail.com", "HUB_SMTP_PASSWORD": "two"}


def test_group_readable_file_is_ignored_with_reason(tmp_path):
    p = ss.save({"HUB_SMTP_PASSWORD": "topsecret"}, tmp_path / "hub.env")
    os.chmod(p, 0o640)
    env = {}
    r = ss.load(p, env)
    assert r["loaded"] == [] and env == {} and "chmod 600" in r["ignored"] and "topsecret" not in r["ignored"]


def test_foreign_owner_is_ignored(tmp_path, monkeypatch):
    p = ss.save({"HUB_SMTP_PASSWORD": "x"}, tmp_path / "hub.env")
    mine = os.getuid()
    monkeypatch.setattr(ss.os, "getuid", lambda: mine + 1)
    env = {}
    assert ss.load(p, env)["loaded"] == [] and env == {}


def test_real_environment_wins_but_an_empty_one_does_not(tmp_path):
    p = ss.save({"HUB_SMTP_HOST": "from-file", "HUB_SMTP_USER": "from-file"}, tmp_path / "hub.env")
    env = {"HUB_SMTP_HOST": "from-env", "HUB_SMTP_USER": ""}
    assert ss.load(p, env)["loaded"] == ["HUB_SMTP_USER"]
    assert env == {"HUB_SMTP_HOST": "from-env", "HUB_SMTP_USER": "from-file"}


def test_missing_file_is_quiet(tmp_path):
    assert ss.load(tmp_path / "none.env", {}) == {"loaded": [], "ignored": ""}


def test_symlink_refused_for_save_and_load(tmp_path):
    real = ss.save({"HUB_SMTP_USER": "a@b.c"}, tmp_path / "real.env")
    link = tmp_path / "link.env"
    link.symlink_to(real)
    with pytest.raises(ss.SecretError):
        ss.save({"HUB_SMTP_USER": "x@y.z"}, link)
    env = {}
    assert ss.load(link, env)["loaded"] == [] and env == {}


def test_path_inside_this_repository_refused():
    with pytest.raises(ss.SecretError):
        ss.save({"HUB_SMTP_USER": "a@b.c"}, ss.REPO / "hub.env")
    assert not (ss.REPO / "hub.env").exists()


def test_path_inside_any_git_work_tree_refused(tmp_path):
    (tmp_path / "proj" / ".git").mkdir(parents=True)
    with pytest.raises(ss.SecretError):
        ss.save({"HUB_SMTP_USER": "a@b.c"}, tmp_path / "proj" / "sub" / "hub.env")


def test_status_has_names_and_flags_only(tmp_path):
    p = ss.save({"HUB_SMTP_PASSWORD": "topsecret", "HUB_GOOGLE_CLIENT_ID": "1-a.apps.googleusercontent.com"}, tmp_path / "hub.env")
    st = ss.status(p, {"HUB_SMTP_USER": "me@gmail.com"})
    assert st["HUB_SMTP_PASSWORD"] and st["HUB_GOOGLE_CLIENT_ID"] and st["HUB_SMTP_USER"] and not st["HUB_SMTP_HOST"]
    assert set(st) == set(ss.ALLOWED) and all(isinstance(v, bool) for v in st.values())


def test_failed_write_leaves_old_file_intact_and_no_temp_files(tmp_path, monkeypatch):
    p = ss.save({"HUB_SMTP_PASSWORD": "old"}, tmp_path / "hub.env")

    def boom(*a, **k):
        raise OSError("power cut")

    monkeypatch.setattr(ss.os, "replace", boom)
    with pytest.raises(OSError):
        ss.save({"HUB_SMTP_PASSWORD": "new"}, p)
    monkeypatch.undo()
    env = {}
    ss.load(p, env)
    assert env["HUB_SMTP_PASSWORD"] == "old"
    assert [f.name for f in tmp_path.iterdir() if f.name.startswith(".hub.env") or f.name == "hub.env"] == ["hub.env"]  # no temp file left


def test_default_path_follows_the_env_var_then_home(monkeypatch, tmp_path):
    assert str(ss.default_path()).endswith("default/hub.env")
    monkeypatch.delenv("HUB_SECRETS_FILE")
    monkeypatch.setenv("HOME", str(tmp_path))
    assert ss.default_path() == tmp_path / ".config" / "nightloom" / "hub.env"
