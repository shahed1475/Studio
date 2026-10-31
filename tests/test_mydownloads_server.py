"""My Downloads: the small local web server: who may talk to it, what it serves, and the whole find-then-download flow with a fake engine."""
import http.client
import json
import socket
import threading
import types

import pytest

from mydownloads import engine, jobs, server, store

CID = "UCYeOLFYx2orIghktFlQrV7A"
VID = "v0000000001"


def wait(seconds):
    threading.Event().wait(seconds)  # the shared test setup replaces time.sleep


class FakeEngine:
    def __init__(self):
        self.last, self.explode, self.gate = None, False, None

    def plan(self, it, only_channel=None):
        self.last = (it, only_channel)
        if self.explode:
            raise Exception("ERROR: Unable to download webpage: getaddrinfo failed")
        return {"items": [{"id": VID, "title": "T", "kind": "long", "url": "u", "duration": 300, "channel": "C", "channel_id": CID, "saved": False, "owned": True,
                           "refused": "", "error": "", "partial": False}], "notes": list(it.notes)}

    def resolve_channel(self, text):
        if text == "@mine":
            return {"id": CID, "title": "The Sleeping Library", "handle": "@thesleepinglib"}
        raise ValueError("I could not find a channel at that address.")

    def download(self, video_id, folder, on_progress, stop):
        if self.gate is not None:
            self.gate.wait(5)
        out = folder / "C" / f"T [{video_id}].mp4"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"x" * 100)
        return out


@pytest.fixture
def srv(tmp_path, monkeypatch):
    monkeypatch.setenv("MYDL_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("MYDL_FOLDER", str(tmp_path / "Downloads"))
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<!doctype html><title>Downloads</title><script src=/app.js></script>")
    (web / "app.js").write_text("console.log(1)")
    (web / "style.css").write_text("body{}")
    (tmp_path / "geist.woff2").write_bytes(b"wOF2")
    (tmp_path / "secret.txt").write_text("not for the web")
    eng = FakeEngine()
    runner = jobs.Runner(eng, threaded=True, sleep=lambda s: None, free_bytes=lambda p: 50 << 30)
    opened = []
    httpd = server.make_server(server.App(eng, runner, web_dir=web, font=tmp_path / "geist.woff2", open_folder=opened.append), port=0)
    threading.Thread(target=lambda: httpd.serve_forever(poll_interval=0.02), daemon=True).start()  # the default 0.5 s poll made every shutdown slow
    yield types.SimpleNamespace(port=httpd.server_port, eng=eng, runner=runner, opened=opened, tmp=tmp_path)
    httpd.shutdown()
    httpd.server_close()


def call(s, method, path, body=None, headers=None, host=None):
    c = http.client.HTTPConnection("127.0.0.1", s.port, timeout=10)
    h = {"Host": host or f"127.0.0.1:{s.port}"}
    if method == "POST":
        h.update({"X-MyDownloads": "1", "Content-Type": "application/json"})
    h.update(headers or {})
    h = {k: v for k, v in h.items() if v is not None}
    c.request(method, path, body=json.dumps(body) if body is not None else None, headers=h)
    r = c.getresponse()
    data = r.read()
    c.close()
    return r.status, {k.lower(): v for k, v in r.getheaders()}, data


def js(data):
    return json.loads(data)


def wait_for_job(s, states=("done", "stopped")):
    for _ in range(200):
        j = js(call(s, "GET", "/api/state")[2])["job"]
        if j and j["state"] in states:
            return j
        wait(0.05)
    raise AssertionError("the job did not finish")


# ---- who may talk to it
@pytest.mark.parametrize("host", ["evil.example", "evil.example:80", "127.0.0.1", "127.0.0.1:1", "localhost:1"])
def test_a_wrong_host_name_is_refused(srv, host):
    assert call(srv, "GET", "/api/state", host=host)[0] == 403
    assert call(srv, "GET", "/", host=host)[0] == 403


def test_localhost_is_allowed_too(srv):
    assert call(srv, "GET", "/api/state", host=f"localhost:{srv.port}")[0] == 200


def test_a_post_without_the_header_is_refused(srv):
    assert call(srv, "POST", "/api/plan", {"text": "my last 3 videos"}, headers={"X-MyDownloads": None})[0] == 403


def test_a_post_from_another_website_is_refused(srv):
    assert call(srv, "POST", "/api/plan", {"text": "my last 3 videos"}, headers={"Origin": "http://evil.example"})[0] == 403
    assert call(srv, "POST", "/api/plan", {"text": "my last 3 videos"}, headers={"Origin": "null"})[0] == 403


@pytest.mark.parametrize("origin", ["http://127.0.0.1:{p}", "http://localhost:{p}"])
def test_a_post_from_its_own_page_is_allowed(srv, origin):
    assert call(srv, "POST", "/api/plan", {"text": "my last 3 videos"}, headers={"Origin": origin.format(p=srv.port)})[0] == 200


def test_it_never_asks_the_browser_to_share_answers_with_other_sites(srv):
    _, h, _ = call(srv, "GET", "/api/state")
    assert not any(k.startswith("access-control-") for k in h)
    st, h, _ = call(srv, "OPTIONS", "/api/plan", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"})
    assert st in (403, 405, 501) and not any(k.startswith("access-control-") for k in h)


def test_an_oversize_body_is_refused_without_reading_it(srv):
    s = socket.create_connection(("127.0.0.1", srv.port), timeout=10)
    s.sendall((f"POST /api/plan HTTP/1.1\r\nHost: 127.0.0.1:{srv.port}\r\nX-MyDownloads: 1\r\nContent-Type: application/json\r\nContent-Length: 999999\r\n\r\n").encode())
    assert s.recv(200).startswith(b"HTTP/1.1 413")
    s.close()


def test_a_body_that_is_not_json_is_a_plain_error(srv):
    c = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=10)
    c.request("POST", "/api/plan", body="{nope", headers={"Host": f"127.0.0.1:{srv.port}", "X-MyDownloads": "1"})
    r = c.getresponse()
    assert r.status == 400 and "error" in js(r.read())


# ---- what it serves
def test_the_page_and_its_files_are_served_with_safe_headers(srv):
    st, h, d = call(srv, "GET", "/")
    assert st == 200 and b"<title>Downloads</title>" in d and h["content-type"].startswith("text/html")
    assert "default-src 'self'" in h["content-security-policy"] and "frame-ancestors 'none'" in h["content-security-policy"]
    assert h["x-content-type-options"] == "nosniff" and h["cache-control"] == "no-store"
    assert call(srv, "GET", "/app.js")[1]["content-type"].startswith("application/javascript")
    assert call(srv, "GET", "/style.css")[1]["content-type"].startswith("text/css")
    assert call(srv, "GET", "/geist.woff2")[1]["content-type"] == "font/woff2"


@pytest.mark.parametrize("path", ["/../secret.txt", "/web/index.html", "/secret.txt", "/%2e%2e/secret.txt", "/app.js/../../secret.txt", "/index.html", "/nope", "/api/nope"])
def test_only_listed_files_are_served(srv, path):
    st, _, d = call(srv, "GET", path)
    assert st == 404 and b"not for the web" not in d


def test_healthz(srv):
    assert call(srv, "GET", "/healthz")[2] == b"ok"


# ---- state and finding
def test_state_at_the_start(srv):
    j = js(call(srv, "GET", "/api/state")[2])
    assert j["folder"] == str(store.folder()) and j["channels"] == [] and j["job"] is None and j["address"].startswith("http://127.0.0.1:")
    assert j["folder_exists"] is False and j["free_gb"] > 0


def test_plan_reads_the_words_and_returns_the_list(srv):
    st, _, d = call(srv, "POST", "/api/plan", {"text": "download my last 5 videos about Cambyses", "channel": CID})
    j = js(d)
    assert st == 200 and j["summary"] == "The 5 newest of your videos about “cambyses”" and j["items"][0]["id"] == VID
    assert j["intent"] == {"count": 5, "order": "newest", "kind": "any", "keywords": ["cambyses"], "urls": []}
    assert srv.eng.last[1] == CID


def test_plan_needs_some_words(srv):
    st, _, d = call(srv, "POST", "/api/plan", {"text": "   "})
    assert st == 400 and "Tell me" in js(d)["error"]


def test_plan_trouble_is_said_in_plain_words(srv):
    srv.eng.explode = True
    st, _, d = call(srv, "POST", "/api/plan", {"text": "my last 3 videos"})
    assert st == 502 and "internet" in js(d)["error"].lower()


# ---- downloading
def test_find_then_download_saves_the_video_in_the_folder(srv):
    st, _, d = call(srv, "POST", "/api/download", {"items": [{"id": VID, "title": "T", "kind": "long"}]})
    assert st == 200 and js(d)["state"] in ("running", "done")
    job = wait_for_job(srv)
    assert job["state"] == "done" and job["items"][0]["status"] == "done"
    assert (srv.tmp / "Downloads" / "C" / f"T [{VID}].mp4").read_bytes() == b"x" * 100


def test_a_bad_id_is_refused(srv):
    st, _, d = call(srv, "POST", "/api/download", {"items": [{"id": "../../etc/passwd", "title": "x"}]})
    assert st == 400 and "error" in js(d)


def test_a_second_job_while_one_runs_is_refused(srv):
    srv.eng.gate = threading.Event()
    assert call(srv, "POST", "/api/download", {"items": [{"id": VID, "title": "T"}]})[0] == 200
    st, _, d = call(srv, "POST", "/api/download", {"items": [{"id": "v0000000002", "title": "U"}]})
    assert st == 409 and "already running" in js(d)["error"]
    srv.eng.gate.set()
    wait_for_job(srv)


def test_stop_and_continue_answer_plainly(srv):
    assert call(srv, "POST", "/api/stop", {})[0] == 200
    st, _, d = call(srv, "POST", "/api/resume", {})
    assert st == 400 and "nothing to continue" in js(d)["error"].lower()


# ---- the list of my channels
def test_adding_a_channel_needs_the_owner_to_say_it_is_theirs(srv):
    st, _, d = call(srv, "POST", "/api/channels", {"text": "@mine", "confirm": False})
    assert st == 400 and "tick" in js(d)["error"].lower() and store.channels() == []


def test_adding_a_channel_with_the_statement_saves_it_and_logs_how(srv):
    st, _, d = call(srv, "POST", "/api/channels", {"text": "@mine", "confirm": True})
    assert st == 200 and [c["id"] for c in js(d)["channels"]] == [CID]
    assert "your statement" in store.channels()[0]["how"]


def test_a_channel_that_cannot_be_found_is_a_plain_error(srv):
    st, _, d = call(srv, "POST", "/api/channels", {"text": "@nobody", "confirm": True})
    assert st == 400 and "could not find" in js(d)["error"] and store.channels() == []


def test_removing_a_channel(srv):
    store.add_channel(CID, "T", "@t", "test")
    assert js(call(srv, "POST", "/api/channels/remove", {"id": CID})[2])["removed"] is True
    assert js(call(srv, "POST", "/api/channels/remove", {"id": CID})[2])["removed"] is False


# ---- the folder
def test_open_folder_creates_it_and_opens_only_that_folder(srv):
    st, _, _ = call(srv, "POST", "/api/open-folder", {"path": "/etc"})
    assert st == 200 and srv.opened == [store.folder()] and store.folder().is_dir()
