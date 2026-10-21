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
    Fake.headers = {"X-Forwarded-For": "1.2.3.4, 203.0.113.9"}  # a visitor can send their own first entry: only the last, added by our proxy, counts
    assert dashboard.client_ip(Fake) == "203.0.113.9"
    Fake.headers = {"X-Forwarded-For": "203.0.113.9"}
    Fake.client_address = ("198.51.100.4", 5)  # not the proxy: the header is not trusted
    assert dashboard.client_ip(Fake) == "198.51.100.4"
    Fake.client_address, Fake.headers = ("127.0.0.1", 5), {}
    assert dashboard.client_ip(Fake) == "127.0.0.1"


def test_in_a_user_studio_the_container_networks_gateway_counts_as_the_proxy(monkeypatch):
    class Fake:
        client_address = ("172.19.0.1", 5)  # how the proxy appears to a container behind Docker's published port
        headers = {"X-Forwarded-For": "203.0.113.9"}

    monkeypatch.delenv("STUDIO_MODE", raising=False)
    assert dashboard.client_ip(Fake) == "172.19.0.1"  # the owner's studio: not believed
    monkeypatch.setenv("STUDIO_MODE", "tenant")
    assert dashboard.client_ip(Fake) == "203.0.113.9"
    Fake.client_address = ("172.19.0.7", 5)  # another container on that network is not the gateway
    assert dashboard.client_ip(Fake) == "172.19.0.7"
    Fake.client_address = ("203.0.113.50", 5)
    assert dashboard.client_ip(Fake) == "203.0.113.50"


def test_a_user_studio_listens_only_on_its_bind_address_so_the_published_port_reaches_it(monkeypatch):
    monkeypatch.setenv("STUDIO_MODE", "tenant")
    monkeypatch.setenv("STUDIO_BIND", "0.0.0.0")
    assert dashboard.listen_addresses(claimed=False) == ["0.0.0.0"]  # unclaimed too: the invite page must be reachable, everything else is refused
    monkeypatch.delenv("STUDIO_MODE")
    assert dashboard.listen_addresses(claimed=False) == ["127.0.0.1"] and dashboard.listen_addresses(claimed=True) == ["127.0.0.1", "0.0.0.0"]


# ---- the niche page ----
import json
import time

import config
import niche
import topicqueue


@pytest.fixture
def signed_in(server, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "NICHE_FILE", tmp_path / "niche.json")
    monkeypatch.setattr(config, "TOPICS_FILE", tmp_path / "topics.json")
    topicqueue._write([])
    monkeypatch.setattr(dashboard.llm, "api_key", lambda: "sk-user-key")
    monkeypatch.setattr(dashboard, "_niche_yt", lambda: None)
    monkeypatch.setattr(dashboard, "TOKEN", tmp_path / "token.json")  # no YouTube login in these tests
    tok = webauth.create_invite()
    st, h, _ = call(server, "POST", "/claim", f"token={tok}&email=user%40mail.com&password=a-long-password-1&password2=a-long-password-1", FORM)
    ck = h["Set-Cookie"].split(";")[0]
    dashboard.NICHE_JOB.update(state="idle", step="", error="", fit=None)
    return server, {"Cookie": ck, "Content-Type": "application/json"}


def post(port, headers, path, obj):
    st, _, body = call(port, "POST", path, json.dumps(obj), headers)
    return st, json.loads(body)


def wait_done(port, headers):
    for _ in range(100):
        st, _, body = call(port, "GET", "/api/niche", headers=headers)
        view = json.loads(body)
        if view["job"]["state"] != "working":
            return view
        time.sleep(0.05)
    raise AssertionError("niche job never finished")


def test_the_niche_page_lists_the_presets_and_what_is_still_missing(signed_in, monkeypatch):
    port, h = signed_in
    monkeypatch.setattr(dashboard.llm, "api_key", lambda: "")
    st, _, body = call(port, "GET", "/api/niche", headers=h)
    view = json.loads(body)
    assert st == 200 and len(view["presets"]) == 10 and {"id", "name", "channel_angle", "starter_topics"} <= set(view["presets"][0])
    assert view["setup"] == {"key": False, "youtube": False} and view["current"]["brief"] is None
    st, out = post(port, h, "/api/niche/choose", {"id": "space_history"})
    assert st == 400 and "OpenRouter key" in out["error"]  # no key yet: nothing is spent or started


def test_choosing_a_preset_researches_it_in_the_background_and_stores_an_unconfirmed_brief(signed_in, monkeypatch):
    port, h = signed_in
    monkeypatch.setattr(niche, "research", lambda n, yt=None, **k: {"niche_id": n["id"], "topics": ["Apollo 13", "Sputnik 1"], "dropped": [], "advice": {"cadence": "x"}, "trend": {}, "youtube_connected": False})
    st, out = post(port, h, "/api/niche/choose", {"id": "space_history"})
    assert st == 200 and out["ok"]
    view = wait_done(port, h)
    assert view["job"]["state"] == "done" and view["current"]["niche"]["id"] == "space_history"
    assert view["current"]["brief"]["confirmed"] is False and topicqueue.items() == ["Apollo 13", "Sputnik 1"]
    assert post(port, h, "/api/niche/choose", {"id": "bogus"})[0] == 400
    st, out = post(port, h, "/api/niche/confirm", {})
    assert st == 200 and json.loads(call(port, "GET", "/api/niche", headers=h)[2])["current"]["brief"]["confirmed"] is True


def test_a_custom_idea_that_does_not_fit_is_answered_at_once_with_the_reason_and_the_closest_preset(signed_in, monkeypatch):
    port, h = signed_in
    monkeypatch.setattr(niche, "fit_check", lambda d, **k: {"fit": False, "reason": "Too broad.", "closest": "ancient_civilizations", "sample_topics": []})
    st, out = post(port, h, "/api/niche/custom", {"description": "everything about the past"})
    assert st == 200 and out["fit"] is False and out["reason"] == "Too broad." and out["closest"] == "ancient_civilizations"
    assert dashboard.NICHE_JOB["state"] == "idle"


def test_a_custom_idea_that_fits_is_built_and_researched(signed_in, monkeypatch):
    port, h = signed_in
    custom = {**niche.preset("space_history"), "id": "custom", "name": "Bronze Age trade"}
    monkeypatch.setattr(niche, "fit_check", lambda d, **k: {"fit": True, "reason": "ok", "closest": None, "sample_topics": ["A"] * 8})
    monkeypatch.setattr(niche, "build_custom", lambda d, fit, **k: custom)
    monkeypatch.setattr(niche, "research", lambda n, yt=None, **k: {"niche_id": "custom", "topics": ["Tin trade"], "dropped": [], "advice": {}, "trend": {}, "youtube_connected": False})
    st, out = post(port, h, "/api/niche/custom", {"description": "Bronze Age trade routes explained"})
    assert st == 200 and out["fit"] is True
    view = wait_done(port, h)
    assert view["current"]["niche"]["name"] == "Bronze Age trade" and topicqueue.items() == ["Tin trade"]


def test_a_failure_inside_the_job_is_shown_to_the_user_not_lost(signed_in, monkeypatch):
    port, h = signed_in

    def boom(n, yt=None, **k):
        raise RuntimeError("OpenRouter said no")

    monkeypatch.setattr(niche, "research", boom)
    post(port, h, "/api/niche/choose", {"id": "space_history"})
    view = wait_done(port, h)
    assert view["job"]["state"] == "error" and "OpenRouter said no" in view["job"]["error"]
    assert post(port, h, "/api/niche/choose", {"id": "space_history"})[0] == 200  # and the user can try again


def test_the_state_tells_the_page_it_is_a_user_studio_and_whether_the_plan_is_confirmed(signed_in, monkeypatch):
    port, h = signed_in
    st = json.loads(call(port, "GET", "/api/state", headers=h)[2])
    assert st["tenant"] is True and st["niche_confirmed"] is False
    niche.apply(niche.preset("space_history"), {"topics": ["Apollo 13"], "advice": {}})
    niche.confirm()
    assert json.loads(call(port, "GET", "/api/state", headers=h)[2])["niche_confirmed"] is True
    monkeypatch.delenv("STUDIO_MODE")
    monkeypatch.setattr(webauth, "AUTH_FILE", webauth.AUTH_FILE.with_name("none.json"))  # the owner's studio, open
    assert json.loads(call(port, "GET", "/api/state")[2])["tenant"] is False


def test_a_host_name_without_a_port_is_accepted_when_it_is_listed(monkeypatch):
    monkeypatch.setattr(dashboard, "PORT", 18921)
    monkeypatch.setenv("STUDIO_HOSTS", "studio.example.com, 100.1.2.3:8913")
    hosts = dashboard.allowed_hosts()
    assert "studio.example.com" in hosts and "studio.example.com:18921" in hosts and "100.1.2.3:8913" in hosts  # behind the proxy the browser sends no port
    assert "evil.example.com" not in hosts and "127.0.0.1:18921" in hosts


# ---- Google sign-in on the web ----
def test_the_youtube_page_offers_the_web_sign_in_and_starts_it(signed_in, monkeypatch):
    import ytweb
    port, h = signed_in
    monkeypatch.setenv("STUDIO_HOSTS", "studio.example.com")
    monkeypatch.setattr(ytweb, "available", lambda: True)
    st = json.loads(call(port, "GET", "/api/state", headers=h)[2])
    assert st["youtube"]["web"] is True
    seen = []
    monkeypatch.setattr(ytweb, "start", lambda redirect, **k: seen.append(redirect) or "https://accounts.google.com/o/oauth2/auth?x=1")
    st, out = post(port, h, "/api/youtube/web-start", {})
    assert st == 200 and out["url"].startswith("https://accounts.google.com/") and seen == ["https://studio.example.com/oauth/callback"]
    monkeypatch.setattr(ytweb, "redirect_uri", lambda: None)
    assert post(port, h, "/api/youtube/web-start", {})[0] == 400  # no public name set: nothing to send Google back to


def test_the_callback_needs_a_signed_in_user_and_reports_a_bad_state_plainly(signed_in, monkeypatch):
    import ytweb
    port, h = signed_in
    assert call(port, "GET", "/oauth/callback?code=c&state=s")[0] == 303  # not signed in: to the login page
    monkeypatch.setattr(ytweb, "finish", lambda code, state, redirect, **k: (_ for _ in ()).throw(ValueError("This sign-in link expired or unknown.")))
    st, _, body = call(port, "GET", "/oauth/callback?code=c&state=s", headers=h)
    assert st == 400 and b"expired or unknown" in body and b'href="/#youtube"' in body
    done = []
    monkeypatch.setattr(ytweb, "finish", lambda code, state, redirect, **k: done.append((code, state)))
    st, hh, _ = call(port, "GET", "/oauth/callback?code=the-code&state=the-state", headers=h)
    assert st == 303 and hh["Location"] == "/#youtube" and done == [("the-code", "the-state")]
    st, _, body = call(port, "GET", "/oauth/callback?error=access_denied", headers=h)
    assert st == 400 and b"not allowed" in body.lower()


def test_the_state_says_when_autopilot_or_a_repair_holds_the_lock_so_the_sidebar_is_not_wrongly_idle(signed_in, monkeypatch):
    import autopilot
    port, h = signed_in
    monkeypatch.setattr(autopilot, "is_running", lambda: True)
    assert json.loads(call(port, "GET", "/api/state", headers=h)[2])["autopilot"]["busy"] is True
    monkeypatch.setattr(autopilot, "is_running", lambda: False)
    assert json.loads(call(port, "GET", "/api/state", headers=h)[2])["autopilot"]["busy"] is False
