"""The "Footage clips" dashboard view: what it shows from a run's own record, what it refuses to serve, and that it sits behind the login."""
import datetime as dt
import http.client
import json
import threading
from http.server import ThreadingHTTPServer

import pytest

import config
import dashboard
import footagestore
import footageview
import llm
import webauth

NOW = dt.datetime(2026, 10, 25, 12, 0, tzinfo=dt.timezone.utc)
LEDGER = {"source": "model output", "author": "a video model", "licence": "AI-generated, labelled", "fetched": "2026-10-25", "sha256": "ab" * 32}


@pytest.fixture(autouse=True)
def stores(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(footagestore, "ROOT", tmp_path / "store")
    monkeypatch.setattr(config, "OUT", tmp_path / "out")
    (tmp_path / "out").mkdir()
    monkeypatch.setattr(llm, "USAGE_FILE", tmp_path / "data" / "llm_usage.json")
    monkeypatch.setattr(llm, "_costs_file", lambda: tmp_path / "data" / "video_costs.json")
    monkeypatch.setattr(llm, "CONFIG_FILE", tmp_path / "llm.json")
    (tmp_path / "llm.json").write_text(json.dumps({"daily_budget_usd": 1.5}))
    return tmp_path


def done_run(scope="footage-test", **fields):
    r = footagestore.create(scope)
    (r.dir / "j1.mp4").write_bytes(b"0123456789")
    (r.dir / "j1.contact.jpg").write_bytes(b"jpg")
    (r.dir / "j1.ledger.json").write_text(json.dumps(LEDGER))
    r.update(status="done", decision="used", reason="fits the scene", cost_booked=0.24, job="j1", model="a-model",
             files={"clip": "j1.mp4", "contact": "j1.contact.jpg", "ledger": "j1.ledger.json"}, **fields)
    return r


def test_build_shows_clip_contact_sheet_ledger_cost_and_money(stores):
    r = done_run()
    for i in range(70):
        r.log(f"line {i}")
    (stores / "data" / "llm_usage.json").write_text(json.dumps({"2026-10-25": {"usd": 0.4}}))
    v = footageview.build(NOW)
    assert v["money"] == {"spent_today": 0.4, "cap": 1.5, "left": 1.1}
    run = v["videos"][0]["runs"][0]
    assert run["status"] == "done" and run["decision"] == "used" and run["reason"] == "fits the scene" and run["cost"] == 0.24
    assert run["clip_url"] == f"/footage/file/footage-test/{r.dir.name}/clip" and run["contact_url"].endswith("/contact") and "thumb_url" not in run
    assert run["ledger"] == LEDGER
    assert run["log"][-1].endswith("line 69") and len(run["log"]) == footageview.LOG_LINES


def test_a_failed_run_shows_its_error_and_no_files(stores):
    r = footagestore.create("footage-test")
    r.update(status="failed", error="the source link did not answer", finished_at="2026-10-25T10:00:00Z")
    run = footageview.build(NOW)["videos"][0]["runs"][0]
    assert run["status"] == "failed" and run["error"] == "the source link did not answer" and run["cost"] == 0.0
    assert run["ledger"] is None and not [k for k in run if k.endswith("_url")]


def test_runs_are_grouped_by_video_with_its_title_and_total_cost(stores):
    d = stores / "out" / "vid-a"
    d.mkdir()
    (d / "meta.json").write_text(json.dumps({"title": "Alpha"}))
    done_run("vid-a")
    done_run("vid-a")
    (stores / "data" / "video_costs.json").write_text(json.dumps({"vid-a": 0.48}))
    v = {x["scope"]: x for x in footageview.build(NOW)["videos"]}
    assert v["vid-a"]["title"] == "Alpha" and v["vid-a"]["total_cost"] == 0.48 and len(v["vid-a"]["runs"]) == 2


def test_a_broken_record_is_skipped_not_fatal(stores):
    done_run()
    bad = footagestore.create("footage-test")
    bad.record_path.write_text("{not json")
    assert len(footageview.build(NOW)["videos"][0]["runs"]) == 1


def test_only_files_the_record_lists_are_served(stores):
    r = done_run()
    (r.dir / "secret.txt").write_text("nope")
    s, rid = "footage-test", r.dir.name
    assert footagestore.file_path(s, rid, "clip").name == "j1.mp4"
    assert footagestore.file_path(s, rid, "thumb") is None  # a kind the record does not list
    assert footagestore.file_path(s, rid, "secret.txt") is None  # not a known kind
    for bad in ("..", "../x", "a/b", ""):
        assert footagestore.file_path(bad, rid, "clip") is None and footagestore.file_path(s, bad, "clip") is None


def test_a_record_that_points_outside_its_folder_is_refused(stores):
    r = done_run()
    outside = stores / "outside.mp4"
    outside.write_bytes(b"x")
    for name in ("../../outside.mp4", str(outside), "sub/j1.mp4"):
        data = r.read()
        data["files"]["clip"] = name
        r.record_path.write_text(json.dumps(data))
        assert footagestore.file_path("footage-test", r.dir.name, "clip") is None
    (r.dir / "link.mp4").symlink_to(outside)
    data = r.read()
    data["files"]["clip"] = "link.mp4"
    r.record_path.write_text(json.dumps(data))
    assert footagestore.file_path("footage-test", r.dir.name, "clip") is None  # a link out of the folder


def test_log_text_is_one_printable_line_and_unknown_values_are_refused(stores):
    r = footagestore.create("footage-test")
    r.log("a\nb\x00c" + "x" * 1000)
    (line,) = footagestore.tail("footage-test", r.dir.name)
    assert "\x00" not in line and len(line) <= footagestore.LOG_LINE_MAX + 40
    with pytest.raises(ValueError):
        r.update(status="weird")
    with pytest.raises(ValueError):
        r.update(files={"../x": "y"})
    with pytest.raises(ValueError):
        footagestore.create("../evil")


# ---- over HTTP ----
@pytest.fixture
def server(stores, monkeypatch):
    monkeypatch.setattr(webauth, "DATA", stores)
    monkeypatch.setattr(webauth, "AUTH_FILE", stores / "auth.json")
    monkeypatch.setattr(webauth, "SECRET_FILE", stores / "auth_secret")
    monkeypatch.setattr(webauth, "SESSIONS_FILE", stores / "sessions.json")
    webauth.LIMITER.fails.clear()
    monkeypatch.setattr("time.sleep", lambda s: None)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), dashboard.H)
    monkeypatch.setattr(dashboard, "PORT", srv.server_address[1])
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address[1]
    srv.shutdown()


def call(port, path, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", port)
    c.request("GET", path, headers={"Host": f"127.0.0.1:{port}", **(headers or {})})
    r = c.getresponse()
    return r.status, dict(r.getheaders()), r.read()


def test_the_pages_need_the_login_and_the_files_come_with_ranges(server):
    r = done_run()
    base = f"/footage/file/footage-test/{r.dir.name}/"
    s, _, body = call(server, "/api/footage")  # no password set yet: open, like the rest of the dashboard
    assert s == 200 and json.loads(body)["videos"][0]["runs"][0]["status"] == "done"
    assert call(server, "/footage")[0] == 200 and b"Footage clips" in call(server, "/footage")[2]
    s, h, body = call(server, base + "clip", {"Range": "bytes=2-5"})
    assert s == 206 and body == b"2345" and h["Content-Type"] == "video/mp4"
    assert call(server, base + "contact")[1]["Content-Type"] == "image/jpeg"
    assert call(server, base + "thumb")[0] == 404 and call(server, base + "nothing")[0] == 404
    assert call(server, f"/footage/file/footage-test/{r.dir.name}/..%2F..%2Fx")[0] == 404
    webauth.set_password("me@gmail.com", "correct horse battery")
    assert call(server, "/footage")[0] == 303
    assert call(server, "/api/footage")[0] == 401
    assert call(server, base + "clip")[0] == 303 and b"0123456789" not in call(server, base + "clip")[2]


def test_a_record_with_missing_or_wrong_fields_cannot_break_the_page(stores):
    done_run()
    bad = footagestore.create("footage-test")
    bad.record_path.write_text(json.dumps({"status": "done", "cost_booked": "lots", "scope": "../x", "run_id": "../y"}))
    runs = footageview.build(NOW)["videos"][0]["runs"]
    assert len(runs) == 2 and {r["cost"] for r in runs} == {0.0, 0.24} and all(r["run_id"] in (bad.dir.name, r["run_id"]) for r in runs)
    assert all(".." not in r["run_id"] for r in runs)


def test_odd_record_shapes_do_not_break_the_page(stores):
    done_run()
    a = footagestore.create("footage-test")
    a.record_path.write_text(json.dumps({"status": "done", "files": "x", "created_at": 5}))
    b = footagestore.create("footage-test")
    b.record_path.write_text(json.dumps({"status": "done", "files": ["a"], "created_at": None, "log": 3}))
    assert len(footageview.build(NOW)["videos"][0]["runs"]) == 3
    assert [r["files"] for r in footagestore.runs() if r["run_id"] in (a.dir.name, b.dir.name)] == [{}, {}]
    assert footagestore.file_path("footage-test", a.dir.name, "clip") is None


def test_range_requests_past_the_end_get_416_and_suffix_ranges_work(server):
    r = done_run()
    url = f"/footage/file/footage-test/{r.dir.name}/clip"
    s, h, _ = call(server, url, {"Range": "bytes=99-"})
    assert s == 416 and h["Content-Range"] == "bytes */10"
    s, h, body = call(server, url, {"Range": "bytes=-3"})
    assert s == 206 and body == b"789" and h["Content-Range"] == "bytes 7-9/10" and h["X-Content-Type-Options"] == "nosniff"
    assert call(server, url, {"Range": "bytes=-"})[0] == 200


def test_the_page_puts_untrusted_text_in_with_textcontent_only():
    html = (config.ROOT / "footage.html").read_text()
    assert "innerHTML" not in html and "insertAdjacentHTML" not in html and "document.write" not in html
