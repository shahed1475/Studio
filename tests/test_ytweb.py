import json
import time

import pytest

import ytweb


class FakeFlow:
    created = []

    def __init__(self, redirect_uri):
        self.redirect_uri, self.code_verifier, self.fetched = redirect_uri, "verifier-123", None
        FakeFlow.created.append(self)

    def authorization_url(self, **kw):
        self.kw = kw
        return "https://accounts.google.com/o/oauth2/auth?x=1", "state-from-google"

    def fetch_token(self, code):
        self.fetched = code
        self.credentials = type("C", (), {"to_json": lambda s: json.dumps({"refresh_token": "r", "token": "t"}), "refresh_token": "r"})()


@pytest.fixture
def web(tmp_path, monkeypatch):
    monkeypatch.setattr(ytweb, "SECRET", tmp_path / "web_client_secret.json")
    monkeypatch.setattr(ytweb, "PENDING", tmp_path / "data" / "oauth_pending.json")
    monkeypatch.setattr(ytweb, "TOKEN", tmp_path / "token.json")
    monkeypatch.setattr(ytweb, "_flow", lambda redirect_uri: FakeFlow(redirect_uri))
    monkeypatch.setattr(ytweb, "_after_login", lambda: None)
    monkeypatch.setattr(ytweb, "_channel_id", lambda creds: "UC_USER")
    monkeypatch.setenv("STUDIO_RENDER_GATE", str(tmp_path / "gate"))
    monkeypatch.setenv("STUDIO_NAME", "ann")
    monkeypatch.delenv("STUDIO_OWNER_CHANNELS", raising=False)
    FakeFlow.created.clear()
    ytweb.SECRET.write_text("{}")
    return tmp_path


def test_google_sign_in_on_the_web_is_offered_only_when_the_owner_has_added_the_web_client(web):
    assert ytweb.available() is True
    ytweb.SECRET.unlink()
    assert ytweb.available() is False
    with pytest.raises(ValueError, match="not set up"):
        ytweb.start("https://studio.example.com/oauth/callback")


def test_start_returns_googles_address_asking_for_a_refresh_token_and_remembers_the_verifier(web):
    url = ytweb.start("https://studio.example.com/oauth/callback", now=1000)
    assert url.startswith("https://accounts.google.com/") and FakeFlow.created[0].kw == {"access_type": "offline", "prompt": "select_account consent"}  # the account chooser always shows
    pending = json.loads(ytweb.PENDING.read_text())
    assert pending["state-from-google"]["verifier"] == "verifier-123" and pending["state-from-google"]["exp"] == 1000 + ytweb.WAIT


def test_finish_exchanges_the_code_once_writes_the_login_owner_only_and_refuses_unknown_state(web):
    ytweb.start("https://studio.example.com/oauth/callback", now=1000)
    ytweb.finish("the-code", "state-from-google", "https://studio.example.com/oauth/callback", now=1010)
    assert FakeFlow.created[-1].fetched == "the-code" and FakeFlow.created[-1].code_verifier == "verifier-123"
    assert json.loads(ytweb.TOKEN.read_text())["refresh_token"] == "r" and oct(ytweb.TOKEN.stat().st_mode)[-3:] == "600"
    with pytest.raises(ValueError, match="expired or unknown"):
        ytweb.finish("the-code", "state-from-google", "https://studio.example.com/oauth/callback", now=1011)  # one use only
    with pytest.raises(ValueError, match="expired or unknown"):
        ytweb.finish("x", "never-issued", "https://studio.example.com/oauth/callback", now=1011)


def test_a_state_that_waited_too_long_is_refused(web):
    ytweb.start("https://studio.example.com/oauth/callback", now=1000)
    with pytest.raises(ValueError, match="expired or unknown"):
        ytweb.finish("c", "state-from-google", "https://studio.example.com/oauth/callback", now=1000 + ytweb.WAIT + 1)
    assert not ytweb.TOKEN.exists()


def test_the_callback_address_comes_from_the_studios_own_public_name(monkeypatch):
    monkeypatch.setenv("STUDIO_HOSTS", "studio.example.com")
    assert ytweb.redirect_uri() == "https://studio.example.com/oauth/callback"
    monkeypatch.setenv("STUDIO_HOSTS", "")
    assert ytweb.redirect_uri() is None


def _sign_in(now=1000):
    ytweb.start("https://studio.example.com/oauth/callback", now=now)
    ytweb.finish("c", "state-from-google", "https://studio.example.com/oauth/callback", now=now + 5)


def test_the_owners_channel_is_refused_and_no_login_is_kept(web, monkeypatch):
    monkeypatch.setenv("STUDIO_OWNER_CHANNELS", "UC_OWNER, UC_OTHER_OWNER_CHANNEL")
    monkeypatch.setattr(ytweb, "_channel_id", lambda creds: "UC_OWNER")
    with pytest.raises(ValueError, match="owner's channel"):
        _sign_in()
    assert not ytweb.TOKEN.exists()


def test_a_channel_already_connected_to_another_studio_is_refused_and_the_same_studio_may_reconnect(web, monkeypatch):
    _sign_in(1000)
    assert ytweb.TOKEN.exists() and json.loads((web / "gate" / "channels.json").read_text()) == {"UC_USER": "ann"}
    _sign_in(2000)  # the same studio signing in again is fine
    monkeypatch.setenv("STUDIO_NAME", "bob")
    ytweb.TOKEN.unlink()
    with pytest.raises(ValueError, match="another studio"):
        _sign_in(3000)
    assert not ytweb.TOKEN.exists()


def test_disconnecting_gives_the_channel_back(web, monkeypatch):
    _sign_in()
    ytweb.release()
    assert json.loads((web / "gate" / "channels.json").read_text()) == {}
    monkeypatch.setenv("STUDIO_NAME", "bob")
    _sign_in(5000)  # now another studio can connect it
    assert json.loads((web / "gate" / "channels.json").read_text()) == {"UC_USER": "bob"}
