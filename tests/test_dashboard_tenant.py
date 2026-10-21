import http.client
import threading
from http.server import ThreadingHTTPServer

import pytest

import dashboard
import webauth


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setattr(webauth, "DATA", tmp_path)
    monkeypatch.setattr(webauth, "AUTH_FILE", tmp_path / "auth.json")
    monkeypatch.setattr(webauth, "SECRET_FILE", tmp_path / "auth_secret")
    monkeypatch.setattr(webauth, "SESSIONS_FILE", tmp_path / "sessions.json")
    monkeypatch.setattr(webauth, "INVITES_FILE", tmp_path / "invites.json")
    monkeypatch.setenv("STUDIO_MODE", "tenant")
    webauth.LIMITER.fails.clear()
    monkeypatch.setattr("time.sleep", lambda s: None)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), dashboard.H)
    monkeypatch.setattr(dashboard, "PORT", srv.server_address[1])
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address[1]
    srv.shutdown()


def call(port, method, path, body=None, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", port)
    c.request(method, path, body=body, headers={"Host": f"127.0.0.1:{port}", **(headers or {})})
    r = c.getresponse()
    return r.status, dict(r.getheaders()), r.read()


FORM = {"Content-Type": "application/x-www-form-urlencoded"}


def test_an_unclaimed_user_studio_serves_nothing_but_the_claim_page(server):
    for path in ("/", "/api/state", "/login", "/api/youtube/status"):
        assert call(server, "GET", path)[0] in (403, 401), path
    assert call(server, "POST", "/api/job", "{}")[0] in (403, 401)
    assert call(server, "GET", "/healthz")[0] == 200 and call(server, "GET", "/static/studio.css")[0] == 200
    assert call(server, "GET", "/claim?token=nope")[0] == 400


def test_the_invite_link_lets_the_user_choose_their_own_password_and_signs_them_in(server):
    tok = webauth.create_invite()
    st, _, body = call(server, "GET", f"/claim?token={tok}")
    assert st == 200 and b'name="password"' in body and tok.encode() in body
    st, _, _ = call(server, "POST", "/claim", f"token={tok}&email=user%40mail.com&password=short&password2=short", FORM)
    assert st == 400 and not webauth.enabled()  # too short: nothing saved, the link still works
    st, h, _ = call(server, "POST", "/claim", f"token={tok}&email=user%40mail.com&password=a-long-password-1&password2=different-password", FORM)
    assert st == 400 and not webauth.enabled()
    st, h, _ = call(server, "POST", "/claim", f"token={tok}&email=user%40mail.com&password=a-long-password-1&password2=a-long-password-1", FORM)
    assert st == 303 and "HttpOnly" in h["Set-Cookie"] and webauth.verify("user@mail.com", "a-long-password-1")
    ck = h["Set-Cookie"].split(";")[0]
    assert call(server, "GET", "/api/state", headers={"Cookie": ck})[0] == 200
    assert call(server, "GET", f"/claim?token={tok}")[0] == 400  # a used link is dead


def test_the_owners_studio_is_unchanged_without_the_mode(server, monkeypatch):
    monkeypatch.delenv("STUDIO_MODE")
    assert call(server, "GET", "/api/state")[0] == 200  # open until a password is set, as before


def test_wrong_password_attempts_are_counted_per_visitor_behind_the_proxy():
    class Fake:
        client_address = ("127.0.0.1", 5)
        headers = {"X-Forwarded-For": "203.0.113.9"}

    assert dashboard.client_ip(Fake) == "203.0.113.9"
    Fake.client_address = ("198.51.100.4", 5)  # not the proxy: the header is not trusted
    assert dashboard.client_ip(Fake) == "198.51.100.4"
    Fake.client_address, Fake.headers = ("127.0.0.1", 5), {}
    assert dashboard.client_ip(Fake) == "127.0.0.1"
