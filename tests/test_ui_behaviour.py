"""The dashboard in a real browser (Chrome headless, skipped where it is not installed): real clicks on the real page against a temporary data folder.

These cover behaviour a string check cannot: what a click does after the page re-renders itself."""
import json
import threading
from http.server import ThreadingHTTPServer

import pytest
import requests

import agentlog
import config
import dashboard
import footagestore
import llm
import webauth
import browserdrive

pytestmark = pytest.mark.skipif(not browserdrive.CHROME, reason="needs Chrome")

EVENTS = [("error", "A render failed", "ffmpeg exited 1"), ("applied", "Repaired a title", "put the phrase first"), ("strategy", "A new strategy", "post on Tuesdays"),
          ("info", "Checked the queue", "")]


@pytest.fixture
def app(tmp_path, monkeypatch):
    (tmp_path / "out").mkdir()
    monkeypatch.setattr(config, "OUT", tmp_path / "out")
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
    for kind, title, detail in EVENTS:
        agentlog.event(kind, title, detail)

    def no_network(*a, **k):
        raise requests.ConnectionError("blocked in tests")

    monkeypatch.setattr(requests.sessions.Session, "request", no_network)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), dashboard.H)
    monkeypatch.setattr(dashboard, "PORT", srv.server_address[1])
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    b = browserdrive.Browser()
    try:
        yield b, f"http://127.0.0.1:{srv.server_address[1]}"
    finally:
        b.close()
        srv.shutdown()


def open_panel(b):
    b.click("document.getElementById('bell')")
    b.until("document.getElementById('notes').classList.contains('open') && document.querySelectorAll('#nlist .nrow').length > 0")
    # the panel scales in over 0.3 s: wait until it has settled, as a person does, so that a click aims at where things really are
    b.until("(()=>{const n=document.getElementById('notes');const s=getComputedStyle(n);return s.opacity==='1'&&(s.transform==='none'||s.transform==='matrix(1, 0, 0, 1, 0, 0)')})()")


def is_open(b):
    return b.js("document.getElementById('notes').classList.contains('open')")


def test_the_panel_stays_open_when_a_filter_chip_is_clicked(app):
    """29 Oct 2026: a click on a chip re-rendered the chips, the page-wide 'click outside' check then no longer found the chip inside the panel and closed it."""
    b, url = app
    b.open(url + "/#home")
    open_panel(b)
    for label in ("Activity", "Warnings", "Growth", "All"):
        b.click(f"[...document.querySelectorAll('#nchips .chip')].find(x=>x.textContent.startsWith('{label}'))")
        assert is_open(b), f"the panel closed after clicking {label}"
        assert b.js(f"document.querySelector('#nchips .chip[aria-pressed=true]').textContent.startsWith('{label}')")
    assert json.loads(b.errors()) == []


def test_the_panel_closes_only_for_an_outside_click_escape_or_a_notification_and_gives_focus_back(app):
    b, url = app
    b.open(url + "/#home")
    open_panel(b)
    b.click("document.querySelector('.nhead h2')")  # the heading: still inside the panel
    assert is_open(b)
    b.click("document.querySelector('#nlist .ngroup')")
    assert is_open(b)
    b.key("Escape", "Escape", 27)
    b.until("!document.getElementById('notes').classList.contains('open')")
    assert b.js("document.activeElement.id") == "bell"
    open_panel(b)
    b.click("document.querySelector('#main h1')")  # outside
    b.until("!document.getElementById('notes').classList.contains('open')")
    open_panel(b)
    b.click("document.querySelector('#nlist .nrow')")  # a notification: it goes to its page and closes
    b.until("!document.getElementById('notes').classList.contains('open')")


def test_mark_all_read_keeps_the_panel_open_and_clears_the_unread_dots(app):
    b, url = app
    b.open(url + "/#home")
    open_panel(b)
    assert b.js("document.querySelectorAll('#nlist .nrow.unread').length") > 0
    b.click("[...document.querySelectorAll('.nhead .btn')].find(x=>x.textContent.includes('Mark all read'))")
    b.until("document.querySelectorAll('#nlist .nrow.unread').length === 0")
    assert is_open(b)


def test_the_background_refresh_does_not_rebuild_an_open_list_when_nothing_changed(app):
    """The panel refreshes every few seconds: rebuilding the rows made them all replay their entrance animation and reset what the person was looking at."""
    b, url = app
    b.open(url + "/#home")
    open_panel(b)
    b.js("document.querySelector('#nlist .nrow').__mark = 'same'")
    b.js("pollNotes()")
    b.js("pollNotes()")
    assert b.js("document.querySelector('#nlist .nrow').__mark") == "same"


def test_opening_the_panel_paints_it_once_and_the_first_refresh_finding_nothing_new_leaves_it_alone(app):
    """29 Oct 2026: opening reset the 'what is on screen' signature, so the first refresh after opening rebuilt the chips and rows a second time. A click that began on a chip
    just before that rebuild got no 'click' at all (Chrome sends none when the pressed element is removed), so the filter silently did not change."""
    b, url = app
    b.open(url + "/#home")
    b.until("typeof NT !== 'undefined' && NT !== null")  # the first background refresh has run
    b.js("window.__paints=0;new MutationObserver(m=>{__paints+=m.length}).observe(document.getElementById('nchips'),{childList:true})")
    b.click("document.getElementById('bell')")
    b.until("document.querySelectorAll('#nlist .nrow').length > 0")
    b.js("new Promise(r=>setTimeout(r,500))")  # the refresh that open starts has answered by now
    b.js("pollNotes()")
    b.js("new Promise(r=>setTimeout(r,300))")
    assert b.js("__paints") == 1, "the chips were rebuilt more than once"


def test_a_new_notification_does_change_an_open_list(app):
    b, url = app
    b.open(url + "/#home")
    open_panel(b)
    before = b.js("document.querySelectorAll('#nlist .nrow').length")
    agentlog.event("applied", "A brand new event", "arrived while the panel was open")
    b.js("pollNotes()")
    b.until(f"document.querySelectorAll('#nlist .nrow').length === {before + 1}")


def test_a_new_event_does_not_pop_a_toast_over_the_open_panel_where_it_would_take_the_click_meant_for_a_chip(app):
    """29 Oct 2026, found in the full suite: an event arriving while the panel was open raised a toast over the panel's chip row; the click on a chip landed on the
    toast, which opened its page and closed the panel. The panel lists the new event itself, so it needs no toast."""
    b, url = app
    b.open(url + "/#home")
    open_panel(b)
    agentlog.event("applied", "Arrived while the panel is open", "listed in the panel, not as a toast")
    b.js("pollNotes()")
    b.until("[...document.querySelectorAll('#nlist .nrow')].some(r=>r.textContent.includes('Arrived while the panel is open'))")
    assert b.js("document.querySelectorAll('#toasts .nt').length") == 0
    b.click("[...document.querySelectorAll('#nchips .chip')].find(x=>x.textContent.startsWith('Activity'))")
    assert is_open(b)


def test_a_toast_that_is_up_when_the_panel_opens_is_cleared_because_the_panel_lists_it(app):
    b, url = app
    b.open(url + "/#home")
    b.js("toastNote({level:'info',source:'Activity',title:'Early toast',detail:'',tab:'activity',id:'x'})")
    b.until("document.querySelectorAll('#toasts .nt').length === 1")
    open_panel(b)
    assert b.js("document.querySelectorAll('#toasts .nt').length") == 0


def test_a_new_event_still_pops_a_toast_while_the_panel_is_closed(app):
    b, url = app
    b.open(url + "/#home")
    b.until("typeof ntSeen!=='undefined' && ntSeen !== null")  # the first poll has run: later items count as new
    agentlog.event("applied", "Arrived while closed", "this one is a toast")
    b.js("pollNotes()")
    b.until("document.querySelectorAll('#toasts .nt').length === 1")


# ---- the Growth page on the data the studio really has (29 Oct 2026) ----
@pytest.fixture
def growth_data(tmp_path, monkeypatch):
    """What the server really holds: daily channel snapshots, a collector file with per-video numbers (many of them not available yet) and a weekly report that does
    NOT have the old 'analysis' and 'studied' keys."""
    import agent
    import growth
    import growthdata
    snaps = tmp_path / "own"
    snaps.mkdir()
    for i, (day, subs, views) in enumerate((("2026-10-19", 0, 0), ("2026-10-24", 3, 410), ("2026-10-28", 8, 1056))):
        (snaps / f"{day}.json").write_text(json.dumps({"date": day, "channel_id": "UC1", "title": "The Sleeping Library", "subscribers": subs, "views": views, "videos": 4 + i * 4, "recent": []}))
    monkeypatch.setattr(growth, "DIR", snaps)
    monkeypatch.setattr(agent, "latest_report", lambda: {"week": "2026-W44", "generated_at": "2026-10-28T06:30:00Z", "queued": [], "proposal": None, "winning": [], "losing": []})
    metrics = tmp_path / "videos.json"
    metrics.write_text(json.dumps({"updated": "2026-10-28T17:31:09Z", "problems": ["The Reporting API is not enabled"], "reach_reports_seen": [], "videos": {
        "abc": {"title": "Who Was Mami Wata?", "published": "2026-10-27T22:00:27Z", "seconds": 349, "kind": "doc", "daily_views_total": 7, "views_90d": None, "avg_pct_viewed": None,
                "retention_at_30s": None, "ctr": None, "impressions": None, "sources": {"ctr": "no reach report yet"}, "unavailable": {}},
        "def": {"title": "The Thunderbird", "published": "2026-10-20T12:00:00Z", "seconds": 58, "kind": "short", "daily_views_total": 54, "views_90d": 54, "avg_pct_viewed": 61.5,
                "retention_at_30s": 70.2, "ctr": None, "impressions": None, "sources": {}, "unavailable": {}}}}))
    monkeypatch.setattr(growthdata, "FILE", metrics)


def test_the_growth_page_shows_the_real_numbers_and_survives_the_real_report_shape(app, growth_data):
    """The page assumed every report has 'studied' and 'analysis': the real weekly report has neither, so it threw and showed nothing."""
    b, url = app
    b.open(url + "/#growth", wait_for="document.getElementById('main') && document.querySelectorAll('#main .kpi').length > 0")
    assert json.loads(b.errors()) == []
    tiles = b.js("[...document.querySelectorAll('#main .kpi')].map(e=>e.textContent.replace(/\\s+/g,' ').trim())")
    assert any("Subscribers" in t and "8" in t for t in tiles) and any("Views" in t and "1,056" in t for t in tiles)
    assert b.js("document.querySelectorAll('#main svg.chart polyline').length") == 1  # three snapshots make a line
    b.click("document.getElementById('gs-videos')")
    b.until("document.querySelector('#gwrap[data-sub=\"videos\"]') !== null")
    text = b.js("document.getElementById('gwrap').innerText")
    assert "Who Was Mami Wata?" in text and "The Thunderbird" in text and "61.5" in text
    assert "not available" in text.lower()  # a missing number is said to be missing, never shown as 0
    assert json.loads(b.errors()) == []


def test_the_growth_page_with_no_data_at_all_says_so_instead_of_breaking(app):
    b, url = app
    b.open(url + "/#growth", wait_for="document.getElementById('main') && document.querySelectorAll('#main h1').length > 0")
    assert json.loads(b.errors()) == []
    assert b.js("document.getElementById('main').innerText").count("Growth") >= 1


# ---- stopping work, and the Create video button (29 Oct 2026) ----
@pytest.fixture
def running_job(tmp_path, monkeypatch):
    import subprocess
    import time as _t

    import autopilot
    monkeypatch.setattr(dashboard, "LOGS", tmp_path / "logs")
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "100000-doc.log").write_text("Documentary: The Lost Army\nVoice...\n")
    monkeypatch.setattr(autopilot, "JOB_FILE", tmp_path / "job.pid")
    proc = subprocess.Popen(["sleep", "73"], start_new_session=True)
    (tmp_path / "job.pid").write_text(str(proc.pid))
    monkeypatch.setattr(dashboard, "JOBS", {"100000-doc": {"id": "100000-doc", "cmd": "doc", "status": "running", "started": _t.time(), "ended": None, "proc": proc, "before": []}})
    yield proc
    try:
        proc.kill()
    except OSError:
        pass


def test_a_running_job_can_be_stopped_from_the_live_page_with_a_second_click_to_confirm(app, running_job):
    b, url = app
    b.open(url + "/#live", wait_for="document.querySelectorAll('#lv-hero .stopbtn').length > 0")
    assert b.js("document.querySelector('#lv-hero .stopbtn').textContent.trim()") == "Stop"
    b.click("document.querySelector('#lv-hero .stopbtn')")
    assert "again" in b.js("document.querySelector('#lv-hero .stopbtn').textContent").lower()  # the first click only asks
    assert running_job.poll() is None  # nothing has been stopped yet
    b.click("document.querySelector('#lv-hero .stopbtn')")
    b.until("document.querySelectorAll('#lv-hero .stopbtn').length === 0", timeout=15)
    assert running_job.poll() is not None
    assert json.loads(b.errors()) == []


def test_the_activity_page_and_the_create_page_offer_stop_too(app, running_job):
    b, url = app
    b.open(url + "/#activity", wait_for="document.querySelectorAll('#main .stopbtn').length > 0")
    b.open(url + "/#create", wait_for="document.querySelectorAll('#main .choice').length > 0 && document.querySelectorAll('#main .stopbtn').length > 0")  # the Activity page's buttons must not satisfy it
    assert "creating a video" in b.js("document.getElementById('main').innerText").lower()
    assert b.js("[...document.querySelectorAll('#main .choice .btn')].every(x=>x.disabled)")  # one at a time


def test_the_create_button_is_called_create_video(app):
    b, url = app
    b.open(url + "/#create", wait_for="document.querySelectorAll('#main .choice').length > 0")
    labels = b.js("[...document.querySelectorAll('#main .choice .btn')].map(x=>x.textContent.trim())")
    assert labels == ["Create video", "Create Short"], labels
    assert "Make documentary" not in b.js("document.body.innerText")
