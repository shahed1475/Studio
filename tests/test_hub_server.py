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


def test_demo_niche_is_public_free_rate_limited_and_stores_nothing(hub):
    port, _ = hub
    s, _, d, _ = call(port, "POST", "/api/demo/niche", {"text": "Calm stories about ancient civilizations and archaeology discoveries"}, XH)
    assert s == 200 and d["tier"] == "A" and d["matches"][0]["id"] == "ancient_civilizations"
    assert call(port, "POST", "/api/demo/niche", {"text": "daily crypto trading tips and bitcoin predictions"}, XH)[2]["state"] == "rejected"
    assert call(port, "POST", "/api/demo/niche", {"text": "x"})[0] == 403  # still needs the header
    assert db.connect().execute("select count(*) from tasks").fetchone()[0] == 0
    codes = [call(port, "POST", "/api/demo/niche", {"text": "history of medieval trade"}, XH)[0] for _ in range(22)]
    assert 429 in codes


def test_profile_is_private_validated_and_saved(hub):
    port, mail = hub
    assert call(port, "GET", "/api/profile")[0] == 401
    tok, _ = sign_in(port, mail)
    h = {**XH, "Cookie": f"hub_session={tok}"}
    s, _, d, _ = call(port, "GET", "/api/profile", headers=h)
    assert s == 200 and d["profile"]["niche_id"] == "" and d["platforms"]["youtube"] == "studio_upload"
    s, _, d, _ = call(port, "POST", "/api/profile", {"niche_id": "ancient_civilizations", "niche_text": "  Calm   stories ", "tier": "A", "platforms": ["youtube", "tiktok", "youtube"]}, h)
    assert s == 200 and d["profile"] == {"niche_id": "ancient_civilizations", "niche_text": "Calm stories", "tier": "A", "platforms": ["tiktok", "youtube"]}
    assert call(port, "POST", "/api/profile", {"niche_id": "made_up"}, h)[0] == 400
    assert call(port, "POST", "/api/profile", {"platforms": ["myspace"]}, h)[0] == 400
    other, _ = sign_in(port, mail, "other@example.com")
    assert call(port, "GET", "/api/profile", headers={**XH, "Cookie": f"hub_session={other}"})[2]["profile"]["niche_id"] == ""  # not shared between accounts


# Google's sign-in script puts a cookie named g_state on the site. Its value is JSON with quote marks, which Python's SimpleCookie cannot parse: it stopped there and the
# session cookie behind it was lost, so a person who had just signed in was sent back to the sign-in page (found in a real Chrome run, 10 Nov 2026).
G_STATE = 'g_state={"i_l":0,"i_ll":1794286161399,"i_b":"RTyNgLywmk2l884wbiX/7MwmgU/Pmum4o711vf7c2Cw","i_e":{"enable_itp_optimization":24},"i_et":1794286161399}'


@pytest.mark.parametrize("session_first", [False, True])
def test_session_survives_googles_json_cookie_in_either_order(hub, session_first):
    port, mail = hub
    token, _ = sign_in(port, mail)
    parts = [f"hub_session={token}", "hub_csrf=abc", G_STATE] if session_first else ["hub_csrf=abc", G_STATE, f"hub_session={token}"]
    assert call(port, "GET", "/api/me", headers={"Cookie": "; ".join(parts), **XH})[0] == 200


def test_parse_cookies_keeps_the_good_cookies_around_a_json_one():
    got = server.parse_cookies("hub_csrf=abc; " + G_STATE + "; hub_session=tok")
    assert got["hub_csrf"] == "abc" and got["hub_session"] == "tok" and got["g_state"].startswith('{"i_l":0')


def test_parse_cookies_survives_garbage_and_empty():
    assert server.parse_cookies("=; ;;noequals; x=y; =z") == {"x": "y"}
    assert server.parse_cookies("") == {}


def test_parse_cookies_first_value_wins():
    assert server.parse_cookies("hub_session=first; hub_session=second") == {"hub_session": "first"}


# ---- M3: the research store and the plan package ----
SRC = {"url": "https://en.wikipedia.org/wiki/Petra", "title": "Petra", "passage": "Petra is an archaeological site in southern Jordan.", "revised": "2026-10-01T00:00:00Z"}


def signed_in(port, mail, email="ann@example.com"):
    tok, _ = sign_in(port, mail, email)
    h = {**XH, "Cookie": f"hub_session={tok}"}
    return h, call(port, "GET", "/api/me", headers=h)[2]["account"]["id"]


def test_research_endpoint_needs_a_session_and_is_private(hub):
    from hub import research

    port, mail = hub
    assert call(port, "GET", "/api/research")[0] == 401
    h, aid = signed_in(port, mail)
    assert call(port, "GET", "/api/research", headers=h)[2] == {"ok": True, "sources": [], "topics": []}
    research.add_topic(aid, "Petra", SRC)
    d = call(port, "GET", "/api/research", headers=h)[2]
    assert len(d["topics"]) == 1 and d["topics"][0]["label"] == "PARTIALLY_VERIFIED" and d["sources"][0]["url"] == SRC["url"]
    other, _ = signed_in(port, mail, "other@example.com")
    assert call(port, "GET", "/api/research", headers=other)[2]["topics"] == []


def test_export_needs_a_session_and_a_known_platform(hub):
    port, mail = hub
    assert call(port, "GET", "/api/export?platform=tiktok")[0] == 401
    h, _ = signed_in(port, mail)
    assert call(port, "GET", "/api/export?platform=myspace", headers=h)[0] == 400
    assert call(port, "GET", "/api/export", headers=h)[0] == 400


def test_export_is_an_honest_markdown_download(hub):
    from hub import research

    port, mail = hub
    h, aid = signed_in(port, mail)
    assert call(port, "POST", "/api/profile", {"niche_id": "ancient_civilizations", "niche_text": "", "tier": "A", "platforms": ["tiktok"]}, h)[0] == 200
    research.add_topic(aid, "Petra", SRC)
    research.add_topic(aid, "Atlantis", None)
    s, hdr, body, _ = call(port, "GET", "/api/export?platform=tiktok", headers=h, raw=True)
    text = body.decode()
    assert s == 200 and hdr["Content-Type"].startswith("text/markdown") and "attachment" in hdr["Content-Disposition"] and hdr["X-Content-Type-Options"] == "nosniff"
    assert "Petra" in text and SRC["url"] in text and "PARTIALLY_VERIFIED" in text and "Atlantis" in text and "UNVERIFIED" in text
    assert "Nothing here was posted" in text and "manual_export" in text and "SECONDARY" in text and "Watch the whole video once" in text
    assert re.search(r"(?<!PARTIALLY_)(?<!UN)VERIFIED", text) is None  # the word VERIFIED never stands alone
    assert "Atlantis" not in call(port, "GET", "/api/export?platform=tiktok", headers=signed_in(port, mail, "other@example.com")[0], raw=True)[2].decode()


# ---- per-account AI key ----
AIKEY, AIMODEL = "sk-or-v1-" + "a1b2c3d4" * 8, "vendor/some-model"


class FakeOpenRouter:
    def __init__(self):
        self.status, self.error = 200, None

    def get(self, url, headers=None, timeout=None):
        if self.error:
            raise self.error
        return type("R", (), {"status_code": self.status, "json": lambda s: {}})()


@pytest.fixture()
def openrouter(monkeypatch):
    from hub import keystore, llm

    fake = FakeOpenRouter()
    monkeypatch.setattr(llm.requests, "get", fake.get)
    return fake


@pytest.fixture(autouse=True)
def key_master(tmp_path, monkeypatch):
    from hub import keystore

    monkeypatch.setattr(keystore, "MASTER_FILE", tmp_path / "hub" / "keystore.key")
    monkeypatch.delenv("HUB_KEYSTORE_KEY", raising=False)


def save_key(port, h, key=AIKEY, model=AIMODEL):
    return call(port, "POST", "/api/key", {"key": key, "model": model}, h, raw=True)


def test_key_endpoints_need_a_session_and_never_echo_the_key(hub, openrouter):
    port, mail = hub
    assert call(port, "GET", "/api/key")[0] == 401
    assert call(port, "POST", "/api/key", {"key": AIKEY, "model": AIMODEL}, XH)[0] == 401
    assert call(port, "POST", "/api/key/remove", {}, XH)[0] == 401
    h, _ = signed_in(port, mail)
    assert call(port, "GET", "/api/key", headers=h)[2] == {"ok": True, "set": False, "model": "", "added_at": None}
    s, hdr, body, _ = save_key(port, h)
    assert s == 200 and AIKEY.encode() not in body and json.loads(body)["verified"] is True
    s, hdr, body, _ = call(port, "GET", "/api/key", headers=h, raw=True)
    d = json.loads(body)
    assert d["set"] is True and d["model"] == AIMODEL and AIKEY.encode() not in body and all(AIKEY not in str(v) for v in hdr.values())
    assert call(port, "POST", "/api/key", {"key": AIKEY, "model": AIMODEL}, {"Cookie": h["Cookie"]})[0] == 403  # no X-Hub header: refused


def test_other_account_cannot_see_or_remove_a_key(hub, openrouter):
    port, mail = hub
    h, _ = signed_in(port, mail)
    save_key(port, h)
    other, _ = signed_in(port, mail, "other@example.com")
    assert call(port, "GET", "/api/key", headers=other)[2]["set"] is False
    assert call(port, "POST", "/api/key/remove", {}, other)[2]["removed"] is False
    assert call(port, "GET", "/api/key", headers=h)[2]["set"] is True
    assert call(port, "POST", "/api/key/remove", {}, h)[2]["removed"] is True and call(port, "GET", "/api/key", headers=h)[2]["set"] is False


def test_a_key_openrouter_refuses_is_not_stored(hub, openrouter):
    port, mail = hub
    h, _ = signed_in(port, mail)
    openrouter.status = 401
    s, _, body, _ = save_key(port, h)
    assert s == 400 and json.loads(body)["error"] == "key_rejected" and AIKEY.encode() not in body
    assert call(port, "GET", "/api/key", headers=h)[2]["set"] is False


def test_an_unreachable_check_stores_the_key_as_unverified(hub, openrouter):
    import requests

    port, mail = hub
    h, _ = signed_in(port, mail)
    openrouter.error = requests.ConnectionError("down")
    s, _, body, _ = save_key(port, h)
    assert s == 200 and json.loads(body)["verified"] is False and call(port, "GET", "/api/key", headers=h)[2]["set"] is True


@pytest.mark.parametrize("key,model,error", [("hello", AIMODEL, "bad_key"), (AIKEY, "nomodel", "bad_model"), ("sk-or-v1-" + "z" * 300, AIMODEL, "bad_key")])
def test_bad_shapes_are_refused_and_not_echoed(hub, openrouter, key, model, error):
    port, mail = hub
    h, _ = signed_in(port, mail)
    s, _, body, _ = save_key(port, h, key, model)
    assert s == 400 and json.loads(body)["error"] == error and key.encode() not in body and call(port, "GET", "/api/key", headers=h)[2]["set"] is False


def test_key_changes_are_limited_to_ten_an_hour(hub, openrouter):
    port, mail = hub
    h, _ = signed_in(port, mail)
    codes = [save_key(port, h)[0] for _ in range(12)]
    assert codes[:10] == [200] * 10 and codes[10:] == [429, 429]


def test_account_delete_needs_a_session_the_typed_word_and_clears_the_cookie(hub):
    port, mail = hub
    assert call(port, "POST", "/api/account/delete", {"confirm": "delete"}, XH)[0] == 401
    h, aid = signed_in(port, mail)
    assert call(port, "POST", "/api/account/delete", {"confirm": "delete"}, {"Cookie": h["Cookie"]})[0] == 403  # no X-Hub
    assert call(port, "POST", "/api/account/delete", {}, h)[0] == 400 and call(port, "POST", "/api/account/delete", {"confirm": "yes"}, h)[0] == 400
    assert call(port, "GET", "/api/me", headers=h)[0] == 200  # still there after the refusals
    other, _ = signed_in(port, mail, "other@example.com")
    s, hdr, d, _ = call(port, "POST", "/api/account/delete", {"confirm": " Delete "}, h)
    assert s == 200 and d == {"ok": True} and "Max-Age=0" in hdr["Set-Cookie"]
    assert call(port, "GET", "/api/me", headers=h)[0] == 401 and call(port, "GET", "/api/me", headers=other)[0] == 200


def test_the_privacy_page_is_served_with_the_page_security_headers(hub):
    port, _ = hub
    s, hdr, body, _ = call(port, "GET", "/privacy.html", raw=True)
    assert s == 200 and hdr["Content-Type"].startswith("text/html") and "Content-Security-Policy" in hdr and b"Privacy" in body
