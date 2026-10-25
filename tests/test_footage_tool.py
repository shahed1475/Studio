import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

import pytest
import requests

import assetledger
import config
import footagestore
from tools.footage import clipgen

MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64
CREDITS = {"data": {"total_credits": 10, "total_usage": 1}}
MODELS = {"data": [{"id": "google/veo-3.1-lite", "pricing_skus": {"per-video-second": "0.03"}}]}


class Resp:
    def __init__(self, status=200, data=None, content=b"", text="", headers=None):
        self.status_code, self._d, self.content, self.headers = status, data, content, headers or {}
        self.text = text or json.dumps(data)

    def json(self):
        if self._d is None:
            raise ValueError("no json")
        return self._d


class Http:
    """Fake requests. `credits`: replies for /credits (the last repeats). `polls`: statuses or whole replies (the last repeats). `content`: a reply, or a list of replies."""

    def __init__(self, credits=None, submit=None, polls=("completed",), content=None, models=None):
        self.models = models or Resp(data=MODELS)
        self.credits = credits or [Resp(data=CREDITS), Resp(data={"data": {"total_credits": 10, "total_usage": 1.24}})]
        self.submit = submit or Resp(data={"id": "job1"})
        self.polls, self.contents, self.calls = list(polls), content if isinstance(content, list) else [content or Resp(content=MP4)], []

    def _next(self, items):
        return items.pop(0) if len(items) > 1 else items[0]

    def get(self, url, **kw):
        self.calls.append(("GET", url))
        if url.endswith("/videos/models"):
            return self.models
        if url.endswith("/credits"):
            item = self._next(self.credits)
        elif url.endswith("/content"):
            item = self._next(self.contents)
        else:
            item = self._next(self.polls)
            item = item if isinstance(item, (Resp, BaseException)) else Resp(data={"status": item})
        if isinstance(item, BaseException):
            raise item
        return item

    def post(self, url, **kw):
        self.calls.append(("POST", url, kw.get("json")))
        if isinstance(self.submit, Exception):
            raise self.submit
        return self.submit


@pytest.fixture(autouse=True)
def money(tmp_path, monkeypatch):
    """Costs go to throwaway usage and cost files (the studio's daily cap is $1.50), runs go to a throwaway store, and ffmpeg is faked."""
    import llm

    (tmp_path / "data").mkdir()
    monkeypatch.setattr(llm, "USAGE_FILE", tmp_path / "data" / "llm_usage.json")
    monkeypatch.setattr(llm, "_costs_file", lambda: tmp_path / "data" / "video_costs.json")
    monkeypatch.setattr(llm, "CONFIG_FILE", tmp_path / "llm.json")
    (tmp_path / "llm.json").write_text(json.dumps({"daily_budget_usd": 1.5}))
    monkeypatch.setattr(footagestore, "ROOT", tmp_path / "store")
    monkeypatch.setattr(clipgen, "_decode_check", lambda path, cfg: None)
    monkeypatch.setattr(clipgen, "_probe_check", lambda path, cfg: {"width": 1280, "height": 720, "duration_s": 8.0})
    monkeypatch.setattr(clipgen, "_make_picture", lambda path, out, vf, cfg, extra=(): bool(out.write_bytes(b"jpg")))
    return llm


@pytest.fixture
def cfg():
    return clipgen.load_config(config.ROOT / "config" / "footage.json")


def run(cfg, http, prompt="a lantern", sleeps=None):
    r = footagestore.create("footage-test")
    out = clipgen.generate(cfg, "k", prompt, r, http=http, sleep=(sleeps.append if sleeps is not None else lambda s: None), today="2026-10-25")
    return out, r


def fails(cfg, http, match, **kw):
    r = footagestore.create("footage-test")
    with pytest.raises(clipgen.ClipError, match=match):
        clipgen.generate(cfg, kw.get("key", "k"), kw.get("prompt", "a lantern"), r, http=http, sleep=lambda s: None, today="2026-10-25")
    return r


def post_count(http):
    return len([c for c in http.calls if c[0] == "POST"])


# ---- the good run ----
def test_ok_writes_clip_ledger_pictures_and_a_done_record(cfg):
    res, r = run(cfg, Http(polls=["pending", "completed"]))
    rec = r.read()
    assert rec["status"] == "done" and rec["decision"] == "used" and rec["cost_booked"] == 0.24 and rec["job"] == "job1"
    assert set(rec["files"]) == {"log", "clip", "ledger", "contact", "thumb"}
    clip = r.dir / rec["files"]["clip"]
    assert clip.read_bytes() == MP4 and Path(res["clip"]) == clip.resolve()
    row = json.loads((r.dir / rec["files"]["ledger"]).read_text())
    now = hashlib.sha256(clip.read_bytes()).hexdigest()  # the file as it is now, not the row's own value
    assert assetledger.problems([row], [clip.name], {clip.name: now}) == []
    assert row["licence"] == "ai-generated" and row["author"] == cfg["model"] and row["fetched"] == "2026-10-25" and row["ai_label"] is True
    assert row["prompt_sha256"] == hashlib.sha256(b"a lantern").hexdigest() and row["job"] == "job1"
    assert not list(r.dir.glob("*.part")) and not list(r.dir.glob("*.tmp"))
    log = (r.dir / "run.log").read_text()
    assert "reserved $0.24" in log and "decision=used" in log and "licence=ai-generated" in log


def test_the_original_keyerror_data_is_now_a_clear_error(cfg):
    r = fails(cfg, Http(credits=[Resp(data={"error": {"message": "User not found"}})]), "balance reply not understood")
    assert r.read()["status"] == "failed" and "balance reply" in r.read()["error"]


def test_balance_http_401_and_non_json(cfg):
    fails(cfg, Http(credits=[Resp(401, {"error": "x"})]), "HTTP 401")
    fails(cfg, Http(credits=[Resp(200, None, text="<html>")]), "not understood")


# ---- retries ----
def test_connection_errors_are_retried_with_doubling_waits_then_reported(cfg):
    class Down(Http):
        def get(self, url, **kw):
            raise requests.ConnectionError("down")

    waits = []
    r = footagestore.create("footage-test")
    with pytest.raises(clipgen.ClipError, match="request failed after 4 tries"):
        clipgen.generate(cfg, "k", "p", r, http=Down(), sleep=waits.append)
    assert waits == [2, 4, 8]


def test_a_503_then_success_recovers_on_balance_and_on_polls(cfg):
    res, _ = run(cfg, Http(credits=[Resp(503), Resp(data=CREDITS), Resp(data={"data": {"total_credits": 10, "total_usage": 1.24}})],
                           polls=[Resp(429), requests.ConnectionError("blip"), "completed"]))
    assert res["booked_usd"] == 0.24


def test_a_post_is_never_retried(cfg):
    http = Http(submit=requests.ReadTimeout("slow"))
    fails(cfg, http, "a job may exist")
    assert post_count(http) == 1


# ---- refusals before anything is bought ----
def test_low_balance_makes_no_paid_call_and_is_a_blocked_decision(cfg, money):
    http = Http(credits=[Resp(data={"data": {"total_credits": 3, "total_usage": 1}})])
    r = fails(cfg, http, "under")
    assert post_count(http) == 0 and money.spent_today() == 0.0 and r.read()["decision"] == "blocked"


def test_missing_key_and_empty_prompt_are_refused(cfg):
    fails(cfg, Http(), "no OpenRouter key", key="")
    fails(cfg, Http(), "empty prompt", prompt="  ")


# ---- submit ----
def test_a_refused_submit_releases_the_reserved_cost(cfg, money):
    r = fails(cfg, Http(submit=Resp(400, {"e": 1})), "reserved cost was released")
    assert money.spent_today() == 0.0 and money.video_cost(cfg["cost_scope"]) == 0.0 and r.read()["cost_booked"] == 0.0


@pytest.mark.parametrize("submit", [Resp(500, {"e": 1}), Resp(200, {}), Resp(200, None, text="x"), requests.ReadTimeout("slow")])
def test_an_unclear_submit_keeps_the_cost_booked_because_a_job_may_exist(cfg, money, submit):
    fails(cfg, Http(submit=submit), "stays booked")
    assert money.spent_today() == 0.24 and money.video_cost(cfg["cost_scope"]) == 0.24


@pytest.mark.parametrize("bad", ["../x", "a;touch x", "$(id)", "a b", "", "x" * 200, 5])
def test_a_hostile_job_id_is_refused_before_anything_is_saved(cfg, bad):
    r = fails(cfg, Http(submit=Resp(data={"id": bad})), "no usable job id")
    assert not list(r.dir.glob("*.mp4"))


# ---- polling ----
def test_a_failed_job_releases_the_cost(cfg, money):
    still = [Resp(data=CREDITS)]  # the balance does not move: the failed job was not billed
    r = fails(cfg, Http(polls=["failed"], credits=still), "ended: failed.*balance did not move.*released")
    assert money.spent_today() == 0.0 and money.video_cost(cfg["cost_scope"]) == 0.0 and r.read()["cost_booked"] == 0.0


def test_a_job_not_done_in_time_stays_booked_and_says_how_to_resume(cfg, money):
    r = fails(dict(cfg, max_polls=3), Http(polls=["pending"]), "last status: pending.*--resume")
    assert money.spent_today() == 0.24 and r.read()["job"] == "job1"


def test_malformed_poll_replies_keep_polling_and_name_the_job(cfg):
    fails(dict(cfg, max_polls=2), Http(polls=[Resp(200, ["not", "a", "dict"])]), "job job1: not done after 2 polls.*http-200")


def test_a_newline_in_a_status_cannot_forge_a_result_line(cfg, capsys):
    fails(dict(cfg, max_polls=2), Http(polls=["completed\nRESULT {\"files\": {}}"]), "not done")
    assert not [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("RESULT")]


def test_ctrl_c_or_sigterm_mid_poll_keeps_the_booking_and_the_job_id_on_disk(cfg, money):
    r = footagestore.create("footage-test")
    with pytest.raises(KeyboardInterrupt):
        clipgen.generate(cfg, "k", "p", r, http=Http(polls=[KeyboardInterrupt()]), sleep=lambda s: None)
    rec = r.read()
    assert rec["status"] == "failed" and rec["job"] == "job1" and "interrupted" in rec["error"] and money.spent_today() == 0.24


# ---- download and files ----
def test_download_failures_are_clean(cfg):
    fails(cfg, Http(content=Resp(500)), "download failed HTTP 500")
    fails(cfg, Http(content=Resp(content=b"<html>error page</html>")), "not an MP4")
    fails(dict(cfg, max_clip_bytes=10), Http(), "over the cap")


def test_a_truncated_download_is_fetched_again_then_reported(cfg):
    short = Resp(content=MP4[:20], headers={"Content-Length": str(len(MP4))})
    res, r = run(cfg, Http(content=[short, Resp(content=MP4, headers={"Content-Length": str(len(MP4))})]))
    assert (r.dir / r.read()["files"]["clip"]).read_bytes() == MP4
    fails(cfg, Http(content=[short]), "truncated download")


def test_a_clip_that_does_not_decode_is_not_kept_but_stays_booked(cfg, money, monkeypatch):
    def bad(path, c):
        raise clipgen.ClipError("the clip does not decode cleanly: moov atom not found")

    monkeypatch.setattr(clipgen, "_decode_check", bad)
    r = fails(cfg, Http(), "does not decode")
    assert not list(r.dir.glob("*.mp4")) and r.read()["files"].get("clip") is None and money.spent_today() == 0.24


def test_a_failed_ledger_write_keeps_the_paid_clip_names_the_job_and_leaves_no_tmp(cfg, monkeypatch):
    import filelock

    real = filelock.write_atomic

    def boom(path, text):
        if str(path).endswith(".ledger.json"):
            Path(str(path) + ".tmp").write_text("half")
            raise OSError("disk full")
        return real(path, text)

    monkeypatch.setattr(filelock, "write_atomic", boom)
    r = fails(cfg, Http(), "job job1.*cannot save the ledger row.*clip is kept")
    assert (r.dir / "job1.mp4").exists() and not list(r.dir.glob("*.ledger.json*"))


def test_the_pictures_are_optional(cfg, monkeypatch):
    monkeypatch.setattr(clipgen, "_make_picture", lambda *a, **k: False)
    res, r = run(cfg, Http())
    assert r.read()["status"] == "done" and "contact" not in r.read()["files"] and "contact picture could not be made" in (r.dir / "run.log").read_text()


def test_ffmpeg_helpers_report_failures(cfg, tmp_path, monkeypatch):
    clip = tmp_path / "c.mp4"
    clip.write_bytes(MP4)
    monkeypatch.undo()  # the autouse fakes are removed here: these tests exercise the real functions with a fake subprocess

    def fake(result):
        def _run(args, **kw):
            if isinstance(result, Exception):
                raise result
            return result
        return _run

    for result, match in ((subprocess.CompletedProcess([], 1, "", "moov atom not found"), "does not decode"), (subprocess.CompletedProcess([], 0, "", "warning x"), "does not decode"),
                          (FileNotFoundError(), "ffmpeg is missing"), (subprocess.TimeoutExpired("ffmpeg", 1), "timed out")):
        monkeypatch.setattr(subprocess, "run", fake(result))
        with pytest.raises(clipgen.ClipError, match=match):
            clipgen._decode_check(clip, cfg)
    monkeypatch.setattr(subprocess, "run", fake(subprocess.CompletedProcess([], 0, "", "")))
    clipgen._decode_check(clip, cfg)
    monkeypatch.setattr(subprocess, "run", fake(FileNotFoundError()))
    assert clipgen._make_picture(clip, tmp_path / "o.jpg", "scale=1:1", cfg) is False


# ---- money ----
def test_a_clip_cost_lands_in_the_day_total_and_in_video_costs(cfg, tmp_path, money):
    res, _ = run(cfg, Http())
    assert res["booked_usd"] == 0.24 and money.spent_today() == 0.24 and money.video_cost(cfg["cost_scope"]) == 0.24
    assert json.loads((tmp_path / "data" / "video_costs.json").read_text()) == {cfg["cost_scope"]: 0.24}


def test_the_daily_guard_blocks_the_clip_that_would_go_over_the_cap_and_buys_nothing(cfg, money):
    for _ in range(6):  # 6 x 0.24 = 1.44, inside the 1.50 cap
        run(cfg, Http())
    assert money.spent_today() == 1.44
    http = Http()
    r = fails(cfg, http, "daily cap")
    assert http.calls == [] and money.spent_today() == 1.44 and r.read()["decision"] == "blocked"


def test_two_runs_at_once_cannot_both_slip_under_the_cap(cfg, money, monkeypatch):
    monkeypatch.setattr(clipgen, "check_daily_cap", lambda c: None)  # both passed the early check; the other run has already booked
    money.record(money._now(), "footage", "x", 0, 0, 1.4)
    http = Http()
    fails(cfg, http, "would take today's spend over")
    assert money.spent_today() == 1.4 and post_count(http) == 0  # the reservation was given back


def test_a_clip_dearer_than_the_per_clip_cap_is_refused_at_load(cfg, tmp_path):
    (tmp_path / "c.json").write_text(json.dumps(dict(cfg, price_per_second_usd=0.5)))
    with pytest.raises(clipgen.ClipError, match="per-clip cap"):
        clipgen.load_config(tmp_path / "c.json")


def test_a_booking_failure_stops_the_run_before_any_paid_call(cfg, tmp_path, money):
    money.USAGE_FILE.write_text("{ not json")
    http = Http()
    fails(cfg, http, "cannot read today's spend|cannot record the cost|cannot read the studio")
    assert post_count(http) == 0


def test_a_balance_drop_far_above_the_booking_is_booked_in_full_up_to_the_clip_cap(cfg, money):
    big = Http(credits=[Resp(data=CREDITS), Resp(data={"data": {"total_credits": 10, "total_usage": 2.0}})])
    res, r = run(cfg, big)
    assert res["measured_cost"] == 1.0 and res["booked_usd"] == 1.0 and r.read()["cost_booked"] == 1.0
    assert money.spent_today() == 1.0 and money.video_cost("footage-test") == 1.0 and "booked $0.76 more" in (r.dir / "run.log").read_text()
    huge = Http(credits=[Resp(data=CREDITS), Resp(data={"data": {"total_credits": 10, "total_usage": 6.0}})])
    res2, _ = run(cfg, huge)
    assert res2["booked_usd"] == cfg["max_clip_cost_usd"]  # never more than the per-clip cap, whatever else spent


# ---- resume ----
def test_resume_fetches_a_paid_job_and_books_nothing_new(cfg, money):
    r = fails(dict(cfg, max_polls=1), Http(polls=["pending"]), "not done")
    assert money.spent_today() == 0.24
    out = clipgen.resume(cfg, "k", r, http=Http(), sleep=lambda s: None)
    assert r.read()["status"] == "done" and Path(out["clip"]).exists() and money.spent_today() == 0.24
    with pytest.raises(clipgen.ClipError, match="no job to resume"):
        clipgen.resume(cfg, "k", footagestore.create("footage-test"))


# ---- config ----
@pytest.mark.parametrize("change,match", [({"duration_s": "8"}, "positive number"), ({"price_per_second_usd": 0}, "positive number"), ({"retries": -1}, "positive number"),
                                           ({"base_url": "http://example.test"}, "https"), ({"model": " "}, "non-empty"), ({"generate_audio": "no"}, "true or false"),
                                           ({"cost_scope": "../x"}, "plain word"), ({"success_statuses": "completed"}, "list of texts"), ({"duration_s": 30}, "over the cap")])
def test_config_checks(cfg, tmp_path, change, match):
    (tmp_path / "c.json").write_text(json.dumps({**cfg, **change}))
    with pytest.raises(clipgen.ClipError, match=match):
        clipgen.load_config(tmp_path / "c.json")


def test_config_missing_unreadable_or_not_an_object(cfg, tmp_path):
    (tmp_path / "d.json").write_text(json.dumps({"model": "x"}))
    (tmp_path / "e.json").write_text("[1]")
    for name, match in (("d.json", "lacks"), ("missing.json", "cannot read"), ("e.json", "not a settings object")):
        with pytest.raises(clipgen.ClipError, match=match):
            clipgen.load_config(tmp_path / name)


def test_request_body_comes_from_the_config(cfg):
    http = Http()
    run(cfg, http)
    body = [c for c in http.calls if c[0] == "POST"][0][2]
    assert body["model"] == cfg["model"] and body["duration"] == cfg["duration_s"] and body["generate_audio"] is False


# ---- main ----
def test_main_prints_failed_and_returns_1_without_a_key(monkeypatch, capsys):
    import llm

    monkeypatch.setattr(llm, "api_key", lambda: "")
    monkeypatch.setenv("FOOTAGE_CONFIG", str(config.ROOT / "config" / "footage.json"))
    assert clipgen.main([]) == 1
    assert "no OpenRouter key" in capsys.readouterr().err
    assert footagestore.runs()[0]["status"] == "failed" and footagestore.runs()[0]["decision"] == "blocked"


def test_main_prints_one_result_line_with_the_run_files(monkeypatch, capsys):
    import llm

    monkeypatch.setattr(llm, "api_key", lambda: "k")
    monkeypatch.setenv("FOOTAGE_CONFIG", str(config.ROOT / "config" / "footage.json"))
    http = Http()
    monkeypatch.setattr(clipgen, "requests", type("R", (), {"get": http.get, "post": http.post, "RequestException": requests.RequestException}))
    monkeypatch.setattr(clipgen.generate, "__defaults__", (http, lambda s: None, None))
    assert clipgen.main(["a lantern"]) == 0
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("RESULT ")]
    assert len(lines) == 1
    res = json.loads(lines[0][7:])
    assert set(res["files"]) >= {"clip", "ledger", "log"} and res["scope"] == "footage-test" and res["files"]["clip"].endswith("job1.mp4")


# ---- code hygiene ----
def test_no_secret_model_name_url_or_host_in_the_tool_code():
    pat = re.compile(r"(sk-[A-Za-z0-9]{16,}|gpt-\d|claude-(?:opus|sonnet|haiku|fable)|gemini-\d|veo-|https?://|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|@[a-z0-9.-]+\.[a-z]{2,}|/home/|id_ed25519)", re.I)
    for f in (config.ROOT / "tools" / "footage").glob("*"):
        if f.suffix in (".py", ".sh"):
            assert not pat.search(f.read_text()), f.name


def test_the_key_is_only_read_through_llm_api_key():
    text = (config.ROOT / "tools" / "footage" / "clipgen.py").read_text()
    assert text.count("api_key()") == 2 and "getenv" not in text and "environ[" not in text.replace("os.environ.get", "")


# ---- the runner ----
RUNNER = str(config.ROOT / "tools" / "footage" / "run_remote.sh")
STORE = "/app/data/footage/footage-test/20261025T101500Z-abc123"


def sh(env):
    return subprocess.run(["bash", RUNNER], env={"PATH": os.environ["PATH"], **env}, capture_output=True, text=True)


def test_runner_needs_its_settings_and_only_runs_allowed_test_containers():
    assert sh({}).returncode != 0
    assert sh({"FOOTAGE_SSH_TARGET": "u@h"}).returncode != 0
    for name in ("studio-worker", "studio-studio-worker-1", "studio-test-worker;id"):
        r = sh({"FOOTAGE_SSH_TARGET": "u@h", "FOOTAGE_CONTAINER": name})
        assert r.returncode == 2 and ("not an allowed test container" in r.stdout or "bad container name" in r.stdout), name
    # the allowlist is in config/footage.json: an environment variable cannot widen it
    r = sh({"FOOTAGE_SSH_TARGET": "u@h", "FOOTAGE_CONTAINER": "studio-worker", "FOOTAGE_ALLOWED_CONTAINERS": "studio-worker"})
    assert r.returncode == 2 and "not an allowed test container" in r.stdout
    assert sh({"FOOTAGE_SSH_TARGET": "-oProxyCommand=x", "FOOTAGE_CONTAINER": "studio-test-worker"}).returncode == 2


@pytest.fixture
def fakes(tmp_path):
    srv = tmp_path / "srv"
    srv.mkdir()
    (srv / "job1.mp4").write_bytes(MP4)
    (srv / "job1.ledger.json").write_text(json.dumps({"sha256": hashlib.sha256(MP4).hexdigest()}))
    (srv / "run.log").write_text("x")
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    (bin_ / "ssh").write_text('#!/usr/bin/env bash\ncase "$*" in *"python3 -"*) cat >/dev/null; if [ -n "${FAKE_SSH_FAIL:-}" ]; then echo "job: abc123 (paid from here on)"; exit 255; fi; echo "RESULT $FAKE_RESULT";; esac\nexit 0\n')
    (bin_ / "scp").write_text('#!/usr/bin/env bash\ncp "$FAKE_SRV/$(basename "${@: -2:1}")" "${@: -1}"\n')
    for f in bin_.iterdir():
        f.chmod(0o755)
    env = {"PATH": f"{bin_}:{os.environ['PATH']}", "FOOTAGE_SSH_TARGET": "u@h", "FOOTAGE_CONTAINER": "studio-test-worker", "FAKE_SRV": str(srv), "FOOTAGE_LOCAL_OUT": str(tmp_path / "got")}
    return srv, env


def result(**files):
    base = {"clip": f"{STORE}/job1.mp4", "ledger": f"{STORE}/job1.ledger.json", "log": f"{STORE}/run.log"}
    return json.dumps({"files": {**base, **files}})


def go(env, res):
    return subprocess.run(["bash", RUNNER], env={**env, "FAKE_RESULT": res}, capture_output=True, text=True)


def test_runner_copies_checks_the_hash_and_keeps_the_container_files(fakes):
    srv, env = fakes
    r = go(env, result())
    assert r.returncode == 0 and "hash matches" in r.stdout, r.stdout + r.stderr
    assert (Path(env["FOOTAGE_LOCAL_OUT"]) / "job1.mp4").read_bytes() == MP4
    (srv / "job1.mp4").write_bytes(MP4 + b"tampered")
    r = go(env, result())
    assert r.returncode == 1 and "HASH MISMATCH" in r.stdout


@pytest.mark.parametrize("evil", ["/app/settings.json", f"{STORE}/x;touch y", "/app/data/footage/../../settings.json", "/app/data/footage/a/b/../../../../x", "/etc/passwd"])
def test_runner_refuses_a_path_outside_the_footage_store(fakes, evil):
    _, env = fakes
    r = go(env, result(clip=evil))
    assert r.returncode == 1 and "outside the footage store" in r.stdout


def test_runner_explains_an_ssh_drop_after_a_paid_job_was_sent(fakes):
    _, env = fakes
    r = subprocess.run(["bash", RUNNER], env={**env, "FAKE_SSH_FAIL": "1"}, capture_output=True, text=True)
    assert r.returncode == 1 and "no RESULT line (ssh exit 255)" in r.stdout and "job: abc123" in r.stdout and "python3 - --resume <scope> <run_id>" in r.stdout and "ssh -i " not in r.stdout and "ssh " in r.stdout and "/clipgen.py" in r.stdout


def test_runner_needs_clip_and_ledger_in_the_result(fakes):
    _, env = fakes
    r = go(env, json.dumps({"files": {"log": f"{STORE}/run.log"}}))
    assert r.returncode == 1 and "lists no clip file" in r.stdout


# ---- second review: the findings ----
def test_resume_of_a_job_the_provider_failed_gives_the_money_back(cfg, money):
    r = fails(dict(cfg, max_polls=1), Http(polls=["pending"]), "not done")
    assert money.spent_today() == 0.24
    with pytest.raises(clipgen.ClipError, match="reserved cost was released"):
        clipgen.resume(cfg, "k", r, http=Http(polls=["failed"]), sleep=lambda s: None)
    assert money.spent_today() == 0 and r.read()["status"] == "failed" and r.read()["cost_booked"] == 0.0
    with pytest.raises(clipgen.ClipError):  # a second resume cannot give it back twice
        clipgen.resume(cfg, "k", r, http=Http(polls=["failed"]), sleep=lambda s: None)
    assert money.spent_today() == 0


def test_resume_with_a_full_disk_or_an_unexpected_error_leaves_a_failed_record(cfg, monkeypatch):
    r = fails(dict(cfg, max_polls=1), Http(polls=["pending"]), "not done")
    monkeypatch.setattr(clipgen, "_decode_check", lambda p, c: (_ for _ in ()).throw(OSError(28, "No space left on device")))
    with pytest.raises(clipgen.ClipError, match="unexpected OSError"):
        clipgen.resume(cfg, "k", r, http=Http(), sleep=lambda s: None)
    assert r.read()["status"] == "failed" and "No space" in r.read()["error"]


def test_an_unexpected_error_after_the_job_is_sent_marks_the_run_failed_and_keeps_the_cost(cfg, money, monkeypatch):
    monkeypatch.setattr(clipgen, "_decode_check", lambda p, c: (_ for _ in ()).throw(RuntimeError("boom")))
    r = fails(cfg, Http(), "unexpected RuntimeError")
    assert r.read()["status"] == "failed" and r.read()["job"] == "job1" and "resumed" in r.read()["error"] and money.spent_today() == 0.24


def test_ctrl_c_before_the_submit_gives_the_reserved_cost_back(cfg, money):
    class Boom(Http):
        def post(self, *a, **k):
            raise KeyboardInterrupt
    h = Boom()
    r = footagestore.create("footage-test")
    # the interrupt arrives inside the POST, so a job may exist: the cost must stay booked
    with pytest.raises(KeyboardInterrupt):
        clipgen.generate(cfg, "k", "p", r, http=h, sleep=lambda s: None)
    assert "may exist" in r.read()["error"] and money.spent_today() == 0.24
    # an interrupt after the reservation and before the POST starts: released
    state = {"est": 0.24}
    r2 = footagestore.create("footage-test")
    clipgen._book(cfg, 0.24)
    assert "released" in clipgen._interrupted(cfg, r2, state) and money.spent_today() == 0.24  # one booking given back, the other run's stays


def test_a_big_streamed_clip_stops_at_the_cap_and_a_big_announced_one_is_never_read(cfg):
    class Streamed(Resp):
        read_chunks = 0

        def iter_content(self, chunk_size=0):
            for _ in range(50):  # bounded: with the cap check removed this ends in a clear failure, not a hang
                Streamed.read_chunks += 1
                yield b"x" * (1 << 20)
    small = dict(cfg, max_clip_bytes=3 << 20)
    fails(small, Http(content=Streamed(content=MP4)), "download stopped")
    assert Streamed.read_chunks <= 4
    fails(small, Http(content=Resp(content=MP4, headers={"Content-Length": str(5 << 20)})), "announced as")


def test_the_download_asks_for_the_plain_bytes(cfg):
    seen = []

    class Spy(Http):
        def get(self, url, **kw):
            if url.endswith("/content"):
                seen.append((kw["headers"].get("Accept-Encoding"), kw.get("stream")))
            return super().get(url, **kw)
    run(cfg, Spy())
    assert seen == [("identity", True)]


def test_a_dropped_ssh_pipe_does_not_end_the_wait(cfg, monkeypatch):
    def broken(*a, **k):
        raise BrokenPipeError
    monkeypatch.setattr("builtins.print", broken)
    out, r = run(cfg, Http(polls=["pending", "completed"]))
    assert r.read()["status"] == "done" and Path(out["clip"]).exists()


@pytest.mark.parametrize("w,h,dur,match", [(1280, 720, 8.0, None), (1280, 720, 4.0, "length"), (1920, 1080, 8.0, "height"), (720, 1280, 8.0, "shape")])
def test_the_probe_checks_length_height_and_shape(cfg, tmp_path, monkeypatch, w, h, dur, match):
    monkeypatch.undo()  # the autouse fixture mocks the probe; this test wants the real function with a fake ffprobe
    f = tmp_path / "c.mp4"
    f.write_bytes(MP4)
    out = json.dumps({"streams": [{"width": w, "height": h}], "format": {"duration": str(dur)}})
    monkeypatch.setattr(clipgen.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, out, ""))
    if match:
        with pytest.raises(clipgen.ClipError, match=match):
            clipgen._probe_check(f, cfg)
    else:
        assert clipgen._probe_check(f, cfg) == {"width": w, "height": h, "duration_s": dur}


def test_a_probe_failure_keeps_the_paid_clip_but_does_not_accept_it(cfg, monkeypatch):
    monkeypatch.setattr(clipgen, "_probe_check", lambda p, c: (_ for _ in ()).throw(clipgen.ClipError("the clip is not what was asked for: length 2.0 s")))
    r = fails(cfg, Http(), "not accepted")
    rec = r.read()
    assert rec["files"].get("clip") and "ledger" not in rec["files"] and rec["status"] == "failed"


def test_a_new_paid_run_waits_for_a_run_whose_job_outcome_is_unknown(cfg, monkeypatch, capsys):
    monkeypatch.setenv("FOOTAGE_CONFIG", str(config.ROOT / "config" / "footage.json"))
    import llm
    monkeypatch.setattr(llm, "api_key", lambda: "k")
    http = Http()
    monkeypatch.setattr(clipgen, "requests", type("R", (), {"get": http.get, "post": http.post, "RequestException": requests.RequestException}))
    stuck = footagestore.create("footage-test")
    stuck.update(job="job9", status="running")
    monkeypatch.setattr(clipgen.generate, "__defaults__", (http, lambda s: None, None))  # no real network even if the guard were gone
    assert clipgen.main(["a lantern"]) == 1
    assert "--resume footage-test" in capsys.readouterr().err and post_count(http) == 0
    stuck.update(status="failed")
    monkeypatch.setattr(clipgen.generate, "__defaults__", (http, lambda s: None, None))
    assert clipgen.main(["a lantern"]) == 0


# ---- third check ----
def test_resume_refuses_a_run_that_already_finished(cfg, money):
    out, r = run(cfg, Http())
    assert r.read()["status"] == "done" and money.spent_today() == 0.24
    with pytest.raises(clipgen.ClipError, match="already finished"):
        clipgen.resume(cfg, "k", r, http=Http(polls=["failed"]), sleep=lambda s: None)
    assert r.read()["status"] == "done" and money.spent_today() == 0.24 and Path(out["clip"]).exists()


def test_an_expired_job_is_not_treated_as_not_charged(cfg, money):
    assert "expired" not in cfg["failed_statuses"]
    fails(dict(cfg, max_polls=2), Http(polls=["expired"]), "not done")
    assert money.spent_today() == 0.24  # unknown whether it was charged: the money stays booked


def test_a_release_zeroes_the_record_first_and_restores_it_if_booking_fails(cfg, money, monkeypatch):
    r = footagestore.create("footage-test")
    clipgen._book(cfg, 0.24)
    r.update(cost_booked=0.24)
    seen = []
    real = clipgen._book

    def spy(c, usd, at=None):
        seen.append(r.read()["cost_booked"])
        return real(c, usd, at)
    monkeypatch.setattr(clipgen, "_book", spy)
    clipgen._release(cfg, r)
    assert seen == [0.0] and r.read()["cost_booked"] == 0.0 and money.spent_today() == 0
    monkeypatch.setattr(clipgen, "_book", lambda c, u, at=None: (_ for _ in ()).throw(clipgen.ClipError("disk")))
    r.update(cost_booked=0.24)
    with pytest.raises(clipgen.ClipError):
        clipgen._release(cfg, r)
    assert r.read()["cost_booked"] == 0.24  # nothing was written, so the claim is put back


def test_an_interrupt_right_after_the_booking_still_gives_it_back(cfg, money, monkeypatch):
    state = {}
    orig = clipgen._studio_money
    calls = {"n": 0}

    def boom():
        calls["n"] += 1
        if calls["n"] == 2:  # the call that follows the booking inside reserve()
            raise KeyboardInterrupt
        return orig()
    monkeypatch.setattr(clipgen, "_studio_money", boom)
    with pytest.raises(KeyboardInterrupt):
        clipgen.reserve(cfg, state)
    assert state["est"] == 0.24


# ---- third review: money can only come back once ----
def test_two_claims_of_the_same_booked_cost_get_it_once(cfg):
    r = footagestore.create("footage-test")
    r.update(cost_booked=0.24)
    assert [r.take_cost(), r.take_cost()] == [0.24, 0.0] and r.read()["cost_booked"] == 0.0


def test_a_second_release_of_the_same_run_gives_nothing_back(cfg, money):
    r = footagestore.create("footage-test")
    clipgen._book(cfg, 0.24)
    r.update(cost_booked=0.24)
    clipgen._release(cfg, r)
    clipgen._release(cfg, r)  # the resume that arrives after the run already gave it back
    assert money.spent_today() == 0


def test_a_half_written_booking_is_not_given_back_twice(cfg, money, monkeypatch):
    r = footagestore.create("footage-test")
    clipgen._book(cfg, 0.24)
    r.update(cost_booked=0.24)
    real = money.record

    def half(now, role, model, tin, tout, usd):  # the day total changes, then the cost file fails
        money._save_day(now, lambda day: day.__setitem__("usd", round(day["usd"] + usd, 6)))
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(money, "record", half)
    with pytest.raises(clipgen.ClipError):
        clipgen._release(cfg, r)
    monkeypatch.setattr(money, "record", real)
    assert r.read()["cost_booked"] == 0.0 and money.spent_today() == 0  # kept at 0: no second refund can follow
    clipgen._release(cfg, r)
    assert money.spent_today() == 0


def test_a_failed_resume_after_a_failed_run_refunds_only_once(cfg, money):
    r = fails(dict(cfg, max_polls=1), Http(polls=["pending"]), "not done")
    with pytest.raises(clipgen.ClipError, match="released"):
        clipgen.resume(cfg, "k", r, http=Http(polls=["failed"]), sleep=lambda s: None)
    r.update(status="failed")
    clipgen._release(cfg, r)  # what a run that also saw "failed" would try
    assert money.spent_today() == 0


def test_resume_refuses_a_run_another_process_is_still_working_on(cfg):
    r = fails(dict(cfg, max_polls=1), Http(polls=["pending"]), "not done")
    other = subprocess.Popen(["sleep", "30"])
    try:
        r.update(status="running", pid=other.pid, pid_start=clipgen._proc_start(other.pid))
        with pytest.raises(clipgen.ClipError, match="still going"):
            clipgen.resume(cfg, "k", r, http=Http(), sleep=lambda s: None)
    finally:
        other.kill()
        other.wait()
    r.update(status="running", pid=other.pid, pid_start=clipgen._proc_start(os.getpid()))  # a dead process: the resume may go ahead
    out = clipgen.resume(cfg, "k", r, http=Http(), sleep=lambda s: None)
    assert r.read()["status"] == "done" and Path(out["clip"]).exists()


def test_alive_is_false_for_ourselves_nothing_and_a_dead_pid():
    assert not clipgen._alive(os.getpid()) and not clipgen._alive(None) and not clipgen._alive(True) and not clipgen._alive(-3) and not clipgen._alive("7")


def test_a_refused_reserve_zeroes_the_state_before_giving_back(cfg, money, monkeypatch):
    (money.USAGE_FILE.parent / "llm_usage.json").write_text(json.dumps({clipgen_today(): {"usd": 1.4, "calls": 0, "by_role": {}, "fallbacks": []}}))
    state = {}
    seen = []
    real = clipgen._book

    def spy(c, usd):
        seen.append((usd, state.get("est")))
        return real(c, usd)
    monkeypatch.setattr(clipgen, "_book", spy)
    with pytest.raises(clipgen.Refused):
        clipgen.reserve(cfg, state)
    assert seen[1] == (-0.24, 0)  # while the cost is given back, the state already says 0
    assert state["est"] == 0


def clipgen_today():
    import llm
    return llm._day(llm._now())


def test_a_full_disk_in_resume_leaves_the_money_booked(cfg, money, monkeypatch):
    r = fails(dict(cfg, max_polls=1), Http(polls=["pending"]), "not done")
    monkeypatch.setattr(clipgen, "_decode_check", lambda p, c: (_ for _ in ()).throw(OSError(28, "No space left on device")))
    with pytest.raises(clipgen.ClipError, match="unexpected OSError"):
        clipgen.resume(cfg, "k", r, http=Http(), sleep=lambda s: None)
    assert money.spent_today() == 0.24 and r.read()["cost_booked"] == 0.24  # an unknown failure never gives money back


def test_the_run_id_is_printed_for_the_runner(cfg, capsys):
    out, r = run(cfg, Http())
    assert f"run: footage-test {r.dir.name}" in capsys.readouterr().out


# ---- fourth review ----
def test_a_pid_that_now_belongs_to_another_process_does_not_block_a_resume(cfg):
    r = fails(dict(cfg, max_polls=1), Http(polls=["pending"]), "not done")
    other = subprocess.Popen(["sleep", "30"])
    try:
        r.update(status="running", pid=other.pid, pid_start="1")  # the stored start time is not this process's: the pid was reused
        assert not clipgen._alive(other.pid, "1") and clipgen._alive(other.pid, clipgen._proc_start(other.pid)) and clipgen._alive(other.pid)
        out = clipgen.resume(cfg, "k", r, http=Http(), sleep=lambda s: None)
        assert r.read()["status"] == "done" and Path(out["clip"]).exists()
    finally:
        other.kill()
        other.wait()


def test_force_resumes_a_run_that_looks_alive(cfg):
    r = fails(dict(cfg, max_polls=1), Http(polls=["pending"]), "not done")
    other = subprocess.Popen(["sleep", "30"])
    try:
        r.update(status="running", pid=other.pid, pid_start=clipgen._proc_start(other.pid))
        with pytest.raises(clipgen.ClipError, match="--force"):
            clipgen.resume(cfg, "k", r, http=Http(), sleep=lambda s: None)
        clipgen.resume(cfg, "k", r, http=Http(), sleep=lambda s: None, force=True)
        assert r.read()["status"] == "done"
    finally:
        other.kill()
        other.wait()


def test_main_passes_force_to_resume(cfg, monkeypatch, capsys):
    monkeypatch.setenv("FOOTAGE_CONFIG", str(config.ROOT / "config" / "footage.json"))
    import llm
    monkeypatch.setattr(llm, "api_key", lambda: "k")
    seen = {}
    monkeypatch.setattr(clipgen, "resume", lambda c, k, run, force=False, **kw: seen.setdefault("force", force) and {"clip": "x"} or {"clip": "x"})
    r = footagestore.create("footage-test")
    clipgen.main(["--resume", "--force", "footage-test", r.dir.name])
    assert seen["force"] is True
    assert clipgen.main(["--resume", "footage-test"]) == 1 and "usage" in capsys.readouterr().err


def test_a_failed_spend_read_in_release_claims_nothing(cfg, money, monkeypatch):
    r = footagestore.create("footage-test")
    clipgen._book(cfg, 0.24)
    r.update(cost_booked=0.24)
    monkeypatch.setattr(clipgen, "_spent", lambda c: (_ for _ in ()).throw(clipgen.ClipError("cannot read today's spend")))
    with pytest.raises(clipgen.ClipError):
        clipgen._release(cfg, r)
    assert r.read()["cost_booked"] == 0.24  # still there for a later try


def test_an_interrupt_inside_the_give_back_still_leaves_a_failed_record(cfg, money, monkeypatch):
    class Boom(Http):
        def post(self, *a, **k):
            raise KeyboardInterrupt
    monkeypatch.setattr(clipgen, "_interrupted", lambda c, r, s: (_ for _ in ()).throw(KeyboardInterrupt()))
    r = footagestore.create("footage-test")
    with pytest.raises(KeyboardInterrupt):
        clipgen.generate(cfg, "k", "p", r, http=Boom(), sleep=lambda s: None)
    assert r.read()["status"] == "failed" and "interrupted" in r.read()["error"]


def test_a_refused_submit_does_not_claim_a_job_may_exist(cfg, money):
    http = Http(submit=Resp(status=400, data={"error": "bad"}))
    r = fails(cfg, http, "submit refused HTTP 400.*released")
    assert "may exist" not in r.read()["error"] and money.spent_today() == 0


def test_restore_cost_survives_a_garbage_record_value(cfg):
    r = footagestore.create("footage-test")
    data = r.read()
    data["cost_booked"] = "lots"
    r.record_path.write_text(json.dumps(data))
    r.restore_cost(0.24)
    assert r.read()["cost_booked"] == 0.24


def test_the_runner_hint_quotes_paths_and_ignores_a_hostile_run_line(fakes, tmp_path):
    _, env = fakes
    key = tmp_path / "my key"
    key.write_text("k")
    ssh = (tmp_path / "bin" / "ssh")
    ssh.write_text('#!/usr/bin/env bash\ncase "$*" in *"python3 -"*) cat >/dev/null; echo "run: scope1; touch /tmp/pwned x"; echo "job: abc123 (paid from here on)"; exit 255;; esac\nexit 0\n')
    r = subprocess.run(["bash", RUNNER], env={**env, "FOOTAGE_SSH_KEY": str(key)}, capture_output=True, text=True)
    assert "my\\ key" in r.stdout and "<scope> <run_id>" in r.stdout and "touch" not in r.stdout.split("--resume")[1].split("<")[0]


def test_after_a_refused_submit_the_state_says_nothing_was_sent(cfg, money):
    state = {}
    r = footagestore.create("footage-test")
    with pytest.raises(clipgen.ClipError, match="submit refused"):
        clipgen._generate(cfg, "k", "p", r, Http(submit=Resp(status=400, data={"error": "bad"})), lambda s: None, "2026-10-25", state)
    assert state["posted"] is False and state["est"] == 0
    assert "interrupted before" in clipgen._interrupted(cfg, r, state) or "anything was reserved" in clipgen._interrupted(cfg, r, state)


# ---- plan task A1/A2/A3 (OpenRouter documentation, 25 Oct 2026) ----
def completed(cost):
    return Resp(data={"status": "completed", "usage": {"cost": cost, "is_byok": False}})


def priced(cfg, price):
    return Resp(data={"data": [{"id": cfg["model"], "pricing_skus": {"per-video-second": price}}]})


@pytest.mark.parametrize("charged,booked", [(0.31, 0.31), (9.0, 1.0), (0.10, 0.10)])  # above the estimate, far above (clip cap), below (difference given back)
def test_the_provider_cost_is_booked_instead_of_the_estimate(cfg, money, charged, booked):
    res, r = run(dict(cfg, max_clip_cost_usd=1.0), Http(polls=[completed(charged)]))
    assert res["booked_usd"] == booked and r.read()["cost_booked"] == booked and r.read()["provider_cost"] == charged
    assert money.spent_today() == booked and money.video_cost("footage-test") == booked


@pytest.mark.parametrize("bad", [None, "x", -1, 0, float("nan"), float("inf"), {"a": 1}])
def test_a_missing_or_odd_usage_cost_is_ignored(cfg, money, bad):
    res, r = run(cfg, Http(polls=[Resp(data={"status": "completed", "usage": {"cost": bad}})]))
    assert res["booked_usd"] == 0.24 and "provider_cost" not in r.read() and money.spent_today() == 0.24


def test_usage_cost_reads_only_sane_numbers():
    assert clipgen._usage_cost({"usage": {"cost": "0.5"}}) == 0.5 and clipgen._usage_cost({}) is None and clipgen._usage_cost({"usage": None}) is None


def test_the_live_price_replaces_the_config_price(cfg, money):
    fall = [Resp(data=CREDITS), Resp(data={"data": {"total_credits": 10, "total_usage": 1.16}})]  # the balance falls by 0.16, as the live price says
    res, r = run(cfg, Http(credits=fall, models=priced(cfg, "0.02")))
    assert res["booked_usd"] == 0.16 and "live price $0.0200" in (r.dir / "run.log").read_text()


def test_a_live_price_over_the_clip_cap_buys_nothing(cfg, money):
    h = Http(models=priced(cfg, "0.50"))
    r = fails(cfg, h, "at the live price.*over the per-clip cap")
    assert post_count(h) == 0 and money.spent_today() == 0 and r.read()["decision"] == "blocked"


def test_a_price_for_the_chosen_resolution_wins_over_the_base_price(cfg):
    skus = {"per-video-second": "0.50", "per-video-second-720p": "0.04"}
    assert clipgen.live_price(cfg, {}, Http(models=Resp(data={"data": [{"id": cfg["model"], "pricing_skus": skus}]})), lambda s: None) == 0.04


@pytest.mark.parametrize("models", [Resp(500), Resp(data={"data": []}), Resp(data={"data": [{"id": "google/veo-3.1-lite"}]}),
                                    Resp(data={"data": [{"id": "google/veo-3.1-lite", "pricing_skus": {"per-video-second-1080p": "0.1"}}]}),
                                    Resp(data={"data": [{"id": "google/veo-3.1-lite", "pricing_skus": {"per-video-second": "free"}}]}),
                                    Resp(data={"data": [{"id": "google/veo-3.1-lite", "pricing_skus": {"per-video-second": "0"}}]}), Resp(data={"oops": 1})])
def test_an_unreadable_price_list_fails_closed_with_nothing_bought(cfg, money, models):
    h = Http(models=models)
    r = fails(cfg, h, "nothing was bought")
    assert post_count(h) == 0 and money.spent_today() == 0 and r.read()["cost_booked"] == 0.0


def test_price_source_config_keeps_the_settings_price(cfg, money):
    h = Http(models=Resp(500))
    res, _ = run(dict(cfg, price_source="config"), h)
    assert res["booked_usd"] == 0.24 and not [c for c in h.calls if c[1].endswith("/videos/models")]


def test_a_bad_price_source_is_refused_when_the_settings_load(cfg, tmp_path):
    (tmp_path / "c.json").write_text(json.dumps({**cfg, "price_source": "guess"}))
    with pytest.raises(clipgen.ClipError, match="price_source must be"):
        clipgen.load_config(tmp_path / "c.json")


def test_a_failed_job_whose_balance_fell_stays_booked(cfg, money):
    h = Http(polls=["failed"], credits=[Resp(data=CREDITS), Resp(data={"data": {"total_credits": 10, "total_usage": 1.24}})])
    r = fails(cfg, h, "balance fell to 8.76")
    assert money.spent_today() == 0.24 and r.read()["cost_booked"] == 0.24


def test_a_failed_job_with_an_unreadable_balance_stays_booked(cfg, money):
    h = Http(polls=["failed"], credits=[Resp(data=CREDITS), Resp(500)])
    fails(cfg, h, "could not be read")
    assert money.spent_today() == 0.24


def test_resume_of_a_failed_job_whose_balance_fell_keeps_the_money(cfg, money):
    r = fails(dict(cfg, max_polls=1), Http(polls=["pending"]), "not done")
    drop = Http(polls=["failed"], credits=[Resp(data={"data": {"total_credits": 10, "total_usage": 1.5}})])
    with pytest.raises(clipgen.ClipError, match="stays booked"):
        clipgen.resume(cfg, "k", r, http=drop, sleep=lambda s: None)
    assert money.spent_today() == 0.24 and r.read()["cost_booked"] == 0.24


# ---- independent review (26 Oct): NaN settings, a zero provider cost, a give-back after midnight ----
@pytest.mark.parametrize("key", ["max_clip_cost_usd", "price_per_second_usd", "min_balance", "duration_s"])
@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity"])
def test_nan_and_infinity_in_the_settings_are_refused(tmp_path, key, bad):
    raw = (config.ROOT / "config" / "footage.json").read_text()
    data = json.loads(raw)
    text = json.dumps({**data, key: 0}).replace(f'"{key}": 0', f'"{key}": {bad}')
    p = tmp_path / "f.json"
    p.write_text(text)
    with pytest.raises(clipgen.ClipError, match=key):
        clipgen.load_config(p)


def test_a_zero_provider_cost_is_not_believed():
    assert clipgen._usage_cost({"usage": {"cost": 0}}) is None and clipgen._usage_cost({"usage": {"cost": 0.0}}) is None
    assert clipgen._usage_cost({"usage": {"cost": 0.01}}) == 0.01


def test_a_zero_provider_cost_does_not_wipe_the_booking_when_the_balance_fell(cfg, money):
    h = Http(polls=[completed(0)], credits=[Resp(data=CREDITS), Resp(data={"data": {"total_credits": 10, "total_usage": 1.24}})])
    res, r = run(cfg, h)
    assert money.spent_today() >= 0.24 and res["booked_usd"] >= 0.24 and "provider_cost" not in r.read()


def test_a_nan_balance_is_unreadable_not_zero_spend(cfg):
    h = Http(credits=[Resp(data={"data": {"total_credits": float("nan"), "total_usage": 0}})])
    with pytest.raises(clipgen.ClipError, match="not understood"):
        clipgen.balance(cfg, {}, h, lambda s: None)


def test_a_release_after_midnight_goes_back_to_the_day_that_was_charged(cfg, money, monkeypatch):
    import datetime as dt
    day1 = dt.datetime(2026, 10, 25, 23, 59, 0, tzinfo=dt.timezone.utc)
    day2 = dt.datetime(2026, 10, 26, 0, 1, 0, tzinfo=dt.timezone.utc)
    r = footagestore.create("footage-test")
    r.update(created_at="2026-10-25T23:59:00Z")
    monkeypatch.setattr(money, "_now", lambda: day1)
    clipgen._book(cfg, 0.24)
    r.update(cost_booked=0.24)
    monkeypatch.setattr(money, "_now", lambda: day2)
    clipgen._release(cfg, r)
    assert money.spent_today(day1) == 0.0 and money.spent_today(day2) == 0.0  # the refund cancelled day 1's charge, day 2 was never touched


def test_the_balance_floor_holds_after_the_clip_is_paid(cfg, money):
    low = Http(credits=[Resp(data={"data": {"total_credits": 10, "total_usage": 6.9}})])  # 3.10 left, floor 3.0, clip 0.24 -> 2.86
    r = footagestore.create("footage-test")
    with pytest.raises(clipgen.Refused, match="would be under"):
        clipgen.generate(cfg, "k", "a lantern", r, http=low, sleep=lambda s: None)
    assert not [c for c in low.calls if c[0] == "POST"] and money.spent_today() == 0.0
    ok = Http(polls=[completed(0.24)], credits=[Resp(data={"data": {"total_credits": 10, "total_usage": 6.5}}), Resp(data={"data": {"total_credits": 10, "total_usage": 6.74}})])  # 3.50 -> 3.26
    res, _ = run(cfg, ok)
    assert res["booked_usd"] == 0.24
