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
from tools.footage import clipgen

MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64


class Resp:
    def __init__(self, status=200, data=None, content=b"", text=""):
        self.status_code, self._d, self.content, self.text = status, data, content, text or json.dumps(data)

    def json(self):
        if self._d is None:
            raise ValueError("no json")
        return self._d


class Http:
    """Fake requests: `credits` is a list of replies (the last one repeats), `polls` a list of statuses."""

    def __init__(self, credits=None, submit=None, polls=("completed",), content=None):
        self.credits = credits or [Resp(data={"data": {"total_credits": 10, "total_usage": 1}}), Resp(data={"data": {"total_credits": 10, "total_usage": 1.24}})]
        self.submit = submit or Resp(data={"id": "job1"})
        self.polls, self.content, self.calls = list(polls), content or Resp(content=MP4), []

    def get(self, url, **kw):
        self.calls.append(("GET", url))
        if url.endswith("/credits"):
            return self.credits.pop(0) if len(self.credits) > 1 else self.credits[0]
        if url.endswith("/content"):
            return self.content
        return Resp(data={"status": self.polls.pop(0) if len(self.polls) > 1 else self.polls[0]})

    def post(self, url, **kw):
        self.calls.append(("POST", url, kw.get("json")))
        return self.submit


@pytest.fixture(autouse=True)
def money(tmp_path, monkeypatch):
    """Every footage test books its cost into a throwaway usage file and cost file, never the real ones; the daily cap is the studio's $1.50."""
    import llm

    (tmp_path / "data").mkdir()
    monkeypatch.setattr(llm, "USAGE_FILE", tmp_path / "data" / "llm_usage.json")
    monkeypatch.setattr(llm, "_costs_file", lambda: tmp_path / "data" / "video_costs.json")
    monkeypatch.setattr(llm, "CONFIG_FILE", tmp_path / "llm.json")
    (tmp_path / "llm.json").write_text(json.dumps({"daily_budget_usd": 1.5}))
    return llm


@pytest.fixture
def cfg():
    return clipgen.load_config(config.ROOT / "config" / "footage.json")


def run(cfg, tmp_path, http, prompt="a lantern"):
    return clipgen.generate(cfg, "k", prompt, tmp_path / "out", http=http, sleep=lambda s: None, today="2026-10-25")


def test_ok_writes_clip_and_a_valid_ledger_row(cfg, tmp_path):
    res = run(cfg, tmp_path, Http(polls=["pending", "completed"]))
    assert res["cost"] == 0.24 and Path(res["clip"]).read_bytes() == MP4
    row = json.loads(Path(res["ledger"]).read_text())
    assert row["licence"] == "ai-generated" and row["author"] == cfg["model"] and row["fetched"] == "2026-10-25"
    name = Path(res["clip"]).name
    now = hashlib.sha256(Path(res["clip"]).read_bytes()).hexdigest()  # the file as it is now, not the row's own value
    assert assetledger.problems([row], [name], {name: now}) == []
    assert row["ai_label"] is True and row["job"] == "job1" and len(row["prompt_sha256"]) == 64 and Path(res["clip"]).is_absolute()
    assert not list((tmp_path / "out").glob("*.part"))


def test_the_original_keyerror_data_is_now_a_clear_error(cfg, tmp_path):
    with pytest.raises(clipgen.ClipError, match="balance reply not understood"):
        run(cfg, tmp_path, Http(credits=[Resp(data={"error": {"message": "User not found"}})]))


def test_balance_http_401_and_non_json(cfg, tmp_path):
    with pytest.raises(clipgen.ClipError, match="HTTP 401"):
        run(cfg, tmp_path, Http(credits=[Resp(401, {"error": "x"})]))
    with pytest.raises(clipgen.ClipError, match="not understood"):
        run(cfg, tmp_path, Http(credits=[Resp(200, None, text="<html>")]))


def test_balance_network_error_is_wrapped(cfg, tmp_path):
    class Boom(Http):
        def get(self, url, **kw):
            raise requests.ConnectionError("down")

    with pytest.raises(clipgen.ClipError, match="balance check failed"):
        run(cfg, tmp_path, Boom())


def test_low_balance_makes_no_paid_call(cfg, tmp_path):
    http = Http(credits=[Resp(data={"data": {"total_credits": 3, "total_usage": 1}})])
    with pytest.raises(clipgen.ClipError, match="under"):
        run(cfg, tmp_path, http)
    assert not [c for c in http.calls if c[0] == "POST"]


@pytest.mark.parametrize("submit,msg", [(Resp(500, {"e": 1}), "HTTP 500"), (Resp(200, {}), "no usable job id"), (Resp(200, None, text="x"), "no usable job id")])
def test_submit_failures(cfg, tmp_path, submit, msg):
    with pytest.raises(clipgen.ClipError, match=msg):
        run(cfg, tmp_path, Http(submit=submit))


def test_failed_job_and_timeout(cfg, tmp_path):
    with pytest.raises(clipgen.ClipError, match="ended: failed"):
        run(cfg, tmp_path, Http(polls=["failed"]))
    with pytest.raises(clipgen.ClipError, match="may still finish"):
        run(dict(cfg, max_polls=3), tmp_path, Http(polls=["pending"]))


def test_download_failures_leave_no_file(cfg, tmp_path):
    with pytest.raises(clipgen.ClipError, match="download failed HTTP 500"):
        run(cfg, tmp_path, Http(content=Resp(500)))
    with pytest.raises(clipgen.ClipError, match="not an MP4"):
        run(cfg, tmp_path, Http(content=Resp(content=b"<html>error page</html>")))
    with pytest.raises(clipgen.ClipError, match="over the cap"):
        run(dict(cfg, max_clip_bytes=10), tmp_path, Http())
    assert not (tmp_path / "out").exists()  # every check runs before anything is written


def test_unwritable_output_dir_is_a_clean_error_with_the_job_id(cfg, tmp_path):
    (tmp_path / "out").write_text("a file, not a folder")
    with pytest.raises(clipgen.ClipError, match="job job1"):
        run(cfg, tmp_path, Http())


@pytest.mark.parametrize("bad", ["../x", "a;touch x", "$(id)", "a b", "", "x" * 200, 5])
def test_a_hostile_job_id_is_refused_before_anything_is_saved(cfg, tmp_path, bad):
    with pytest.raises(clipgen.ClipError, match="no usable job id"):
        run(cfg, tmp_path, Http(submit=Resp(data={"id": bad})))
    assert not (tmp_path / "out").exists()


def test_malformed_poll_reply_and_poll_network_error_name_the_job(cfg, tmp_path):
    class BadPoll(Http):
        def get(self, url, **kw):
            if "/videos/" in url and not url.endswith("/content"):
                return Resp(200, ["not", "a", "dict"])
            return super().get(url, **kw)

    with pytest.raises(clipgen.ClipError, match="job job1.*not done after"):
        run(dict(cfg, max_polls=2), tmp_path, BadPoll())

    class Down(Http):
        def get(self, url, **kw):
            if "/videos/" in url:
                raise requests.ConnectionError("down")
            return super().get(url, **kw)

    with pytest.raises(clipgen.ClipError, match=r"job job1: request failed.*balance now"):
        run(cfg, tmp_path, Down())


def test_a_failed_ledger_write_keeps_the_paid_clip_and_names_the_job(cfg, tmp_path, monkeypatch):
    real = Path.write_text

    def boom(self, *a, **k):
        if self.name.endswith(".ledger.json"):
            raise OSError("disk full")
        return real(self, *a, **k)

    monkeypatch.setattr(Path, "write_text", boom)
    with pytest.raises(clipgen.ClipError, match="job job1.*clip is kept"):
        run(cfg, tmp_path, Http())
    assert (tmp_path / "out" / "job1.mp4").exists()


def test_cost_is_none_when_the_balance_after_is_unknown(cfg, tmp_path):
    http = Http(credits=[Resp(data={"data": {"total_credits": 10, "total_usage": 1}}), Resp(500, {})])
    res = run(cfg, tmp_path, http)
    assert res["cost"] is None and "unknown" in res["balance_after"]


def test_server_text_in_errors_is_printable_and_short(cfg, tmp_path):
    with pytest.raises(clipgen.ClipError) as e:
        run(cfg, tmp_path, Http(credits=[Resp(500, {}, text="bad\x1b[31m\x00" + "z" * 500)]))
    assert "\x1b" not in str(e.value) and "\x00" not in str(e.value) and len(str(e.value)) < 300


def test_main_prints_failed_and_returns_1(monkeypatch, capsys):
    import llm

    monkeypatch.setattr(llm, "api_key", lambda: "")
    assert clipgen.main([]) == 1 and "no OpenRouter key" in capsys.readouterr().err


def test_caps_and_config_checks(cfg, tmp_path):
    with pytest.raises(clipgen.ClipError, match="over the cap"):
        (tmp_path / "c.json").write_text(json.dumps(dict(cfg, duration_s=30)))
        clipgen.load_config(tmp_path / "c.json")
    (tmp_path / "d.json").write_text(json.dumps({"model": "x"}))
    with pytest.raises(clipgen.ClipError, match="lacks"):
        clipgen.load_config(tmp_path / "d.json")
    with pytest.raises(clipgen.ClipError, match="cannot read"):
        clipgen.load_config(tmp_path / "missing.json")
    with pytest.raises(clipgen.ClipError, match="no OpenRouter key"):
        clipgen.generate(cfg, "", "p", tmp_path, http=Http())


def test_request_body_comes_from_the_config(cfg, tmp_path):
    http = Http()
    run(cfg, tmp_path, http)
    body = [c for c in http.calls if c[0] == "POST"][0][2]
    assert body["model"] == cfg["model"] and body["duration"] == cfg["duration_s"] and body["generate_audio"] is False


def test_nc_nd_and_unknown_licences_block(tmp_path):
    f = tmp_path / "a.mp4"
    f.write_bytes(MP4)
    for lic in ("cc by-nc", "cc by-nd", "unknown", ""):
        r = assetledger.row(f, "u", lic, "2026-10-25", "a")
        assert any("not allowed" in p for p in assetledger.problems([r], ["a.mp4"]))


def test_no_secret_model_name_url_or_host_in_the_tool_code():
    pat = re.compile(r"(sk-[A-Za-z0-9]{16,}|gpt-\d|claude-(?:opus|sonnet|haiku|fable)|gemini-\d|veo-|https?://|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|@[a-z0-9.-]+\.[a-z]{2,}|/home/|id_ed25519)", re.I)
    for f in (config.ROOT / "tools" / "footage").glob("*"):
        if f.suffix in (".py", ".sh"):
            assert not pat.search(f.read_text()), f.name


def sh(env):
    return subprocess.run(["bash", str(config.ROOT / "tools" / "footage" / "run_remote.sh")], env={"PATH": os.environ["PATH"], **env}, capture_output=True, text=True)


def test_runner_needs_its_settings_and_only_runs_allowed_test_containers():
    assert sh({}).returncode != 0
    assert sh({"FOOTAGE_SSH_TARGET": "u@h"}).returncode != 0
    for name in ("studio-worker", "studio-studio-worker-1", "studio-test-worker;id"):
        r = sh({"FOOTAGE_SSH_TARGET": "u@h", "FOOTAGE_CONTAINER": name})
        assert r.returncode == 2 and "not an allowed test container" in r.stdout, name
    r = sh({"FOOTAGE_SSH_TARGET": "u@h", "FOOTAGE_CONTAINER": "studio-worker", "FOOTAGE_OWNER_CONTAINER": "x"})
    assert r.returncode == 2


def test_runner_copies_checks_the_hash_and_refuses_unsafe_paths(tmp_path):
    """ssh and scp are faked on PATH: ssh answers the container step with a RESULT line, scp copies from a fixture folder."""
    srv = tmp_path / "srv"
    srv.mkdir()
    (srv / "job1.mp4").write_bytes(MP4)
    (srv / "job1.ledger.json").write_text(json.dumps({"sha256": hashlib.sha256(MP4).hexdigest()}))
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    (bin_ / "ssh").write_text('#!/usr/bin/env bash\ncat >/dev/null\n[[ "$*" == *"python3 -"* ]] && echo "RESULT $FAKE_RESULT"\nexit 0\n')
    (bin_ / "scp").write_text('#!/usr/bin/env bash\ncp "$FAKE_SRV/$(basename "${@: -2:1}")" "${@: -1}"\n')
    for f in bin_.iterdir():
        f.chmod(0o755)
    base = {"PATH": f"{bin_}:{os.environ['PATH']}", "FOOTAGE_SSH_TARGET": "u@h", "FOOTAGE_CONTAINER": "studio-test-worker",
            "FAKE_SRV": str(srv), "FOOTAGE_LOCAL_OUT": str(tmp_path / "got")}
    script = str(config.ROOT / "tools/footage/run_remote.sh")

    def go(result):
        return subprocess.run(["bash", script], env={**base, "FAKE_RESULT": result}, capture_output=True, text=True)

    good = json.dumps({"clip": "/app/cache/footage/job1.mp4", "ledger": "/app/cache/footage/job1.ledger.json"})
    r = go(good)
    assert r.returncode == 0 and "hash matches" in r.stdout, r.stdout + r.stderr
    (srv / "job1.mp4").write_bytes(MP4 + b"tampered")
    r = go(good)
    assert r.returncode == 1 and "HASH MISMATCH" in r.stdout
    r = go(json.dumps({"clip": "/app/x;touch y", "ledger": "/app/y"}))
    assert r.returncode == 1 and "unsafe path" in r.stdout


def test_a_clip_cost_lands_in_the_day_total_and_in_video_costs(cfg, tmp_path, money):
    res = run(cfg, tmp_path, Http())
    assert res["booked_usd"] == 0.24
    assert money.spent_today() == 0.24
    assert money.video_cost(cfg["cost_scope"]) == 0.24
    assert json.loads((tmp_path / "data" / "video_costs.json").read_text()) == {cfg["cost_scope"]: 0.24}


def test_the_daily_guard_blocks_the_clip_that_would_go_over_the_cap_and_buys_nothing(cfg, tmp_path, money):
    for _ in range(6):  # 6 x 0.24 = 1.44, inside the 1.50 cap
        run(cfg, tmp_path, Http())
    assert money.spent_today() == 1.44
    http = Http()
    with pytest.raises(clipgen.ClipError, match="daily cap"):
        run(cfg, tmp_path, http)  # 1.44 + 0.24 = 1.68 is over
    assert http.calls == []  # not even a balance check: nothing was bought
    assert money.spent_today() == 1.44


def test_a_run_over_the_cap_makes_no_http_call_at_all(cfg, tmp_path, money):
    (tmp_path / "llm.json").write_text(json.dumps({"daily_budget_usd": 0.2}))
    http = Http()
    with pytest.raises(clipgen.ClipError, match="daily cap"):
        run(cfg, tmp_path, http)
    assert http.calls == [] and money.spent_today() == 0.0


def test_a_job_that_may_have_run_is_booked_even_when_a_later_step_fails(cfg, tmp_path, money):
    with pytest.raises(clipgen.ClipError, match="booked"):
        run(cfg, tmp_path, Http(content=Resp(500)))
    assert money.spent_today() == 0.24 and money.video_cost(cfg["cost_scope"]) == 0.24


def test_a_job_the_provider_failed_books_nothing(cfg, tmp_path, money):
    with pytest.raises(clipgen.ClipError, match="booked \\$0.00"):
        run(cfg, tmp_path, Http(polls=["failed"]))
    assert money.spent_today() == 0.0


def test_a_clip_dearer_than_the_per_clip_cap_is_refused_at_load(cfg, tmp_path):
    (tmp_path / "c.json").write_text(json.dumps(dict(cfg, price_per_second_usd=0.5)))
    with pytest.raises(clipgen.ClipError, match="per-clip cap"):
        clipgen.load_config(tmp_path / "c.json")
