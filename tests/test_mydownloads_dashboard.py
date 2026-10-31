"""The Downloads tool in the dashboard: where it is, what its button opens, and that user studios never get it (real Chrome, skipped where it is missing)."""
import json
import threading
from http.server import ThreadingHTTPServer

import pytest
import requests

import agentlog
import browserdrive
import config
import dashboard
import footagestore
import llm
import mydownloads
import webauth

pytestmark = pytest.mark.skipif(not browserdrive.CHROME, reason="needs Chrome")


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


def test_downloads_is_a_tool_in_the_menu_and_opens_its_page(app):
    b, url = app
    b.open(url + "/#home")
    names = b.js("[...document.querySelectorAll('#nav3 button .t')].map(x => x.textContent)")
    assert "Downloads" in names and names.index("Downloads") > names.index("Footage")
    b.click("[...document.querySelectorAll('#nav3 button')].find(x => x.textContent.includes('Downloads'))")
    b.until("document.querySelector('#main h1')?.textContent === 'Downloads'")
    assert b.js("location.hash") == "#downloads"
    assert json.loads(b.errors()) == []


def test_the_button_opens_the_downloader_on_this_computer_in_a_new_tab(app):
    b, url = app
    b.open(url + "/#downloads", wait_for=b.READY + " && document.querySelector('#main h1')?.textContent === 'Downloads'")
    a = b.js("(() => { const a = document.querySelector('#main a.btn'); return [a.getAttribute('href'), a.target, a.rel, a.textContent.trim()] })()")
    assert a[0] == mydownloads.ADDRESS + "/" and a[1] == "_blank" and "noopener" in a[2] and a[3] == "Open the downloader"
    text = b.js("document.getElementById('main').textContent")
    assert "your own videos" in text and "systemctl --user start studio-mydownloads" in text and "phone" in text


def test_a_user_studio_never_gets_the_tool(app):
    b, url = app
    b.open(url + "/#home")
    assert "Downloads" in b.js("document.getElementById('nav3').textContent")
    b.js("S.tenant = true; chrome();")
    assert "Downloads" not in b.js("document.getElementById('nav3').textContent")
    assert "Downloads" not in b.js("document.getElementById('sheetcard').textContent")


def test_the_page_fits_a_phone_screen(app):
    b, url = app
    b.size(360, 740, mobile=True)
    b.open(url + "/#downloads", wait_for=b.READY + " && document.querySelector('#main h1')?.textContent === 'Downloads'")
    assert b.js("document.documentElement.scrollWidth <= window.innerWidth") is True
