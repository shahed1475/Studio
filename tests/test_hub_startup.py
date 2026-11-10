"""What the hub says when it starts: plain words about what is switched on, read from the private secrets file. Never a value."""
import os

import pytest

from hub import secretstore as ss
from hub import server

SECRETS = {"HUB_SMTP_HOST": "smtp.gmail.com", "HUB_SMTP_PORT": "587", "HUB_SMTP_USER": "owner.private@gmail.com",
           "HUB_SMTP_PASSWORD": "abcdefghijklmnop", "HUB_MAIL_FROM": "owner.private@gmail.com",
           "HUB_GOOGLE_CLIENT_ID": "123456789012-abcdef.apps.googleusercontent.com"}


def no_secret_in(lines):
    text = "\n".join(lines)
    for value in SECRETS.values():
        if value not in ("smtp.gmail.com", "587"):  # host and port are settings, not secrets
            assert value not in text


def test_report_says_what_is_on_and_never_prints_a_value(tmp_path):
    p = ss.save(SECRETS, tmp_path / "hub.env")
    lines = server.startup_report({}, p)
    text = "\n".join(lines)
    assert "Mail: SMTP" in text and "Google sign-in: on" in text
    no_secret_in(lines)


def test_report_with_nothing_set_says_outbox_and_google_off(tmp_path):
    lines = server.startup_report({}, tmp_path / "none.env")
    text = "\n".join(lines)
    assert "local outbox" in text and "Google sign-in: off" in text


def test_report_says_why_a_loose_file_was_ignored(tmp_path):
    p = ss.save(SECRETS, tmp_path / "hub.env")
    os.chmod(p, 0o640)
    env = {}
    lines = server.startup_report(env, p)
    assert any("ignored" in l and "chmod 600" in l for l in lines) and env == {}
    no_secret_in(lines)


def test_report_names_the_missing_piece_of_mail(tmp_path):
    p = ss.save({k: v for k, v in SECRETS.items() if k != "HUB_SMTP_PASSWORD"}, tmp_path / "hub.env")
    text = "\n".join(server.startup_report({}, p))
    assert "incomplete" in text and "HUB_SMTP_PASSWORD" in text


def test_main_reads_the_file_before_it_binds_and_prints_no_value(tmp_path, monkeypatch, capsys):
    p = ss.save(SECRETS, tmp_path / "hub.env")
    monkeypatch.setenv("HUB_SECRETS_FILE", str(p))
    for name in ss.ALLOWED:
        monkeypatch.setenv(name, "")  # recorded by monkeypatch, so the load below is undone at teardown
    seen = {}

    class Fake:
        server_address = ("127.0.0.1", 1)

        def serve_forever(self):
            pass

    def fake_make_server(host, port):
        seen["client_id_at_bind"] = os.environ.get("HUB_GOOGLE_CLIENT_ID")
        return Fake()

    monkeypatch.setattr(server, "make_server", fake_make_server)
    server.main()
    out = capsys.readouterr().out
    assert seen["client_id_at_bind"] == SECRETS["HUB_GOOGLE_CLIENT_ID"]
    no_secret_in(out.splitlines())


def test_report_says_whether_sign_up_is_open_or_closed_and_the_mail_cap(tmp_path):
    none = tmp_path / "none.env"
    text = "\n".join(server.startup_report({}, none))
    assert "Sign-up: OPEN to anyone" in text and "at most 100" in text
    closed = "\n".join(server.startup_report({"HUB_ALLOWED_EMAILS": "friend@example.com, @team.example", "HUB_MAIL_DAILY_CAP": "30"}, none))
    assert "Sign-up: closed to 2 listed" in closed and "at most 30" in closed
    assert "friend@example.com" not in closed and "team.example" not in closed  # the list itself is not printed
