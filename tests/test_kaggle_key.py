"""The owner's Kaggle API token in Settings (kagglekey.py, 22 Nov 2026): saved hidden, format-checked, tested read-only, removable, never in a user studio."""
import json
from pathlib import Path

import pytest
import requests

import dashboard
import kagglekey

TOKEN = "KGAT_" + "0123456789abcdef" * 2  # a stand-in with the real shape, never a real token


@pytest.fixture
def settings(tmp_path, monkeypatch):
    f = tmp_path / "settings.json"
    f.write_text("{}")
    monkeypatch.setattr(dashboard, "SETTINGS", f)
    monkeypatch.delenv("STUDIO_MODE", raising=False)
    return f


def test_the_token_is_saved_hidden_and_only_with_kaggles_shape(settings):
    assert dashboard.H.route(None, "/api/key/save", {"which": "kaggle", "value": f"  {TOKEN}  "}) == {"ok": True}
    assert json.loads(settings.read_text())["kaggle_api_token"] == TOKEN and (settings.stat().st_mode & 0o777) == 0o600
    for bad in ("not-a-kaggle-token-at-all", "KGAT_short", "KGAT_" + "a" * 20 + " x", "sk-or-v1-" + "a" * 40):
        with pytest.raises(ValueError, match="KGAT_") as e:
            dashboard.H.route(None, "/api/key/save", {"which": "kaggle", "value": bad})
        assert bad.strip() not in str(e.value)                                       # the refused value is never echoed back
    assert json.loads(settings.read_text())["kaggle_api_token"] == TOKEN             # a refused value never replaces the saved one


def test_the_settings_view_says_saved_and_never_holds_the_token(settings):
    dashboard.H.route(None, "/api/key/save", {"which": "kaggle", "value": TOKEN})
    view = dashboard.state()["settings"]
    assert view["kaggle_key"] == "saved" and TOKEN not in json.dumps(dashboard.state(), default=str)


def test_the_test_is_one_read_only_call_with_the_token_in_a_header(settings, monkeypatch):
    seen = []

    class R:
        status_code = 200

        def json(self):
            return [{"ref": "titanic"}, {"ref": "digits"}]

    def get(url, **kw):
        seen.append((url, kw))
        return R()

    got = kagglekey.test(TOKEN, get=get)
    url, kw = seen[0]
    assert got["ok"] and "2 competitions" in got["detail"] and TOKEN not in json.dumps(got)
    assert url == "https://www.kaggle.com/api/v1/competitions/list" and TOKEN not in url          # never in the address
    assert kw["headers"]["Authorization"] == f"Bearer {TOKEN}" and kw["timeout"] == 15 and kw["allow_redirects"] is False


@pytest.mark.parametrize("code, words", [(401, "refused"), (403, "refused"), (429, "limiting"), (500, "HTTP 500")])
def test_a_refusal_or_an_error_is_plain_words_and_never_the_token(code, words):
    class R:
        status_code = code

    got = kagglekey.test(TOKEN, get=lambda url, **kw: R())
    assert not got["ok"] and words in got["detail"] and TOKEN not in got["detail"]


def test_a_network_error_never_shows_the_token():
    def get(url, **kw):
        raise requests.ConnectionError(f"failed with header Bearer {TOKEN}")

    got = kagglekey.test(TOKEN, get=get)
    assert not got["ok"] and TOKEN not in json.dumps(got) and "could not be reached" in got["detail"]
    assert kagglekey.test("")["detail"].startswith("No Kaggle token")


def test_the_dashboard_test_and_remove_routes(settings, monkeypatch):
    monkeypatch.setattr(kagglekey, "test", lambda token: {"ok": token == TOKEN, "detail": "stand-in"})
    assert dashboard.H.route(None, "/api/kaggle/test", {})["ok"] is False                       # nothing saved yet
    dashboard.H.route(None, "/api/key/save", {"which": "kaggle", "value": TOKEN})
    assert dashboard.H.route(None, "/api/kaggle/test", {})["ok"] is True
    assert dashboard.H.route(None, "/api/kaggle/remove", {})["ok"] is True
    assert "kaggle_api_token" not in json.loads(settings.read_text())


def test_a_user_studio_never_gets_the_token_card_or_routes(settings, monkeypatch):
    monkeypatch.setenv("STUDIO_MODE", "tenant")
    for path, body in (("/api/key/save", {"which": "kaggle", "value": TOKEN}), ("/api/kaggle/test", {}), ("/api/kaggle/remove", {})):
        with pytest.raises(ValueError, match="user studio"):
            dashboard.H.route(None, path, body)
    assert "kaggle_api_token" not in json.loads(settings.read_text())


def test_the_settings_card_is_a_hidden_field_with_a_label_and_no_browser_dialog():
    html = (Path(dashboard.__file__).parent / "dashboard.html").read_text()
    card = html[html.index('id="kagglekey"'):html.index("${xllmCard()}")]
    assert 'id="kgt" type="password" autocomplete="new-password"' in card and '<label for="kgt"' in card
    assert "non-commercial" in card and 'aria-live="polite"' in card
    js = html[html.index("async function kaggleAct"):html.index("async function kaggleAct") + 900]
    assert "confirm(" not in js and "alert(" not in js and "Click again to remove" in js
