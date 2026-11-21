"""The dashboard's Reports page (reportsview.py): lists reports/ and the master report, serves only a name it listed itself
(never .env, a token, a path or a symlink), escapes the file before showing it, and is missing in user studios."""
import http.client
import json
import os
import threading
import time
from http.server import ThreadingHTTPServer

import pytest
import requests

import agentlog
import browserdrive
import config
import dashboard
import footagestore
import llm
import reportsview
import webauth


@pytest.fixture
def studio(tmp_path, monkeypatch):
    root = tmp_path / "studio"
    (root / "reports").mkdir(parents=True)
    (root / ".env").write_text("OPENROUTER_API_KEY=sk-or-secret\n")
    (root / "token.json").write_text('{"token": "secret"}')
    (root / "reports" / "OLD.md").write_text("# Old audit\n\nolder text\n")
    os.utime(root / "reports" / "OLD.md", (time.time() - 7200, time.time() - 7200))
    (root / "reports" / "AUTOPILOT_MASTER_AUDIT.md").write_text(
        "# Autopilot master audit\n\nIntro **bold** and `code`.\n\n| Area | Result |\n|---|---|\n| Dashboard | ok |\n\n- one\n- two\n")
    os.utime(root / "reports" / "AUTOPILOT_MASTER_AUDIT.md", (time.time() - 3600, time.time() - 3600))
    (root / "reports" / "NEWEST.md").write_text("# Newest\n\n<script>window.__x=1</script><img src=x onerror=\"window.__y=1\">\n")
    (root / "reports" / "notes.txt").write_text("not a report")
    (root / "reports" / "audit_ui.py").write_text("print(1)")
    (root / "YOUTUBE-AUTOMATION-MASTER-REPORT.md").write_text("# Master report\n\nall sections\n")
    monkeypatch.setattr(reportsview, "_root", lambda r=None: root)
    return root


def test_lists_only_markdown_reports_newest_first_and_opens_the_master_audit_first(studio):
    d = reportsview.listing()
    names = [r["name"] for r in d["reports"]]
    assert set(names) == {"OLD.md", "AUTOPILOT_MASTER_AUDIT.md", "NEWEST.md", "YOUTUBE-AUTOMATION-MASTER-REPORT.md"}
    assert names.index("NEWEST.md") < names.index("AUTOPILOT_MASTER_AUDIT.md") < names.index("OLD.md")
    assert d["start"] == "AUTOPILOT_MASTER_AUDIT.md"
    assert next(r for r in d["reports"] if r["name"] == "OLD.md")["title"] == "Old audit"


def test_without_the_master_audit_the_newest_report_opens_first(studio):
    (studio / "reports" / "AUTOPILOT_MASTER_AUDIT.md").unlink()
    assert reportsview.listing()["start"] == reportsview.listing()["reports"][0]["name"]


def test_an_empty_studio_has_no_reports(tmp_path, monkeypatch):
    monkeypatch.setattr(reportsview, "_root", lambda r=None: tmp_path)
    assert reportsview.listing() == {"reports": [], "start": None, "folder": "reports"}


def test_reads_a_listed_report(studio):
    r = reportsview.read("AUTOPILOT_MASTER_AUDIT.md")
    assert r["title"] == "Autopilot master audit" and "| Dashboard | ok |" in r["text"] and r["cut"] is False
    assert reportsview.read("YOUTUBE-AUTOMATION-MASTER-REPORT.md")["title"] == "Master report"


@pytest.mark.parametrize("name", ["../.env", ".env", "token.json", "../token.json", "reports/OLD.md", "/etc/passwd", "notes.txt",
                                  "audit_ui.py", "OLD", "", None, "..", "OLD.md/../../.env", "%2e%2e/.env"])
def test_never_serves_anything_it_did_not_list(studio, name):
    assert reportsview.read(name) is None


def test_a_symlink_in_reports_is_not_served(studio):
    (studio / "reports" / "LINK.md").symlink_to(studio / ".env")
    assert "LINK.md" not in [r["name"] for r in reportsview.listing()["reports"]]
    assert reportsview.read("LINK.md") is None


def test_a_big_report_is_cut_with_a_note(studio, monkeypatch):
    monkeypatch.setattr(reportsview, "MAX_BYTES", 10)
    r = reportsview.read("OLD.md")
    assert r["cut"] is True and len(r["text"]) == 10 and r["bytes"] > 10


# ---- the dashboard route


@pytest.fixture
def server(studio, tmp_path, monkeypatch):
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
    try:
        yield srv.server_address[1]
    finally:
        srv.shutdown()


def _get(port, path):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    c.request("GET", path, headers={"Host": f"127.0.0.1:{port}"})
    r = c.getresponse()
    return r.status, json.loads(r.read() or b"{}")


def _get_raw(port, path):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    c.request("GET", path, headers={"Host": f"127.0.0.1:{port}"})
    r = c.getresponse()
    r.read()
    return r.status


def test_the_api_lists_and_reads_reports(server):
    code, d = _get(server, "/api/reports")
    assert code == 200 and d["start"] == "AUTOPILOT_MASTER_AUDIT.md" and len(d["reports"]) == 4
    code, d = _get(server, "/api/reports?name=AUTOPILOT_MASTER_AUDIT.md")
    assert code == 200 and "| Dashboard | ok |" in d["text"]


@pytest.mark.parametrize("name", ["..%2F.env", ".env", "token.json", "%2Fetc%2Fpasswd", "notes.txt"])
def test_the_api_refuses_other_files(server, name):
    code, d = _get(server, "/api/reports?name=" + name)
    assert code == 404 and "text" not in d and "secret" not in json.dumps(d)


def test_a_user_studio_has_no_reports(server, monkeypatch):
    monkeypatch.setenv("STUDIO_MODE", "tenant")
    assert _get_raw(server, "/api/reports") == 403  # an unclaimed user studio refuses everything before any route
    monkeypatch.setattr(dashboard, "_tenant_unclaimed", lambda: False)  # a claimed one reaches the route, which refuses too
    assert _get(server, "/api/reports")[0] == 404
    assert _get(server, "/api/reports?name=OLD.md")[0] == 404


# ---- the page in a real Chrome


@pytest.fixture
def page(server):
    if not browserdrive.CHROME:
        pytest.skip("needs Chrome")
    b = browserdrive.Browser()
    try:
        yield b, f"http://127.0.0.1:{server}"
    finally:
        b.close()


OPEN = " && document.querySelector('#rp_doc .md') !== null"


def test_reports_is_a_tool_that_opens_the_master_audit_rendered(page):
    b, url = page
    b.open(url + "/#home")
    assert "Reports" in b.js("[...document.querySelectorAll('#nav3 button .t')].map(x => x.textContent)")
    b.click("[...document.querySelectorAll('#nav3 button')].find(x => x.textContent.includes('Reports'))")
    b.until("document.querySelector('#main h1')?.textContent === 'Reports'" + OPEN)
    assert b.js("location.hash") == "#reports"
    assert b.js("document.getElementById('rp_sel').value") == "AUTOPILOT_MASTER_AUDIT.md"
    assert b.js("document.querySelector('#rp_doc .md h2')?.textContent") == "Autopilot master audit"
    assert b.js("document.querySelector('#rp_doc .md table td')?.textContent") == "Dashboard"
    assert b.js("document.querySelector('#rp_doc .md b')?.textContent") == "bold"
    assert b.js("document.querySelectorAll('#rp_doc .md li').length") == 2
    assert json.loads(b.errors()) == []


def test_the_report_text_is_escaped_never_run(page):
    b, url = page
    b.open(url + "/#reports", wait_for=b.READY + OPEN)
    b.js("document.getElementById('rp_sel').value = 'NEWEST.md'; document.getElementById('rp_sel').dispatchEvent(new Event('change'))")
    b.until("document.querySelector('#rp_doc .md h2')?.textContent === 'Newest'")
    assert b.js("document.querySelectorAll('#rp_doc script, #rp_doc img').length") == 0
    assert b.js("window.__x === undefined && window.__y === undefined") is True
    assert "<script>" in b.js("document.getElementById('rp_doc').textContent")


def test_a_state_refresh_keeps_the_chosen_report(page):
    b, url = page
    b.open(url + "/#reports", wait_for=b.READY + OPEN)
    b.js("rpOpen('OLD.md', false)")
    b.until("document.querySelector('#rp_doc .md h2')?.textContent === 'Old audit'")
    b.js("render()")
    time.sleep(0.4)
    assert b.js("document.querySelector('#rp_doc .md h2')?.textContent") == "Old audit"
    assert b.js("document.getElementById('rp_sel').value") == "OLD.md"


def test_a_user_studio_never_sees_the_page(page):
    b, url = page
    b.open(url + "/#home")
    b.js("S.tenant = true; chrome();")
    assert "Reports" not in b.js("document.getElementById('nav3').textContent")
    assert "Reports" not in b.js("document.getElementById('sheetcard').textContent")


def test_the_page_fits_a_phone_screen(page):
    b, url = page
    b.size(360, 740, mobile=True)
    b.open(url + "/#reports", wait_for=b.READY + OPEN)
    assert b.js("document.documentElement.scrollWidth <= window.innerWidth") is True
