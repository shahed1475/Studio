"""The three new dashboard panels in a real Chrome (21 Nov 2026): Search demand and What viewers ask (Autopilot > Research), Click rate
(Growth > Overview). They show what the files hold, escape outside text, and their buttons send the right requests. Skipped where Chrome is missing."""
import datetime as dt
import json
import threading
import time
from http.server import ThreadingHTTPServer

import pytest
import requests

import agentlog
import browserdrive
import commentinsights
import config
import dashboard
import footagestore
import growthdata
import llm
import searchdemand
import webauth

pytestmark = pytest.mark.skipif(not browserdrive.CHROME, reason="needs Chrome")
NOW = dt.datetime.now(dt.timezone.utc)
EVIL = '<img src=x onerror="window.__pwned=1">'


def demand_rows():
    return {"updated": NOW.isoformat(), "youtube_searches": 1, "note": "x", "rows": [
        {"topic": "The Devil's Bible: Codex Gigas", "subject": "The Devil's Bible", "score": 0.881, "at": NOW.isoformat(), "parts": {
            "autocomplete": {"hits": 10, "phrases": ["the devil's bible book", "the devil's bible explained"]},
            "wikipedia": {"title": "Codex Gigas", "avg_30": 1073.9, "avg_prev_30": 1220.0, "trend": 0.88, "days": 60},
            "youtube": {"results": 10, "median_views": 315774, "top_views": 9000000, "recent": 2, "small_channel_wins": 4}}},
        {"topic": EVIL, "subject": EVIL, "score": None, "at": NOW.isoformat(), "parts": {"autocomplete": None, "wikipedia": None, "youtube": None}}]}


def comments_data(setup=""):
    if setup:
        return {"updated": NOW.isoformat(), "own": [], "niche": [], "clusters": [], "ideas": [], "errors": ["own channel: HTTP 403 insufficientPermissions"],
                "quota_units": 1, "keep_days": 30, "setup": setup}
    row = {"fetched": NOW.isoformat(), "published": "2026-11-20T00:00:00Z"}
    return {"updated": NOW.isoformat(), "keep_days": 30, "quota_units": 9, "errors": [], "setup": "", "ideas_error": "",
            "own": [{**row, "q": "Who painted the devil page?", "video_id": "abcDEF12345", "video_title": "Our Codex Film", "channel": "", "likes": 3, "own": True}],
            "niche": [{**row, "q": "What language is the Voynich manuscript in? " + EVIL, "video_id": "n1", "video_title": "Voynich Explained", "channel": "Chan A",
                       "likes": 50, "own": False}],
            "clusters": [{"label": "voynich manuscript", "count": 4, "likes": 60, "examples": ["What language is the Voynich manuscript in?"]}],
            "ideas": ["The Voynich Manuscript's Unknown Script"]}


@pytest.fixture
def app(tmp_path, monkeypatch):
    (tmp_path / "out").mkdir()
    monkeypatch.setattr(config, "OUT", tmp_path / "out")
    monkeypatch.setattr(config, "TOPICS_FILE", tmp_path / "topics.json")
    (tmp_path / "topics.json").write_text("[]")
    monkeypatch.setattr(footagestore, "ROOT", tmp_path / "footage")
    monkeypatch.setattr(llm, "USAGE_FILE", tmp_path / "llm_usage.json")
    monkeypatch.setattr(llm, "_costs_file", lambda: tmp_path / "video_costs.json")
    monkeypatch.setattr(llm, "CONFIG_FILE", tmp_path / "llm.json")
    (tmp_path / "llm.json").write_text(json.dumps({"daily_budget_usd": 1.5}))
    monkeypatch.setattr(webauth, "DATA", tmp_path)
    monkeypatch.setattr(webauth, "AUTH_FILE", tmp_path / "auth.json")
    monkeypatch.setattr(webauth, "SECRET_FILE", tmp_path / "auth_secret")
    monkeypatch.setattr(webauth, "SESSIONS_FILE", tmp_path / "sessions.json")
    monkeypatch.setattr(agentlog, "FILE", tmp_path / "events.jsonl")
    started = []
    monkeypatch.setattr(dashboard, "start_job", lambda cmd, args: started.append((cmd, list(args))) or "job1")
    monkeypatch.setattr(requests.sessions.Session, "request", lambda *a, **k: (_ for _ in ()).throw(requests.ConnectionError("blocked in tests")))
    searchdemand.DIR.mkdir(parents=True, exist_ok=True)
    (searchdemand.DIR / "latest.json").write_text(json.dumps(demand_rows()))
    commentinsights.save(comments_data())
    day = (NOW - dt.timedelta(days=2)).date()
    growthdata.FILE.parent.mkdir(parents=True, exist_ok=True)
    growthdata.FILE.write_text(json.dumps({"updated": NOW.isoformat(), "problems": [], "videos": {
        "aaaaaaaaaaa": {"title": "Mami Wata", "kind": "doc", "reach": {(day - dt.timedelta(days=i)).isoformat(): {"impressions": 30, "ctr": 0.07} for i in range(20)}},
        "bbbbbbbbbbb": {"title": "Kitsune " + EVIL, "kind": "short", "reach": {(day - dt.timedelta(days=i)).isoformat(): {"impressions": 25, "ctr": 0.015} for i in range(20)}}}}))
    srv = ThreadingHTTPServer(("127.0.0.1", 0), dashboard.H)
    monkeypatch.setattr(dashboard, "PORT", srv.server_address[1])
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    b = browserdrive.Browser()
    try:
        yield b, f"http://127.0.0.1:{srv.server_address[1]}", started, tmp_path
    finally:
        b.close()
        srv.shutdown()


def research(b, url):
    b.open(url + "/#autopilot", wait_for=b.READY + " && !!document.getElementById('aps-research')")
    b.click("document.getElementById('aps-research')")
    b.until("!!document.querySelector('#sdemand .rows') && !!document.getElementById('scomments')")


def test_search_demand_shows_each_part_and_escapes_outside_text(app):
    b, url, started, _ = app
    research(b, url)
    text = b.js("document.getElementById('sdemand').innerText")
    assert "The Devil's Bible" in text and "Autocomplete 10/10" in text and "Wikipedia 1,074 a day" in text and "median 315,774 views" in text
    assert "4 small channels beat their size" in text and "People type: the devil's bible book" in text and "88 / 100" in text and "no signal" in text
    assert b.js("document.querySelectorAll('#sdemand img').length") == 0 and b.js("window.__pwned === undefined") is True
    b.click("[...document.querySelectorAll('#sdemand button')].find(x => x.textContent.includes('Check now'))")
    time.sleep(0.6)
    assert ("demand", []) in started
    assert json.loads(b.errors()) == []


def test_what_viewers_ask_shows_questions_links_ideas_and_adds_an_idea(app):
    b, url, started, tmp = app
    research(b, url)
    text = b.js("document.getElementById('scomments').innerText")
    assert "Who painted the devil page?" in text and "Our Codex Film" in text and "Chan A" in text and "voynich manuscript" in text
    href = b.js("document.querySelector('#scomments a.btn').getAttribute('href')")
    assert href == "https://studio.youtube.com/video/abcDEF12345/comments"
    assert b.js("document.querySelectorAll('#scomments img').length") == 0 and b.js("window.__pwned === undefined") is True
    b.click("[...document.querySelectorAll('#scomments button')].find(x => x.textContent.includes('Add to queue'))")
    b.until("[...document.querySelectorAll('#scomments button')].some(x => x.textContent === 'Added')")
    assert json.loads((tmp / "topics.json").read_text()) == ["The Voynich Manuscript's Unknown Script"]
    b.click("[...document.querySelectorAll('#scomments button')].find(x => x.textContent.includes('Check now'))")
    time.sleep(0.6)
    assert ("comments", ["--force"]) in started
    assert json.loads(b.errors()) == []


def test_without_a_key_the_panel_shows_the_setup_step_and_opens_settings(app):
    b, url, _, _ = app
    commentinsights.save(comments_data(setup=commentinsights.SETUP))
    research(b, url)
    text = b.js("document.getElementById('scomments').innerText")
    assert "One free setup step first" in text and "YouTube Data API key" in text
    b.click("[...document.querySelectorAll('#scomments button')].find(x => x.textContent.includes('Open Settings'))")
    b.until("location.hash === '#settings' && !!document.getElementById('ytkey')", 10)
    assert "No key saved yet" in b.js("document.getElementById('ytkey').innerText")
    assert b.js("document.getElementById('ytk').type") == "password"


def test_the_growth_overview_shows_the_click_rate(app):
    b, url, _, _ = app
    b.open(url + "/#growth", wait_for=b.READY + " && !!document.getElementById('gseg')")
    b.js("gSubSet('overview')")
    b.until("!!document.getElementById('gctr')")
    text = b.js("document.getElementById('gctr').innerText")
    assert "Click rate" in text and "Documentaries" in text and "7.0%" in text and "1.5%" in text and "Mami Wata" in text
    assert "2 videos have enough impressions to judge; 1 is under 3.0%" in text
    assert b.js("document.querySelectorAll('#gctr img').length") == 0 and b.js("window.__pwned === undefined") is True
    assert "No title change is logged yet" in text
    assert json.loads(b.errors()) == []


def test_the_panels_fit_a_phone(app):
    b, url, _, _ = app
    b.size(360, 760, mobile=True)
    research(b, url)
    assert b.js("document.documentElement.scrollWidth <= window.innerWidth") is True
    b.open(url + "/#growth", wait_for=b.READY + " && !!document.getElementById('gseg')")
    b.js("gSubSet('overview')")
    b.until("!!document.getElementById('gctr')")
    assert b.js("document.documentElement.scrollWidth <= window.innerWidth") is True
