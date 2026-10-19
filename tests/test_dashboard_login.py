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
    webauth.LIMITER.fails.clear()
    monkeypatch.setattr("time.sleep", lambda s: None)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), dashboard.H)
    monkeypatch.setattr(dashboard, "PORT", srv.server_address[1])
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address[1]
    srv.shutdown()


def call(port, method, path, body=None, headers=None, host=None):
    c = http.client.HTTPConnection("127.0.0.1", port)
    h = {"Host": host or f"127.0.0.1:{port}", **(headers or {})}
    c.request(method, path, body=body, headers=h)
    r = c.getresponse()
    return r.status, dict(r.getheaders()), r.read()


def login(port, pw="correct horse battery"):
    return call(port, "POST", "/login", f"email=me%40gmail.com&password={pw}", {"Content-Type": "application/x-www-form-urlencoded"})


def test_open_without_password(server):
    assert call(server, "GET", "/api/state")[0] == 200


def test_everything_needs_login_once_a_password_exists(server):
    webauth.set_password("me@gmail.com", "correct horse battery")
    assert call(server, "GET", "/")[0] == 303
    assert call(server, "GET", "/api/state")[0] == 401
    assert call(server, "POST", "/api/job", "{}")[0] == 401
    assert call(server, "GET", "/healthz")[0] == 200
    assert call(server, "GET", "/static/studio.css")[0] == 200
    assert call(server, "GET", "/login")[0] == 200


def test_login_cookie_then_logout(server):
    webauth.set_password("me@gmail.com", "correct horse battery")
    st, h, _ = login(server)
    assert st == 303 and "HttpOnly" in h["Set-Cookie"] and "SameSite=Strict" in h["Set-Cookie"]
    ck = h["Set-Cookie"].split(";")[0]
    assert call(server, "GET", "/api/state", headers={"Cookie": ck})[0] == 200
    st, h2, _ = call(server, "POST", "/logout", "", {"Cookie": ck})
    assert st == 303 and "Max-Age=0" in h2["Set-Cookie"]


def test_wrong_password_and_lockout(server):
    webauth.set_password("me@gmail.com", "correct horse battery")
    assert login(server, "nope")[0] == 401
    for _ in range(4):
        login(server, "nope")
    assert login(server)[0] == 429  # even the right password waits once locked


def test_unknown_host_refused(server):
    assert call(server, "GET", "/healthz", host="evil.example:80")[0] == 403
