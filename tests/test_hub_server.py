import http.client
import json
import re
import threading

import pytest

from hub import auth, db, server


class Mail:
    def __init__(self):
        self.sent = []

    def send(self, to, subject, body):
        self.sent.append(body)

    def code(self):
        return re.search(r"\b(\d{8})\b", self.sent[-1]).group(1)


@pytest.fixture()
def hub(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "PATH", tmp_path / "hub" / "hub.db")
    monkeypatch.setattr(auth, "SECRET_FILE", tmp_path / "hub" / "secret")
    monkeypatch.setenv("HUB_INSECURE_DEV", "1")
    mail = Mail()
    monkeypatch.setattr(server.Hub, "mailer", mail)
    srv = server.make_server("127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address[1], mail
    srv.shutdown()
    srv.server_close()


def call(port, method, path, body=None, headers=None, raw=False):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    h = {"Content-Type": "application/json", **(headers or {})}
    c.request(method, path, body=(json.dumps(body) if body is not None else None), headers=h)
    r = c.getresponse()
    data = r.read()
    out = (r.status, dict(r.getheaders()), data if raw else (json.loads(data) if data and r.getheader("Content-Type", "").startswith("application/json") else data), r.getheaders())
    c.close()
    return out


XH = {"X-Hub": "1"}


def sign_in(port, mail, email="ann@example.com"):
    call(port, "POST", "/api/auth/request", {"email": email}, XH)
    s, h, d, _ = call(port, "POST", "/api/auth/verify", {"email": email, "code": mail.code()}, XH)
    assert s == 200
    return re.search(r"hub_session=([^;]+)", h["Set-Cookie"]).group(1), h["Set-Cookie"]


def msg(text):
    return {"jsonrpc": "2.0", "id": 1, "method": "SendMessage", "params": {"message": {"messageId": "m", "role": "ROLE_USER", "parts": [{"text": text}]}}}


def test_health_and_security_headers(hub):
    port, _ = hub
    s, h, d, _ = call(port, "GET", "/healthz")
    assert s == 200 and h["X-Content-Type-Options"] == "nosniff" and h["Referrer-Policy"] == "no-referrer"
    s, h, _, _ = call(port, "GET", "/")
    assert s == 200 and "default-src 'self'" in h["Content-Security-Policy"] and h["X-Frame-Options"] == "DENY"
    s, h, _, _ = call(port, "OPTIONS", "/a2a/concierge", headers={"Origin": "https://evil.example"})
    assert not any(k.lower().startswith("access-control") for k in h)


def test_email_sign_in_sets_a_hardened_cookie_and_me_works(hub):
    port, mail = hub
    tok, cookie = sign_in(port, mail)
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie
    s, _, d, _ = call(port, "GET", "/api/me", headers={"Cookie": f"hub_session={tok}"})
    assert s == 200 and d["account"]["email"] == "ann@example.com"
    assert call(port, "GET", "/api/me")[0] == 401
    s, h, _, _ = call(port, "POST", "/api/logout", {}, {**XH, "Cookie": f"hub_session={tok}"})
    assert s == 200 and "Max-Age=0" in h["Set-Cookie"]
    assert call(port, "GET", "/api/me", headers={"Cookie": f"hub_session={tok}"})[0] == 401


def test_secure_flag_is_on_unless_dev(hub, monkeypatch):
    port, mail = hub
    monkeypatch.delenv("HUB_INSECURE_DEV")
    _, cookie = sign_in(port, mail, "bob@example.com")
    assert "Secure" in cookie


def test_posts_need_the_custom_header_and_a_matching_origin(hub):
    port, mail = hub
    assert call(port, "POST", "/api/auth/request", {"email": "a@example.com"})[0] == 403
    assert call(port, "POST", "/api/auth/request", {"email": "a@example.com"}, {**XH, "Origin": "https://evil.example"})[0] == 403
    assert call(port, "POST", "/api/auth/request", {"email": "a@example.com"}, {**XH, "Origin": f"http://127.0.0.1:{port}"})[0] == 200
    tok, _ = sign_in(port, mail)
    assert call(port, "POST", "/a2a/concierge", msg("x"), {"Cookie": f"hub_session={tok}"})[0] == 403  # cookie without the header: refused


def test_a2a_needs_a_session_and_works_with_cookie_or_bearer(hub):
    port, mail = hub
    s, h, d, _ = call(port, "POST", "/a2a/concierge", msg("Calm stories about ancient civilizations and archaeology"))
    assert s == 401 and "Bearer" in h["WWW-Authenticate"]
    tok, _ = sign_in(port, mail)
    s, _, d, _ = call(port, "POST", "/a2a/concierge", msg("Calm stories about ancient civilizations and archaeology"), {**XH, "Cookie": f"hub_session={tok}"})
    assert s == 200 and d["result"]["task"]["status"]["state"] == "TASK_STATE_COMPLETED"
    s, _, d, _ = call(port, "POST", "/a2a/concierge", msg("Calm stories about ancient civilizations and archaeology"), {"Authorization": f"Bearer {tok}", "A2A-Version": "1.0"})
    assert s == 200 and "result" in d
    assert call(port, "POST", "/a2a/concierge", msg("x"), {"Authorization": "Bearer nonsense"})[0] == 401


def test_cards_are_public_and_listed(hub):
    port, _ = hub
    s, _, d, _ = call(port, "GET", "/a2a/")
    assert s == 200 and {a["id"] for a in d["agents"]} >= {"concierge", "publisher"}
    s, _, c, _ = call(port, "GET", "/a2a/concierge/.well-known/agent-card.json")
    assert s == 200 and c["supportedInterfaces"][0]["url"].endswith("/a2a/concierge") and c["name"] == "Concierge"
    assert call(port, "GET", "/a2a/ghost/.well-known/agent-card.json")[0] == 404


def test_streaming_comes_back_as_server_sent_events(hub):
    port, mail = hub
    tok, _ = sign_in(port, mail)
    body = msg("Calm stories about ancient civilizations and archaeology")
    body["method"] = "SendStreamingMessage"
    s, h, raw, _ = call(port, "POST", "/a2a/concierge", body, {"Authorization": f"Bearer {tok}"}, raw=True)
    assert s == 200 and h["Content-Type"] == "text/event-stream"
    events = [json.loads(line[6:]) for line in raw.decode().split("\n") if line.startswith("data: ")]
    assert [next(iter(e["result"])) for e in events] == ["task", "statusUpdate", "artifactUpdate", "statusUpdate"]


def test_oversized_bad_json_and_traversal_are_refused(hub):
    port, mail = hub
    tok, _ = sign_in(port, mail)
    h = {"Authorization": f"Bearer {tok}"}
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    c.request("POST", "/a2a/concierge", body=b"{not json", headers={**h, "Content-Type": "application/json"})
    assert c.getresponse().status == 400
    c.close()
    big = {"jsonrpc": "2.0", "id": 1, "method": "SendMessage", "params": {"pad": "x" * 70000}}
    assert call(port, "POST", "/a2a/concierge", big, h)[0] == 413
    assert call(port, "GET", "/%2e%2e/%2e%2e/etc/passwd")[0] == 404
    assert call(port, "GET", "/../../etc/passwd")[0] == 404


def test_google_endpoint_says_so_when_not_configured(hub, monkeypatch):
    port, _ = hub
    monkeypatch.delenv("HUB_GOOGLE_CLIENT_ID", raising=False)
    s, _, d, _ = call(port, "POST", "/api/auth/google", {"credential": "x", "csrf": "y"}, XH)
    assert s == 503 and d["error"] == "google_not_configured"
    s, h, d, _ = call(port, "GET", "/api/config")
    assert d["google_enabled"] is False and "hub_csrf=" in h["Set-Cookie"]


def test_a2a_calls_are_rate_limited_per_account(hub, monkeypatch):
    port, mail = hub
    monkeypatch.setattr(server, "CALLS_PER_MINUTE", 3)
    tok, _ = sign_in(port, mail)
    h = {"Authorization": f"Bearer {tok}"}
    codes = [call(port, "POST", "/a2a/concierge", msg("hi"), h)[0] for _ in range(5)]
    assert codes[:3] == [200, 200, 200] and codes[3:] == [429, 429]
