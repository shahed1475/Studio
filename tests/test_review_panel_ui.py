"""The Reviewer report panel in a real browser (24 Nov 2026): it shows when a review was made, its id and the script it read, keeps earlier reviews
reachable, survives a page refresh on the same video, and says when the script changed after the review. Uses the app fixture of test_ui_behaviour."""
import json

import pytest

import browserdrive
import reviewer
from test_ui_behaviour import app  # noqa: F401 (the fixture)

pytestmark = pytest.mark.skipif(not browserdrive.CHROME, reason="needs Chrome")
SLUG = "doc-review-panel-test"


def reload(b):
    """A real browser refresh: the marker set before it must be gone after it, so the old page is never read by mistake."""
    b.js("window.__before_reload = 1")
    b.js("location.reload()")
    b.until("window.__before_reload === undefined && !!document.querySelector('[data-review-meta]')")


def _check(name, ok):
    return {"name": name, "ok": ok, "severity": "warn", "detail": f"{name} detail"}


def _write(meta, out):
    folder = out / SLUG
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "meta.json").write_text(json.dumps(meta))


def test_the_panel_shows_review_b_after_a_refresh_keeps_a_and_marks_a_changed_script_stale(app):  # noqa: F811
    import config

    b, base = app
    meta = {"title": "Panel Test Film", "format": "doc", "lines": [{"text": "Why did it happen?"}]}
    a = {"verdict": "pass", "at": "2026-11-21T12:32:26Z", "id": "aaaaaaaaaaaa", "script_sha": "111111111111", "checks": [_check("hook_question", False)]}
    meta["review"] = {"verdict": "pass", "at": "2026-11-24T01:00:00Z", "id": "bbbbbbbbbbbb", "script_sha": reviewer.script_fingerprint(meta),
                      "checks": [_check("duration", True)]}
    meta["review_history"] = [a]
    _write(meta, config.OUT)

    b.open(f"{base}/#videos/{SLUG}")
    b.until("!!document.querySelector('[data-review-meta]')")
    text = b.js("document.querySelector('[data-review-meta]').textContent")
    assert "bbbbbbbbbbbb" in text and "2026-11-24T01:00:00Z" in text and "stale" not in text
    assert "aaaaaaaaaaaa" in b.js("document.querySelector('[data-review-history]').textContent")  # review A is still reachable

    reload(b)  # a refresh stays on the same video and the same current review
    assert "bbbbbbbbbbbb" in b.js("document.querySelector('[data-review-meta]').textContent")

    meta["lines"] = [{"text": "A different opening line."}]  # the script changes after review B
    _write(meta, config.OUT)
    reload(b)
    assert "stale" in b.js("document.querySelector('[data-review-meta]').textContent")
    assert json.loads(b.errors() or "[]") == []  # no script errors on the page


def test_a_failed_review_try_is_shown_instead_of_a_silent_empty_panel(app):  # noqa: F811
    import config

    b, base = app
    _write({"title": "Panel Test Film", "format": "doc", "lines": [{"text": "x"}],
            "review_history": [{"verdict": "pass", "at": "2026-11-21T12:32:26Z", "id": "aaaaaaaaaaaa", "script_sha": "x", "checks": []}],
            "review_attempt": {"id": "cccccccccccc", "at": "2026-11-24T02:00:00Z", "verdict": "unreviewed", "script_sha": "x",
                               "why": "review unavailable: ModelUnavailable"}}, config.OUT)
    b.open(f"{base}/#videos/{SLUG}")
    b.until("!!document.querySelector('[data-review-attempt]')")
    assert "ModelUnavailable" in b.js("document.querySelector('[data-review-attempt]').textContent")
    assert "aaaaaaaaaaaa" in b.js("document.querySelector('[data-review-history]').textContent")


def test_same_script_note_a_malformed_link_and_back_forward_between_videos(app):  # noqa: F811
    import config

    b, base = app
    one = {"title": "Film One", "format": "doc", "lines": [{"text": "Why one?"}]}
    sha = reviewer.script_fingerprint(one)
    one["review"] = {"verdict": "pass", "at": "2026-11-24T01:00:00Z", "id": "bbbbbbbbbbbb", "script_sha": sha, "checks": []}
    one["review_history"] = [{"verdict": "pass", "at": "2026-11-21T12:32:26Z", "id": "aaaaaaaaaaaa", "script_sha": sha, "checks": []}]
    for slug, meta in ((SLUG, one), ("doc-second-film", {"title": "Film Two", "format": "doc", "lines": [{"text": "x"}]})):
        (config.OUT / slug).mkdir(parents=True, exist_ok=True)
        (config.OUT / slug / "meta.json").write_text(json.dumps(meta))

    b.open(f"{base}/#videos/{SLUG}")
    b.until("!!document.querySelector('[data-review-meta]')")
    assert "same script as the previous review" in b.js("document.querySelector('[data-review-meta]').textContent")

    b.js("location.hash = '#videos/doc-second-film'")  # like Back/Forward: the address names another video
    b.until("document.querySelector('h1') && document.querySelector('h1').textContent === 'Film Two'")
    b.js("history.back()")
    b.until("document.querySelector('h1') && document.querySelector('h1').textContent === 'Film One'")

    b.open(f"{base}/#videos/%E0")  # a malformed escape must not blank the page
    b.until("typeof S !== 'undefined' && S !== null && document.querySelectorAll('h1').length > 0")
    assert json.loads(b.errors() or "[]") == []
