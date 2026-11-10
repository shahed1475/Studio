"""The workspace in a real browser (Chrome headless, skipped where it is not installed).

Found by deploying (10 Nov 2026): the hub lists its agent cards with absolute addresses built from HUB_PUBLIC_URL, and the page's security policy only lets it talk to its own origin,
so a browser that reached the hub by any other address (an SSH tunnel on another port, an alias, a wrong setting) saw an empty team and a dead workspace. The page must work at
whatever address it was opened at."""
import http.client
import json
import re
import threading

import pytest

import browserdrive
from hub import auth, db, keystore, server

pytestmark = pytest.mark.skipif(not browserdrive.CHROME, reason="needs Chrome")


class Mail:
    def __init__(self):
        self.sent = []

    def send(self, to, subject, body):
        self.sent.append(body)


@pytest.fixture()
def hub_on_a_different_public_address(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "PATH", tmp_path / "hub" / "hub.db")
    monkeypatch.setattr(auth, "SECRET_FILE", tmp_path / "hub" / "secret")
    monkeypatch.setattr(keystore, "MASTER_FILE", tmp_path / "hub" / "keystore.key")
    monkeypatch.setenv("HUB_INSECURE_DEV", "1")
    monkeypatch.setenv("HUB_PUBLIC_URL", "http://localhost:1")  # nothing listens there: the configured public address is wrong on purpose
    mail = Mail()
    monkeypatch.setattr(server.Hub, "mailer", mail)
    srv = server.make_server("127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address[1], mail
    srv.shutdown()
    srv.server_close()


def signed_in_cookie(port, mail, email="origin@example.com"):
    def post(path, body):
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        c.request("POST", path, json.dumps(body), {"X-Hub": "1", "Content-Type": "application/json"})
        r = c.getresponse()
        return r.getheader("Set-Cookie"), r.read()

    post("/api/auth/request", {"email": email})
    code = re.search(r"\b(\d{8})\b", mail.sent[-1]).group(1)
    sc, _ = post("/api/auth/verify", {"email": email, "code": code})
    return re.search(r"hub_session=([^;]+)", sc).group(1)


def test_the_workspace_shows_its_team_even_when_the_configured_public_address_is_not_the_one_in_use(hub_on_a_different_public_address):
    port, mail = hub_on_a_different_public_address
    token = signed_in_cookie(port, mail)
    b = browserdrive.Browser(1200, 900)
    try:
        b.send("Network.enable")
        b.send("Network.setCookie", name="hub_session", value=token, url=f"http://localhost:{port}", httpOnly=True)
        b.open(f"http://localhost:{port}/app.html", wait_for="document.getElementById('team') && document.getElementById('team').children.length >= 7 && !document.querySelector('#team .skeleton')", timeout=25)
        names = b.js("[...document.querySelectorAll('#team li b')].map(e => e.textContent).join(',')")
        assert names.startswith("Concierge") and "Researcher" in names and b.errors() == "[]"
    finally:
        b.close()
