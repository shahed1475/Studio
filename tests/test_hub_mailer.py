"""The sign-in mail sender. The fake stands in for the network only; what is asserted is what our code asks of smtplib
(a verifying TLS context, TLS before the password, the right class for port 465) and what it puts in the message."""
import ssl

import pytest

from hub import mailer

PASSWORD = "s3cret-app-password"


class FakeSMTP:
    made = []

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port, self.timeout, self.context = host, port, timeout, context
        self.calls, self.tls_context, self.creds, self.sent = [], None, None, None
        FakeSMTP.made.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, *, context=None):
        self.calls.append("starttls")
        self.tls_context = context

    def login(self, user, password):
        self.calls.append("login")
        self.creds = (user, password)

    def send_message(self, msg):
        self.calls.append("send")
        self.sent = msg


class FakeSMTPSSL(FakeSMTP):
    made = []

    def __init__(self, host, port, timeout=None, context=None):
        super().__init__(host, port, timeout, context)
        FakeSMTPSSL.made.append(self)


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    FakeSMTP.made, FakeSMTPSSL.made = [], []
    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", FakeSMTPSSL)
    for name in ("HUB_SMTP_HOST", "HUB_SMTP_PORT", "HUB_SMTP_USER", "HUB_SMTP_PASSWORD", "HUB_MAIL_FROM"):
        monkeypatch.delenv(name, raising=False)


def gmail():
    return mailer.SMTPMailer("smtp.gmail.com", 587, "me@gmail.com", PASSWORD, "me@gmail.com")


def test_starttls_gets_a_verifying_context():
    gmail().send("ann@example.com", "Your sign-in code", "12345678")
    ctx = FakeSMTP.made[0].tls_context
    assert ctx is not None and ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname is True


def test_starttls_happens_before_login():
    gmail().send("ann@example.com", "s", "b")
    assert FakeSMTP.made[0].calls == ["starttls", "login", "send"]
    assert FakeSMTP.made[0].creds == ("me@gmail.com", PASSWORD)


def test_port_465_uses_implicit_ssl_with_verifying_context():
    mailer.SMTPMailer("smtp.gmail.com", 465, "me@gmail.com", PASSWORD, "me@gmail.com").send("ann@example.com", "s", "b")
    assert FakeSMTP.made == FakeSMTPSSL.made and len(FakeSMTPSSL.made) == 1  # only the SSL class was built
    inst = FakeSMTPSSL.made[0]
    assert inst.context.verify_mode == ssl.CERT_REQUIRED and inst.context.check_hostname is True
    assert inst.calls == ["login", "send"]


def test_message_has_to_from_subject_and_never_the_password():
    gmail().send("ann@example.com", "Your sign-in code", "code 12345678")
    msg = FakeSMTP.made[0].sent
    assert (msg["To"], msg["From"], msg["Subject"]) == ("ann@example.com", "me@gmail.com", "Your sign-in code")
    assert PASSWORD not in msg.as_string()


def test_from_env_without_host_is_the_outbox():
    assert isinstance(mailer.from_env(), mailer.OutboxMailer)


def test_from_env_with_host_is_smtp_with_port_587_and_sender_defaults(monkeypatch):
    monkeypatch.setenv("HUB_SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("HUB_SMTP_USER", "me@gmail.com")
    monkeypatch.setenv("HUB_SMTP_PASSWORD", PASSWORD)
    m = mailer.from_env()
    assert isinstance(m, mailer.SMTPMailer) and (m.host, m.port, m.sender) == ("smtp.gmail.com", 587, "me@gmail.com")


@pytest.mark.parametrize("bad", ["abc", "0", "70000", ""])
def test_bad_port_is_a_clear_error(monkeypatch, bad):
    monkeypatch.setenv("HUB_SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("HUB_SMTP_PORT", bad)
    if bad == "":
        assert mailer.from_env().port == 587  # an empty setting means "not set"
        return
    with pytest.raises(ValueError, match="HUB_SMTP_PORT"):
        mailer.from_env()


def _bridge(tmp_path, monkeypatch, data, mode=0o600):
    import json
    f = tmp_path / "mail.json"
    f.write_text(json.dumps(data))
    f.chmod(mode)
    monkeypatch.setenv("HUB_MAIL_BRIDGE", str(f))
    monkeypatch.delenv("HUB_SMTP_HOST", raising=False)
    return f


def test_the_dashboards_gmail_becomes_the_mailer_with_a_fixed_gmail_host(tmp_path, monkeypatch):
    from hub import mailer
    _bridge(tmp_path, monkeypatch, {"address": "Me@Gmail.com", "app_password": "abcdefghijklmnop"})
    m = mailer.from_env()
    assert isinstance(m, mailer.SMTPMailer) and (m.host, m.port, m.user, m.sender) == ("smtp.gmail.com", 587, "me@gmail.com", "me@gmail.com")


def test_a_loose_or_malformed_bridge_file_is_ignored_and_removing_it_falls_back(tmp_path, monkeypatch):
    from hub import mailer
    f = _bridge(tmp_path, monkeypatch, {"address": "me@gmail.com", "app_password": "abcdefghijklmnop"}, mode=0o644)
    assert isinstance(mailer.from_env(), mailer.OutboxMailer)  # readable by others: not trusted
    f.chmod(0o600)
    assert isinstance(mailer.from_env(), mailer.SMTPMailer)
    f.unlink()
    assert isinstance(mailer.from_env(), mailer.OutboxMailer)  # removed in the dashboard: back to the local outbox
    for bad in ({"address": "me@evil.com", "app_password": "abcdefghijklmnop"}, {"address": "me@gmail.com", "app_password": "short"}, ["x"]):
        _bridge(tmp_path, monkeypatch, bad)
        assert isinstance(mailer.from_env(), mailer.OutboxMailer)
