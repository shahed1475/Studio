"""Sending the sign-in code. Three small senders with one method, send(to, subject, body):
SMTPMailer (real mail, from HUB_SMTP_* settings in the server's .env), OutboxMailer (writes the message to data/hub/outbox/ for local testing; never sends anything).
`from_env()` picks SMTP only when HUB_SMTP_HOST is set. The code is the only secret in a message and the message holds no link, so there is nothing to build from a Host header."""
import json
import os
import secrets
import smtplib
import ssl
import time
from email.message import EmailMessage

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


def from_env():
    host = os.getenv("HUB_SMTP_HOST", "").strip()
    if not host:
        return OutboxMailer()
    user = os.getenv("HUB_SMTP_USER", "")
    sender = os.getenv("HUB_MAIL_FROM", "").strip() or user
    return SMTPMailer(host, _port(os.getenv("HUB_SMTP_PORT", "")), user, os.getenv("HUB_SMTP_PASSWORD", ""), sender)
