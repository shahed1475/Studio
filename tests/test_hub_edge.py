import json

import pytest

from hub import edge
from tests.test_hub_server import XH, call, hub  # noqa: F401  (the running server fixture)

SECRET = "edge-secret-value-123"


def test_without_a_secret_set_nothing_changes(hub, monkeypatch):
    monkeypatch.delenv("HUB_EDGE_SECRET", raising=False)
    port, _ = hub
    assert call(port, "GET", "/healthz")[0] == 200 and call(port, "GET", "/api/config")[0] == 200


def test_with_an_edge_secret_every_request_but_healthz_must_carry_it(hub, monkeypatch):
    monkeypatch.setenv("HUB_EDGE_SECRET", SECRET)
    port, _ = hub
    assert call(port, "GET", "/healthz")[0] == 200
    assert call(port, "GET", "/api/config")[0] == 403
    assert call(port, "GET", "/api/config", headers={"X-Edge-Secret": "wrong"})[0] == 403
    assert call(port, "POST", "/api/auth/request", {"email": "a@b.co"}, headers=XH)[0] == 403
    assert call(port, "GET", "/api/config", headers={"X-Edge-Secret": SECRET})[0] == 200


def test_the_visitor_address_is_believed_only_with_the_secret(monkeypatch):
    monkeypatch.setenv("HUB_EDGE_SECRET", SECRET)
    assert edge.client_ip({"X-Edge-Secret": SECRET, "X-Client-IP": "203.0.113.7"}) == "203.0.113.7"
    assert edge.client_ip({"X-Client-IP": "203.0.113.7"}) is None
    assert edge.client_ip({"X-Edge-Secret": SECRET, "X-Client-IP": "not an ip; drop table"}) is None
    monkeypatch.delenv("HUB_EDGE_SECRET")
    assert edge.client_ip({"X-Client-IP": "203.0.113.7"}) is None


def test_turnstile_is_off_until_a_secret_is_set(monkeypatch):
    monkeypatch.delenv("HUB_TURNSTILE_SECRET", raising=False)
    assert edge.turnstile_ok(None, "1.2.3.4") is True and edge.site_key() == ""


def test_turnstile_needs_a_token_cloudflare_confirms(monkeypatch):
    monkeypatch.setenv("HUB_TURNSTILE_SECRET", "ts-secret")
    monkeypatch.setenv("HUB_TURNSTILE_SITEKEY", "0xSITE")
    seen = []
    good = lambda url, form: seen.append((url, form)) or {"success": True}
    assert edge.turnstile_ok("a" * 30, "1.2.3.4", good) is True
    assert seen[0][0].startswith("https://challenges.cloudflare.com/") and seen[0][1]["secret"] == "ts-secret" and seen[0][1]["remoteip"] == "1.2.3.4"
    assert edge.turnstile_ok("a" * 30, "1.2.3.4", lambda u, f: {"success": False}) is False
    assert edge.turnstile_ok("", "1.2.3.4", good) is False and edge.turnstile_ok(None, "1.2.3.4", good) is False
    assert edge.turnstile_ok("a" * 30, "1.2.3.4", lambda u, f: (_ for _ in ()).throw(OSError("down"))) is False  # a failing check refuses
    assert edge.site_key() == "0xSITE"


def test_the_sign_in_request_is_refused_without_a_confirmed_token_and_never_mails(hub, monkeypatch):
    monkeypatch.setenv("HUB_TURNSTILE_SECRET", "ts-secret")
    monkeypatch.setattr(edge, "_post", lambda url, form: {"success": form["response"] == "t" * 20})
    port, mail = hub
    code, _h, body, _c = call(port, "POST", "/api/auth/request", {"email": "a@b.co"}, headers=XH)
    assert code == 400 and body["error"] == "bot_check" and mail.sent == []
    assert call(port, "POST", "/api/auth/request", {"email": "a@b.co", "turnstile": "x" * 20}, headers=XH)[0] == 400
    code = call(port, "POST", "/api/auth/request", {"email": "a@b.co", "turnstile": "t" * 20}, headers=XH)[0]
    assert code == 200 and len(mail.sent) == 1


def test_the_page_is_told_the_site_key_only_when_the_check_is_on(hub, monkeypatch):
    port, _ = hub
    monkeypatch.delenv("HUB_TURNSTILE_SECRET", raising=False)
    assert call(port, "GET", "/api/config")[2]["turnstile_site_key"] == ""
    monkeypatch.setenv("HUB_TURNSTILE_SECRET", "s")
    monkeypatch.setenv("HUB_TURNSTILE_SITEKEY", "0xSITE")
    assert call(port, "GET", "/api/config")[2]["turnstile_site_key"] == "0xSITE"


def test_behind_the_worker_the_pages_origin_is_checked_against_the_forwarded_host(hub, monkeypatch):
    monkeypatch.setenv("HUB_EDGE_SECRET", SECRET)
    monkeypatch.delenv("HUB_TURNSTILE_SECRET", raising=False)
    port, mail = hub
    ok = {**XH, "X-Edge-Secret": SECRET, "X-Forwarded-Host": "nightloom.me.workers.dev", "Origin": "https://nightloom.me.workers.dev"}
    assert call(port, "POST", "/api/auth/request", {"email": "a@b.co"}, headers=ok)[0] == 200
    assert call(port, "POST", "/api/auth/request", {"email": "a@b.co"}, headers={**ok, "Origin": "https://evil.example"})[0] == 403  # another site's page is still refused
