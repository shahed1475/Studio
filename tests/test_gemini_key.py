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
    for bad in ("not-a-google-key-at-all", "AIzashort", "AQ.short", "sk-or-v1-" + "a" * 40, "KGAT_" + "a" * 30, "AQ." + "a" * 20 + " x"):
        with pytest.raises(ValueError, match="AQ. or AIza") as e:
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

    asked = []
    got = geminikey.test(KEY, get=get, chat=lambda k, m: asked.append(m) or "pong")
    assert got["ok"] and "answered a test question" in got["detail"] and KEY not in json.dumps(got)
    assert asked and asked[0] in geminikey.judge_models()  # one tiny question to a judge model, through the judges' own path
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


def test_the_newer_aq_format_that_ai_studio_issues_is_accepted(settings):
    """22 Nov 2026: the owner's new AI Studio key starts with 'AQ.' and the first card refused it (it only knew 'AIza')."""
    aq = "AQ." + "Ab8RN6fakefakefake_-" + "x" * 30  # a stand-in with the new shape, never a real key
    assert dashboard.H.route(None, "/api/key/save", {"which": "gemini", "value": aq}) == {"ok": True}
    assert json.loads(settings.read_text())["gemini_api_key"] == aq and llm.gemini_key() == aq


def test_a_key_google_lists_models_for_but_refuses_questions_with_is_not_a_green_tick():
    """22 Nov 2026: AQ. keys are reported to work on Google's own endpoint but fail with 401 on the OpenAI-style one the judges use."""
    class R:
        status_code = 200

        def json(self):
            return {"models": [{"name": "models/gemini-3.5-flash-lite"}]}

    class Refused(Exception):
        response = type("Resp", (), {"status_code": 401})()

    def chat(k, m):
        raise Refused(f"401 for {k}")

    got = geminikey.test(KEY, get=lambda *a, **k: R(), chat=chat)
    assert not got["ok"] and "HTTP 401" in got["detail"] and "AIza" in got["detail"] and KEY not in got["detail"]


def test_the_judges_call_tries_googles_own_header_when_bearer_is_refused(monkeypatch):
    sent = []

    class Resp:
        def __init__(self, code):
            self.status_code = code

        def raise_for_status(self):
            if self.status_code >= 400:
                raise requests.HTTPError(str(self.status_code))

        def json(self):
            return {"choices": [{"message": {"content": "pong"}}]}

    def post(url, *, timeout, json=None, headers=None, allow_redirects=True):
        sent.append(headers)
        return Resp(401 if "Authorization" in headers else 200)

    monkeypatch.setattr(llm, "_bounded_post", post)
    monkeypatch.setattr(llm, "_GEMINI_AUTH", {})
    assert llm.gemini_ping(KEY, "gemini-3.5-flash-lite") == "pong"  # an AIza key: Bearer first, refused, then x-goog-api-key
    assert "Authorization" in sent[0] and sent[1].get("x-goog-api-key") == KEY and llm._GEMINI_AUTH["aiza"] == "goog"
    sent.clear()
    llm.gemini_ping(KEY, "gemini-3.5-flash-lite")
    assert len(sent) == 1 and "x-goog-api-key" in sent[0]  # the style that worked is remembered
    monkeypatch.setattr(llm, "_bounded_post", lambda url, **k: sent.append(k["headers"]) or Resp(401))
    with pytest.raises(requests.HTTPError):
        llm.gemini_ping("AQ.x" * 10, "gemini-3.5-flash-lite")  # refused both ways: an error, never a silent pass


def test_a_400_naming_the_authorization_header_counts_as_a_refusal_and_bearer_comes_first(monkeypatch):
    """22 Nov 2026, measured with the owner's AQ. key: x-goog-api-key got HTTP 400 'Missing or invalid Authorization header', Bearer answered."""
    sent = []

    class Resp:
        def __init__(self, code, text=""):
            self.status_code, self.text = code, text

        def raise_for_status(self):
            if self.status_code >= 400:
                raise requests.HTTPError(str(self.status_code))

        def json(self):
            return {"choices": [{"message": {"content": "pong"}}]}

    def post(url, *, timeout, json=None, headers=None, allow_redirects=True):
        sent.append(headers)
        return Resp(200) if "Authorization" in headers else Resp(400, '{"error": {"message": "Missing or invalid Authorization header."}}')

    monkeypatch.setattr(llm, "_bounded_post", post)
    monkeypatch.setattr(llm, "_GEMINI_AUTH", {})
    aq = "AQ." + "x" * 40
    assert llm.gemini_ping(aq, "gemini-3.5-flash-lite") == "pong" and "Authorization" in sent[0] and len(sent) == 1
    monkeypatch.setattr(llm, "_GEMINI_AUTH", {"aq": "goog"})  # a remembered wrong style
    sent.clear()
    monkeypatch.setattr(llm, "_GEMINI_AUTH", {})
    monkeypatch.setattr(llm, "_bounded_post", lambda url, **k: sent.append(k["headers"]) or (Resp(400, "Missing or invalid Authorization header") if "x-goog-api-key" in k["headers"] else Resp(401)))
    with pytest.raises(requests.HTTPError):
        llm.gemini_ping(aq, "gemini-3.5-flash-lite")
    assert len(sent) == 2  # both styles were tried before the error


def test_the_script_fact_check_asks_gemini_first_when_a_key_is_saved_and_never_the_writer(settings, monkeypatch):
    """22 Nov 2026: the fact-check (llm._free_chat, role review) never asked the Gemini judges, so a saved key changed nothing while every other judge failed."""
    import freemodels

    asked = []
    monkeypatch.setattr(freemodels, "refresh", lambda now: None)
    monkeypatch.setattr(freemodels, "available", lambda m, now: True)
    monkeypatch.setattr(freemodels, "choose", lambda role, now, avoid=None, n=4: ["openrouter-model:free"])
    monkeypatch.setattr(llm, "extra_models", lambda role: [])
    monkeypatch.setattr(llm, "_race", lambda models, *a, **k: asked.append(list(models)) or None)
    monkeypatch.setattr(llm, "_ask_free", lambda mid, *a, **k: asked.append(mid) or None)
    monkeypatch.setattr(llm, "ROUNDS", 1)
    monkeypatch.setattr(llm, "_WRITERS", set())
    monkeypatch.setattr(llm, "_last_free", {})
    now = llm._now()
    llm._free_chat("p", "review", {}, "k", now)
    assert not any(str(m).startswith("gemini:") for m in str(asked)) or "gemini:" not in str(asked)  # no key: Gemini is not asked
    asked.clear()
    dashboard.H.route(None, "/api/key/save", {"which": "gemini", "value": KEY})
    llm._free_chat("p", "review", {}, "k", now)
    first = asked[0] if isinstance(asked[0], list) else [asked[0]]
    assert first[0].startswith("gemini:") and "openrouter-model:free" in str(asked)  # Gemini first, the others still after it
    asked.clear()
    llm._free_chat("p", "review", {}, "k", now, avoid={"gemini:gemini-3.5-flash-lite"})
    assert "gemini-3.5-flash-lite" not in str(asked)  # a writer (by identity) is never asked to judge
    asked.clear()
    llm._free_chat("p", "script", {}, "k", now)
    assert "gemini:" not in str(asked)  # writing never goes to the judges' Gemini models
