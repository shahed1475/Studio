"""The owner's Gemini (Google AI Studio) key in Settings (geminikey.py, 22 Nov 2026): saved hidden, format-checked, tested read-only, removable,
and read by the judge cascade (llm.gemini_key) when .env has none."""
import json

import pytest
import requests

import dashboard
import geminikey
import judges
import llm

KEY = "AIza" + "0123456789abcdefABCDEF0123456789abc"  # a stand-in with the real shape (39 characters), never a real key


@pytest.fixture
def settings(tmp_path, monkeypatch):
    f = tmp_path / "settings.json"
    f.write_text("{}")
    monkeypatch.setattr(dashboard, "SETTINGS", f)
    monkeypatch.setattr(llm, "SETTINGS_FILE", f)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("STUDIO_MODE", raising=False)
    return f


def test_the_key_is_saved_hidden_and_only_with_googles_shape(settings):
    assert dashboard.H.route(None, "/api/key/save", {"which": "gemini", "value": f"  {KEY}  "}) == {"ok": True}
    assert json.loads(settings.read_text())["gemini_api_key"] == KEY and (settings.stat().st_mode & 0o777) == 0o600
    for bad in ("not-a-google-key-at-all", "AIzashort", "sk-or-v1-" + "a" * 40, "KGAT_" + "a" * 30):
        with pytest.raises(ValueError, match="AIza") as e:
            dashboard.H.route(None, "/api/key/save", {"which": "gemini", "value": bad})
        assert bad not in str(e.value)  # the refused value is never echoed back
    assert json.loads(settings.read_text())["gemini_api_key"] == KEY


def test_the_settings_view_says_saved_and_never_holds_the_key(settings, monkeypatch):
    assert dashboard.state()["settings"]["gemini_key"] == ""
    dashboard.H.route(None, "/api/key/save", {"which": "gemini", "value": KEY})
    assert dashboard.state()["settings"]["gemini_key"] == "saved" and KEY not in json.dumps(dashboard.state(), default=str)


def test_the_judges_read_the_saved_key_and_env_wins(settings, monkeypatch):
    assert llm.gemini_key() == ""
    dashboard.H.route(None, "/api/key/save", {"which": "gemini", "value": KEY})
    assert llm.gemini_key() == KEY
    monkeypatch.setenv("GEMINI_API_KEY", "AIza" + "z" * 35)
    assert llm.gemini_key() == "AIza" + "z" * 35  # .env still wins, as before
    monkeypatch.delenv("GEMINI_API_KEY")
    assert judges._usable("gemini:gemini-3.5-flash-lite", None) != "no GEMINI_API_KEY"  # the judge cascade now counts Gemini as usable
    assert KEY not in llm.scrub(f"HTTP 400 for key {KEY}")  # a provider error that echoes the saved key is cleaned
    settings.write_text("{}")
    assert judges._usable("gemini:gemini-3.5-flash-lite", None) == "no GEMINI_API_KEY"  # and not once the key is gone


def test_the_test_is_one_read_only_call_with_the_key_in_a_header(settings):
    seen = []

    class R:
        status_code = 200

        def json(self):
            return {"models": [{"name": "a"}, {"name": "b"}]}

    def get(url, headers=None, timeout=None, allow_redirects=True):
        seen.append((url, headers, allow_redirects))
        return R()

    got = geminikey.test(KEY, get=get)
    assert got["ok"] and "2 models" in got["detail"] and KEY not in json.dumps(got)
    url, headers, redirects = seen[0]
    assert KEY not in url and headers["x-goog-api-key"] == KEY and redirects is False and url.startswith("https://generativelanguage.googleapis.com/")


def test_a_refused_or_unreachable_key_is_said_plainly_without_the_key():
    class Code:
        def __init__(self, c):
            self.status_code = c

    for code, word in ((400, "refused"), (403, "refused"), (429, "limiting")):
        got = geminikey.test(KEY, get=lambda *a, c=code, **k: Code(c))
        assert not got["ok"] and word in got["detail"] and KEY not in got["detail"]

    def boom(*a, **k):
        raise requests.ConnectionError(f"failed for {KEY}")

    got = geminikey.test(KEY, get=boom)
    assert not got["ok"] and KEY not in got["detail"]
    assert geminikey.test("")["detail"].startswith("No Gemini key")


def test_remove_deletes_only_the_saved_key(settings):
    dashboard.H.route(None, "/api/key/save", {"which": "gemini", "value": KEY})
    settings.write_text(json.dumps({**json.loads(settings.read_text()), "pixabay_key": "keep-me-0123456789"}))
    assert dashboard.H.route(None, "/api/gemini/remove", {})["ok"]
    left = json.loads(settings.read_text())
    assert "gemini_api_key" not in left and left["pixabay_key"] == "keep-me-0123456789"
