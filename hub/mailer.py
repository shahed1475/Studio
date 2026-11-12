"""Sending the sign-in code. Three small senders with one method, send(to, subject, body):
SMTPMailer (real mail, from HUB_SMTP_* settings in the server's .env), OutboxMailer (writes the message to data/hub/outbox/ for local testing; never sends anything).
`from_env()` picks SMTP only when HUB_SMTP_HOST is set. The code is the only secret in a message and the message holds no link, so there is nothing to build from a Host header."""
import json
import os
import re
import secrets
import smtplib
import ssl
import stat
import time
from email.message import EmailMessage
from pathlib import Path

import config


class OutboxMailer:
    def __init__(self, folder=None):
        self.folder = folder or config.ROOT / "data" / "hub" / "outbox"

    def send(self, to: str, subject: str, body: str) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        f = self.folder / f"{int(time.time())}-{secrets.token_hex(3)}.json"
        f.write_text(json.dumps({"to": to, "subject": subject, "body": body}, indent=1))
        os.chmod(f, 0o600)


class SMTPMailer:
    def __init__(self, host: str, port: int, user: str, password: str, sender: str):
        self.host, self.port, self.user, self.password, self.sender = host, port, user, password, sender

    def send(self, to: str, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = self.sender, to, subject
        msg.set_content(body)
        # The default context of smtplib's starttls() does not check the server's certificate (verify_mode CERT_NONE),
        # which would hand the mail password to anyone who can sit on the connection. Always pass a verifying one.
        ctx = ssl.create_default_context()
        implicit = self.port == 465
        conn = smtplib.SMTP_SSL(self.host, self.port, timeout=20, context=ctx) if implicit else smtplib.SMTP(self.host, self.port, timeout=20)
        with conn as s:
            if not implicit:
                s.starttls(context=ctx)
            if self.user:
                s.login(self.user, self.password)
            s.send_message(msg)


def _port(raw: str) -> int:
    raw = (raw or "").strip()
    if not raw:
        return 587
    if not raw.isdigit() or not 1 <= int(raw) <= 65535:
        raise ValueError("HUB_SMTP_PORT is not a port number (1 to 65535)")
    return int(raw)


GMAIL = re.compile(r"^[A-Za-z0-9._%+-]{1,64}@gmail\.com$", re.I)
APP_PASSWORD = re.compile(r"^[a-z]{16}$")


def bridge_path() -> Path:
    return Path(os.getenv("HUB_MAIL_BRIDGE", "/hubmail/mail.json"))


def bridge():
    """The Gmail the owner saved in the main dashboard (a private file the studio writes and this container mounts read-only), as (address, app password), or None.
    Read at every send, so saving or removing it in the dashboard takes effect at once. A file anyone else can read, or one that is not a Gmail address with an app password, is ignored."""
    p = bridge_path()
    try:
        if stat.S_IMODE(p.stat().st_mode) & 0o077:
            return None
        d = json.loads(p.read_text())
        addr, pw = str(d.get("address", "")).strip().lower(), str(d.get("app_password", ""))
    except (OSError, ValueError, AttributeError):
        return None
    return (addr, pw) if GMAIL.match(addr) and APP_PASSWORD.match(pw) else None


def from_env():
    saved = bridge()
    if saved:  # the dashboard's Gmail: the host is fixed, so the password can only go to Gmail
        return SMTPMailer("smtp.gmail.com", 587, saved[0], saved[1], saved[0])
    host = os.getenv("HUB_SMTP_HOST", "").strip()
    if not host:
        return OutboxMailer()
    user = os.getenv("HUB_SMTP_USER", "")
    sender = os.getenv("HUB_MAIL_FROM", "").strip() or user
    return SMTPMailer(host, _port(os.getenv("HUB_SMTP_PORT", "")), user, os.getenv("HUB_SMTP_PASSWORD", ""), sender)
