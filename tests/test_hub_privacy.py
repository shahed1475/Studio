"""Account deletion and the privacy page. Deleting must remove the person from the database file itself, not only from the tables."""
import re
from pathlib import Path

import pytest

from hub import a2a, agents, auth, db, keystore, profile, research

WEB = Path(__file__).resolve().parent.parent / "hub" / "web"
EMAIL = "gone.person@example.com"
KEY = "sk-or-v1-" + "NOTAREALKEY" * 6


class Mail:
    def __init__(self):
        self.sent = []

    def send(self, to, subject, body):
        self.sent.append(body)

    def code(self):
        return re.search(r"\b(\d{8})\b", self.sent[-1]).group(1)


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "PATH", tmp_path / "hub" / "hub.db")
    monkeypatch.setattr(auth, "SECRET_FILE", tmp_path / "hub" / "secret")
    monkeypatch.setattr(keystore, "MASTER_FILE", tmp_path / "hub" / "keystore.key")
    monkeypatch.delenv("HUB_KEYSTORE_KEY", raising=False)


def full_account(email=EMAIL, ip="5.5.5.5"):
    """An account with everything the hub can hold: a session, a profile, research, a stored key, a task and a pending code."""
    m = Mail()
    auth.request_code(email, ip, mailer=m, now=100.0)
    token = auth.verify_code(email, m.code(), ip, now=101.0)["token"]
    aid = auth.session_account(token, now=102.0)["id"]
    import niche

    profile.save(aid, "ancient_civilizations", "", "A", ["youtube"], niche.PRESET_IDS, agents.PLATFORMS)
    research.add_topic(aid, "Petra", {"url": "https://en.wikipedia.org/wiki/Petra", "title": "Petra", "passage": "Petra is a site.", "revised": ""})
    keystore.set_key(aid, KEY, "vendor/some-model")
    a2a.send(agents.AGENTS, aid, "concierge", {"message": {"messageId": "m", "role": "ROLE_USER", "parts": [{"text": "calm stories about ancient legends for adults"}]}})
    auth.request_code(email, ip, mailer=m, now=103.0)  # a code still waiting
    return aid, token


def file_bytes():
    return b"".join(p.read_bytes() for p in sorted(db.PATH.parent.glob("hub.db*")))


def counts(aid, email=EMAIL):
    with db.read() as con:
        n = lambda sql, *a: con.execute(sql, a).fetchone()[0]
        return {"accounts": n("select count(*) from accounts where id=?", aid), "sessions": n("select count(*) from sessions where account_id=?", aid),
                "profiles": n("select count(*) from profiles where account_id=?", aid), "sources": n("select count(*) from sources where account_id=?", aid),
                "topics": n("select count(*) from topics where account_id=?", aid), "keys": n("select count(*) from account_keys where account_id=?", aid),
                "tasks": n("select count(*) from tasks where account_id=?", aid), "codes": n("select count(*) from login_codes where email=?", email),
                "audit_linked": n("select count(*) from audit where account_id=?", aid)}


def test_deleting_an_account_removes_everything_and_the_email_leaves_the_database_file():
    aid, _ = full_account()
    before = counts(aid)
    assert all(before[k] >= 1 for k in ("accounts", "sessions", "profiles", "sources", "topics", "keys", "tasks", "codes", "audit_linked"))
    assert EMAIL.encode() in file_bytes()  # the check below means something only if it was there
    assert auth.delete_account(aid, now=200.0) is True
    assert counts(aid) == {k: 0 for k in before}
    assert EMAIL.encode() not in file_bytes() and b"Petra is a site" not in file_bytes()


def test_the_email_is_gone_from_the_write_ahead_log_even_while_another_connection_is_open():
    """On a busy server another request holds a connection open, so SQLite does not reset the log by itself: the deletion must checkpoint and truncate it."""
    aid, _ = full_account()
    keep = db.connect()
    keep.execute("select count(*) from accounts").fetchall()  # an idle open connection keeps the log file alive when the others close
    try:
        assert EMAIL.encode() in file_bytes()
        auth.delete_account(aid, now=200.0)
        assert EMAIL.encode() not in file_bytes()
    finally:
        keep.close()


def test_the_security_log_keeps_the_fact_of_the_deletion_but_no_person():
    aid, _ = full_account()
    auth.delete_account(aid, now=200.0)
    with db.read() as con:
        rows = [tuple(r) for r in con.execute("select * from audit")]
    assert any("account_deleted" in str(r) for r in rows) and aid not in str(rows) and EMAIL not in str(rows)


def test_the_session_stops_working_and_other_accounts_are_untouched():
    aid, token = full_account()
    other, other_token = full_account("stays@example.com", "6.6.6.6")
    assert auth.delete_account(aid, now=200.0) is True
    assert auth.session_account(token, now=201.0) is None
    assert auth.session_account(other_token, now=201.0)["id"] == other and counts(other, "stays@example.com")["topics"] == 1
    assert auth.delete_account(aid, now=202.0) is False  # already gone


def test_the_privacy_page_says_what_is_kept_and_how_to_leave():
    html = (WEB / "privacy.html").read_text()
    low = html.lower()
    for word in ("delete my account", "encrypted", "wikipedia", "cookie", "backup", "session", "audit", "openrouter", "email"):
        assert word in low, word
    assert "OWNER-TO-FILL" in html  # the contact line the owner must write before launch (deploy refuses to go public while it is here)
    assert not re.search(r"<script(?![^>]*\bsrc=)", html)  # no inline script: the page's CSP forbids it


@pytest.mark.parametrize("page", ["index.html", "signin.html", "app.html"])
def test_every_page_links_to_the_privacy_page(page):
    assert 'href="privacy.html"' in (WEB / page).read_text()
