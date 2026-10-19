import pytest

import webauth


@pytest.fixture(autouse=True)
def tmp_auth(tmp_path, monkeypatch):
    monkeypatch.setattr(webauth, "DATA", tmp_path)
    monkeypatch.setattr(webauth, "AUTH_FILE", tmp_path / "auth.json")
    monkeypatch.setattr(webauth, "SECRET_FILE", tmp_path / "auth_secret")
    monkeypatch.setattr(webauth, "SESSIONS_FILE", tmp_path / "sessions.json")
    webauth.LIMITER.fails.clear()


def test_open_until_a_password_is_set():
    assert not webauth.enabled()
    assert not webauth.verify("a@b.co", "whatever-long-1")


def test_password_roundtrip_and_hash_is_not_plain():
    webauth.set_password("Me@Gmail.com", "correct horse battery")
    assert webauth.verify("me@gmail.com", "correct horse battery")
    assert not webauth.verify("me@gmail.com", "wrong horse battery")
    assert not webauth.verify("other@gmail.com", "correct horse battery")
    assert "correct horse" not in webauth.AUTH_FILE.read_text()


def test_weak_password_rejected():
    with pytest.raises(ValueError):
        webauth.set_password("me@gmail.com", "short")
    with pytest.raises(ValueError):
        webauth.set_password("not-an-email", "long enough password")


def test_token_valid_expired_forged_and_after_password_change():
    webauth.set_password("me@gmail.com", "correct horse battery")
    t = webauth.make_token("me@gmail.com", now=1000)
    assert webauth.check_token(t, now=1001) == "me@gmail.com"
    assert webauth.check_token(t, now=1000 + 15 * 86400) is None
    assert webauth.check_token(t[:-2] + "00", now=1001) is None
    assert webauth.check_token("junk", now=1001) is None
    webauth.set_password("me@gmail.com", "another long password")
    assert webauth.check_token(t, now=1001) is None  # new password signs everyone out


def test_cookie_parsing():
    assert webauth.cookie_from("a=1; studio_session=xyz; b=2") == "xyz"
    assert webauth.cookie_from("") == ""


def test_limiter_blocks_after_five_and_recovers():
    for _ in range(5):
        webauth.LIMITER.fail("1.2.3.4", now=100)
    assert webauth.LIMITER.blocked("1.2.3.4", now=101)
    assert not webauth.LIMITER.blocked("1.2.3.4", now=100 + webauth.WINDOW + 1)
    assert not webauth.LIMITER.blocked("5.6.7.8", now=101)


def test_logout_kills_the_session_on_the_server():
    webauth.set_password("me@gmail.com", "correct horse battery")
    t = webauth.make_token("me@gmail.com")
    assert webauth.check_token(t) == "me@gmail.com"
    webauth.revoke(t)
    assert webauth.check_token(t) is None  # a copied cookie is dead too


def test_reserve_is_atomic_under_parallel_guesses():
    import threading
    got = []
    ts = [threading.Thread(target=lambda: got.append(webauth.LIMITER.reserve("9.9.9.9"))) for _ in range(40)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert got.count(True) == webauth.MAX_FAILS
