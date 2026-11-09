import hashlib
import re

import pytest

from hub import auth, db


class Mail:
    def __init__(self):
        self.sent = []

    def send(self, to, subject, body):
        self.sent.append((to, subject, body))

    def code(self):
        return re.search(r"\b(\d{8})\b", self.sent[-1][2]).group(1)


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "PATH", tmp_path / "hub" / "hub.db")
    monkeypatch.setattr(auth, "SECRET_FILE", tmp_path / "hub" / "secret")


def test_code_is_eight_digits_hashed_and_mailed():
    m = Mail()
    r = auth.request_code("Ann@Example.com ", "1.1.1.1", mailer=m, now=1000)
    assert r == auth.SENT and m.sent[0][0] == "ann@example.com"
    code = m.code()
    assert len(code) == 8
    rows = db.connect().execute("select * from login_codes").fetchall()
    assert len(rows) == 1 and code not in str(dict(rows[0])) and rows[0]["expires_at"] == 1000 + auth.CODE_TTL


def test_bad_address_is_refused_and_nothing_is_sent():
    m = Mail()
    for bad in ("", "no-at", "a@b", "x" * 300 + "@e.com", "a b@e.com"):
        assert auth.request_code(bad, "1.1.1.1", mailer=m, now=1)["ok"] is False
    assert m.sent == []


def test_verify_creates_account_and_session_and_code_is_single_use():
    m = Mail()
    auth.request_code("ann@example.com", "1.1.1.1", mailer=m, now=1000)
    ok = auth.verify_code("ann@example.com", m.code(), "1.1.1.1", now=1010)
    assert ok["ok"] and auth.session_account(ok["token"], now=1011)["email"] == "ann@example.com"
    again = auth.verify_code("ann@example.com", m.code(), "1.1.1.1", now=1012)
    assert again == auth.INVALID
    # the same person signing in again is the same account
    auth.request_code("ann@example.com", "1.1.1.1", mailer=m, now=1100)
    second = auth.verify_code("ann@example.com", m.code(), "1.1.1.1", now=1101)
    assert auth.session_account(second["token"], now=1102)["id"] == auth.session_account(ok["token"], now=1102)["id"]


def test_wrong_codes_lock_the_code_and_expiry_and_unknown_look_the_same():
    m = Mail()
    auth.request_code("ann@example.com", "1.1.1.1", mailer=m, now=1000)
    good = m.code()
    wrong = "00000000" if good != "00000000" else "11111111"
    for i in range(auth.MAX_TRIES):
        assert auth.verify_code("ann@example.com", wrong, "1.1.1.1", now=1001 + i) == auth.INVALID
    assert auth.verify_code("ann@example.com", good, "1.1.1.1", now=1010) == auth.INVALID  # locked even for the right code
    auth.request_code("bob@example.com", "2.2.2.2", mailer=m, now=2000)
    assert auth.verify_code("bob@example.com", m.code(), "2.2.2.2", now=2000 + auth.CODE_TTL + 1) == auth.INVALID
    assert auth.verify_code("nobody@example.com", "12345678", "3.3.3.3", now=3000) == auth.INVALID


def test_send_limits_per_address_and_per_ip():
    m = Mail()
    for i in range(auth.SEND_PER_EMAIL):
        assert auth.request_code("ann@example.com", "1.1.1.1", mailer=m, now=100 + i)["ok"]
    assert auth.request_code("ann@example.com", "1.1.1.1", mailer=m, now=200)["error"] == "too_many"
    assert auth.request_code("ann@example.com", "1.1.1.1", mailer=m, now=100 + 3601)["ok"]  # the window slides
    n = 0
    for i in range(auth.SEND_PER_IP + 3):
        n += auth.request_code(f"u{i}@example.com", "9.9.9.9", mailer=m, now=5000)["ok"]
    assert n == auth.SEND_PER_IP


def test_session_slides_then_hits_the_absolute_limit_and_logout_deletes_it():
    m = Mail()
    auth.request_code("ann@example.com", "1.1.1.1", mailer=m, now=0)
    tok = auth.verify_code("ann@example.com", m.code(), "1.1.1.1", now=1)["token"]
    day = 86400
    t = 1
    for _ in range(4):  # used every 6 days: the 7 day idle limit never trips
        t += 6 * day
        assert auth.session_account(tok, now=t)
    assert auth.session_account(tok, now=1 + auth.SESSION_ABSOLUTE + 1) is None  # only 6 days idle, but past the absolute end
    auth.request_code("cat@example.com", "1.1.1.1", mailer=m, now=10)
    tok2 = auth.verify_code("cat@example.com", m.code(), "1.1.1.1", now=11)["token"]
    assert auth.session_account(tok2, now=11 + auth.SESSION_IDLE + 1) is None
    auth.request_code("dan@example.com", "1.1.1.1", mailer=m, now=20)
    tok3 = auth.verify_code("dan@example.com", m.code(), "1.1.1.1", now=21)["token"]
    before = db.connect().execute("select count(*) from sessions").fetchone()[0]
    auth.logout(tok3)
    assert auth.session_account(tok3, now=22) is None
    assert db.connect().execute("select count(*) from sessions").fetchone()[0] == before - 1
    assert auth.session_account("garbage", now=22) is None and auth.session_account("", now=22) is None


def claims(**kw):
    base = {"iss": "https://accounts.google.com", "aud": "cid", "sub": "g-1", "email": "ann@gmail.com", "email_verified": True, "name": "Ann", "exp": 9e9}
    base.update(kw)
    return lambda token: base


def test_google_sign_in_and_its_refusals():
    r = auth.google_login("tok", "csrf", "csrf", verify=claims(), now=1)
    assert r["ok"] and auth.session_account(r["token"], now=2)["email"] == "ann@gmail.com"
    again = auth.google_login("tok", "c", "c", verify=claims(email="new@gmail.com"), now=3)  # same sub, changed email
    assert auth.session_account(again["token"], now=4)["id"] == auth.session_account(r["token"], now=4)["id"]
    assert auth.google_login("tok", "a", "b", verify=claims(), now=1) == auth.GOOGLE_REFUSED  # csrf mismatch
    assert auth.google_login("tok", "", "", verify=claims(), now=1) == auth.GOOGLE_REFUSED
    assert auth.google_login("tok", "c", "c", verify=claims(email_verified=False, sub="g-2"), now=1) == auth.GOOGLE_REFUSED
    assert auth.google_login("tok", "c", "c", verify=claims(iss="https://evil.example", sub="g-3"), now=1) == auth.GOOGLE_REFUSED

    def boom(token):
        raise ValueError("bad signature")
    assert auth.google_login("tok", "c", "c", verify=boom, now=1) == auth.GOOGLE_REFUSED


def test_google_links_to_an_email_account_only_when_google_is_authoritative():
    m = Mail()
    auth.request_code("ann@gmail.com", "1.1.1.1", mailer=m, now=1)
    first = auth.verify_code("ann@gmail.com", m.code(), "1.1.1.1", now=2)
    aid = auth.session_account(first["token"], now=3)["id"]
    g = auth.google_login("t", "c", "c", verify=claims(sub="g-9", email="ann@gmail.com"), now=4)
    assert auth.session_account(g["token"], now=5)["id"] == aid  # @gmail.com: Google is authoritative
    auth.request_code("pat@corp.example", "1.1.1.1", mailer=m, now=6)
    first = auth.verify_code("pat@corp.example", m.code(), "1.1.1.1", now=7)
    aid2 = auth.session_account(first["token"], now=8)["id"]
    other = auth.google_login("t", "c", "c", verify=claims(sub="g-10", email="pat@corp.example"), now=9)  # not gmail, no hd: do not link
    assert other == auth.GOOGLE_REFUSED
    ws = auth.google_login("t", "c", "c", verify=claims(sub="g-11", email="pat@corp.example", hd="corp.example"), now=10)
    assert auth.session_account(ws["token"], now=11)["id"] == aid2  # verified Workspace domain: linked


def test_audit_records_decisions_but_never_codes_or_tokens():
    m = Mail()
    auth.request_code("ann@example.com", "1.1.1.1", mailer=m, now=1)
    code = m.code()
    ok = auth.verify_code("ann@example.com", code, "1.1.1.1", now=2)
    auth.verify_code("ann@example.com", code, "1.1.1.1", now=3)
    text = " ".join(str(dict(r)) for r in db.connect().execute("select * from audit"))
    assert "code_sent" in text and "login_ok" in text and "login_failed" in text
    assert code not in text and ok["token"] not in text and "ann@example.com" not in text


def test_google_address_that_google_does_not_vouch_for_makes_an_account_without_that_address():
    r = auth.google_login("t", "c", "c", verify=claims(sub="g-20", email="victim@corp.example"), now=1)  # not gmail, no hd
    assert r["ok"] and r["account"]["email"] is None
    m = Mail()
    auth.request_code("victim@corp.example", "1.1.1.1", mailer=m, now=2)
    real = auth.verify_code("victim@corp.example", m.code(), "1.1.1.1", now=3)
    assert real["account"]["id"] != r["account"]["id"]  # the real owner of the address never lands in the pre-made account


def test_google_token_for_another_app_is_refused_when_our_client_id_is_set(monkeypatch):
    monkeypatch.setenv("HUB_GOOGLE_CLIENT_ID", "cid")
    assert auth.google_login("t", "c", "c", verify=claims(aud="someone-elses-app", sub="g-30"), now=1) == auth.GOOGLE_REFUSED
    assert auth.google_login("t", "c", "c", verify=claims(aud="cid", sub="g-31"), now=1)["ok"]
