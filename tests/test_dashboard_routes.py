"""Every GET route of the dashboard: it answers (never a 500) with an empty data folder and with a populated one, API routes return JSON, files that do not exist
are a 404, and once a password is set nothing but the health check and the login page opens without it. Outbound network is blocked, so a route that reaches for
Google or OpenRouter fails fast (and must still answer)."""
import http.client
import inspect
import json
import re
import threading
from http.server import ThreadingHTTPServer

import pytest
import requests

import config
import dashboard
import footagestore
import llm
import webauth

PUBLIC = {"/healthz", "/login"}
TENANT_ONLY = {"/api/niche"}  # answers 404 "only in a user studio" in the owner's studio, by design (STUDIO_MODE=tenant switches it on)
SKIPPED = {"/oauth/callback", "/claim"}  # need a Google state / a tenant claim token: covered by their own tests
PREFIX_SAMPLES = {  # one concrete address for each prefix route; none of these files exist
    "/branding/": "/branding/avatar.png", "/captions/": "/captions/none.srt", "/cover/": "/cover/none.jpg", "/footage/file/": "/footage/file/a/b/clip", "/static/": "/static/none.css",
    "/thumb/": "/thumb/none.jpg", "/thumbopt/": "/thumbopt/none.jpg", "/video/": "/video/none.mp4"}


def inventory() -> tuple[list[str], list[str]]:
    """The exact paths and the path prefixes written in do_GET and _get, read from its source so a new route cannot be forgotten."""
    src = inspect.getsource(dashboard.H.do_GET) + inspect.getsource(dashboard.H._get)
    exact = sorted(set(re.findall(r'u\.path == "(/[^"]*)"', src)) - SKIPPED)
    prefixes = sorted(set(re.findall(r'u\.path\.startswith\("(/[^"]*)"\)', src)) - {"/api/"})
    return exact, prefixes


@pytest.fixture
def server(tmp_path, monkeypatch):
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
    webauth.LIMITER.fails.clear()

    def no_network(*a, **k):
        raise requests.ConnectionError("blocked in tests")

    monkeypatch.setattr(requests.sessions.Session, "request", no_network)
    monkeypatch.setattr("time.sleep", lambda s: None)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), dashboard.H)
    monkeypatch.setattr(dashboard, "PORT", srv.server_address[1])
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address[1], tmp_path
    srv.shutdown()


def get(port, path):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    c.request("GET", path, headers={"Host": f"127.0.0.1:{port}"})
    r = c.getresponse()
    return r.status, r.getheader("Content-Type") or "", r.read()


def populate(tmp):
    folder = tmp / "out" / "a-story"
    folder.mkdir()
    (folder / "meta.json").write_text(json.dumps({"title": "A story", "format": "short", "review": {"verdict": "pass"}, "approved": True}))
    (folder / "video.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"0" * 64)
    run = footagestore.create("footage-test")
    run.update(status="done", decision="used", cost_booked=0.24)


def test_the_inventory_finds_the_routes_we_know():
    exact, prefixes = inventory()
    assert {"/", "/now", "/footage", "/channels", "/api/state", "/api/now", "/api/risk", "/api/channels", "/api/footage"} <= set(exact)
    assert set(prefixes) == set(PREFIX_SAMPLES), "a prefix route was added or removed: give it a sample address in PREFIX_SAMPLES"


@pytest.mark.parametrize("populated", [False, True], ids=["empty data", "populated data"])
def test_every_get_route_answers_without_a_server_error(server, populated):
    port, tmp = server
    if populated:
        populate(tmp)
    exact, _ = inventory()
    for path in exact:
        status, ctype, body = get(port, path)
        if path == "/login":  # no password set yet, so the visitor counts as signed in and is sent home
            assert status == 303
            continue
        if path in TENANT_ONLY:
            assert status == 404 and b"only in a user studio" in body
            continue
        assert status == 200, f"{path} answered {status}: {body[:200]!r}"
        if path.startswith("/api/"):
            json.loads(body)  # raises when the answer is not JSON
        elif path != "/healthz":
            assert ctype.startswith("text/html"), f"{path} answered {ctype}"


def test_files_that_do_not_exist_are_a_404_not_a_crash(server):
    port, _ = server
    for sample in PREFIX_SAMPLES.values():
        assert get(port, sample)[0] == (200 if sample.startswith("/branding/") else 404), sample  # the repository ships the channel avatar
    assert get(port, "/video/..%2F..%2Fetc%2Fpasswd")[0] in (400, 404)
    assert get(port, "/api/does-not-exist")[0] == 404


def test_with_a_password_set_only_the_health_check_and_the_login_page_open(server):
    port, _ = server
    webauth.set_password("me@gmail.com", "correct horse battery")
    exact, _ = inventory()
    for path in exact:
        status = get(port, path)[0]
        if path in PUBLIC:
            assert status == 200, path
        else:
            assert status in (303, 401), f"{path} answered {status} without a login"
    for sample in PREFIX_SAMPLES.values():
        assert get(port, sample)[0] in (303, 401, 404) and get(port, sample)[0] != 200, sample


def test_a_missing_page_file_is_a_clean_500(server, monkeypatch):
    port, tmp = server
    monkeypatch.setattr(config, "ROOT", tmp)  # no channels.html here
    assert get(port, "/channels")[0] == 500


def _video_with_pictures(tmp, slug, **meta):
    folder = tmp / "out" / slug
    (folder / "thumbs").mkdir(parents=True)
    (folder / "thumbs" / "cover.jpg").write_bytes(b"\xff\xd8cover")
    (folder / "thumbs" / "new-a.jpg").write_bytes(b"\xff\xd8thumb")
    (folder / "meta.json").write_text(json.dumps({"title": "T", **meta}))


def test_cover_route_shows_a_shorts_vertical_cover_and_a_documentarys_chosen_thumbnail(server):
    port, tmp = server
    _video_with_pictures(tmp, "a-short", format="short", cover="thumbs/cover.jpg")
    _video_with_pictures(tmp, "a-doc", format="doc", thumbnail="thumbs/new-a.jpg")
    assert get(port, "/cover/a-short")[::2] == (200, b"\xff\xd8cover")
    assert get(port, "/cover/a-doc")[::2] == (200, b"\xff\xd8thumb")


def test_cover_route_never_leaves_the_videos_thumbs_folder(server):
    port, tmp = server
    _video_with_pictures(tmp, "evil", format="short", cover="../meta.json")
    (tmp / "secret.txt").write_text("x")
    assert get(port, "/cover/evil")[0] == 404
    assert get(port, "/cover/..%2f..%2fsecret")[0] in (400, 404)
    assert get(port, "/cover/nothing-here")[0] == 404


def test_the_video_list_tells_the_page_which_cover_a_short_has(server):
    port, tmp = server
    _video_with_pictures(tmp, "a-short", format="short", cover="thumbs/cover.jpg")
    status, _, body = get(port, "/api/state")
    assert status == 200 and [v["cover"] for v in json.loads(body)["videos"] if v["slug"] == "a-short"] == ["thumbs/cover.jpg"]
