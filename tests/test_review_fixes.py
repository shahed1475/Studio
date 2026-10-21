"""Regression tests for the problems the independent review found."""
import datetime as dt
import json
import os
import threading
import time
import types

import agentlog
import clipper
import config
import filelock
import pytest
import strategy
import subtitles
import topicqueue
import tts
import worker

NOW = dt.datetime(2026, 10, 19, 12, 0, tzinfo=dt.timezone.utc)


# ---- topic queue: one locked, atomic place for every writer ----
@pytest.fixture
def queue(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "TOPICS_FILE", tmp_path / "topics.json")
    return tmp_path / "topics.json"


def test_topicqueue_basic_operations(queue):
    assert topicqueue.items() == []
    topicqueue.extend(["a", "b", "a"])
    assert topicqueue.items() == ["a", "b"]  # extend skips what is already queued
    assert topicqueue.pop_first() == "a"
    topicqueue.push_front("z")
    assert topicqueue.items() == ["z", "b"]
    assert topicqueue.append_unique("B") is False and topicqueue.append_unique("c") is True
    assert topicqueue.remove(0) is True and topicqueue.remove(9) is False
    assert topicqueue.items() == ["b", "c"]
    assert topicqueue.pop_first() == "b" and topicqueue.pop_first() == "c" and topicqueue.pop_first() is None


def test_topicqueue_corrupt_file_reads_as_empty_and_never_leaves_a_temp_file(queue):
    queue.write_text("{broken")
    assert topicqueue.items() == []
    topicqueue.extend(["a"])
    assert topicqueue.items() == ["a"] and not list(queue.parent.glob("*.tmp"))


def test_topicqueue_concurrent_writers_lose_nothing(queue):
    def work(n):
        for i in range(10):
            topicqueue.extend([f"t{n}-{i}"])

    threads = [threading.Thread(target=work, args=(n,)) for n in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(topicqueue.items()) == 60


def test_strategy_apply_uses_the_queue_module(queue, tmp_path, monkeypatch):
    monkeypatch.setattr(strategy, "FILE", tmp_path / "strategies.json")
    sid = strategy.add([{"kind": "topic", "text": "The vanishing village", "why": "w", "evidence": []}])[0]["id"]
    strategy.apply(sid)
    assert topicqueue.items() == ["The vanishing village"]


# ---- events: an event written while mark_read runs is not lost ----
def test_event_during_mark_read_is_not_lost(tmp_path, monkeypatch):
    monkeypatch.setattr(agentlog, "FILE", tmp_path / "events.jsonl")
    agentlog.event("info", "first")
    real = agentlog._all
    started = threading.Event()

    def slow_all():
        rows = real()
        started.set()
        time.sleep(0.3)  # the window in which another process appends
        return rows

    monkeypatch.setattr(agentlog, "_all", slow_all)
    t = threading.Thread(target=agentlog.mark_read)
    t.start()
    started.wait()
    agentlog.event("found", "arrived meanwhile")
    t.join()
    monkeypatch.setattr(agentlog, "_all", real)
    assert sorted(e["title"] for e in agentlog.recent()) == ["arrived meanwhile", "first"]


# ---- strategies: two writers at once keep both changes ----
def test_concurrent_strategy_writers_keep_everything(tmp_path, monkeypatch):
    monkeypatch.setattr(strategy, "FILE", tmp_path / "strategies.json")
    monkeypatch.setattr(config, "TOPICS_FILE", tmp_path / "topics.json")

    import hashlib

    def adder(n):
        for i in range(5):
            text = "retell " + hashlib.sha1(f"{n}-{i}".encode()).hexdigest()  # unlike each other: same-idea advice is refused now
            strategy.add([{"kind": "topic", "text": text, "why": "w", "evidence": []}])

    threads = [threading.Thread(target=adder, args=(n,)) for n in range(5)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(strategy.load()) == 25


# ---- clipper must not revert what the owner changed while a Short was rendering ----
def test_clipper_keeps_a_hold_set_during_rendering(tmp_path, monkeypatch):
    from test_clipper import make_doc

    monkeypatch.setattr(config, "OUT", tmp_path)
    make_doc(tmp_path, "doc-a")
    meta = tmp_path / "doc-a" / "meta.json"

    def produce(data, topic, **kw):
        cur = json.loads(meta.read_text())
        cur["hold"] = True  # the owner presses Hold while the Short renders
        meta.write_text(json.dumps(cur))
        return tmp_path / "short"

    clipper.make_next(produce=produce, chat=lambda p: {"hook": "Why?", "title": "T"})
    after = json.loads(meta.read_text())
    assert after["hold"] is True and len(after["clips"]) == 1


def test_clipper_failure_also_keeps_concurrent_changes(tmp_path, monkeypatch):
    from test_clipper import make_doc

    monkeypatch.setattr(config, "OUT", tmp_path)
    make_doc(tmp_path, "doc-a")
    meta = tmp_path / "doc-a" / "meta.json"

    def produce(data, topic, **kw):
        cur = json.loads(meta.read_text())
        cur["approved_by"] = "you"
        meta.write_text(json.dumps(cur))
        raise SystemExit("not enough footage")

    clipper.make_next(produce=produce, chat=lambda p: {"hook": "Why?", "title": "T"})
    after = json.loads(meta.read_text())
    assert after["approved_by"] == "you" and len(after["clips_failed"]) == 2


# ---- captions: braces and backslashes in narration must not open ASS override blocks ----
HOSTILE = [(0.0, 0.4, "He", 0), (0.4, 0.9, "said", 0), (0.9, 1.4, "{\\an9}x", 1), (1.4, 1.9, "back\\slash}", 1), (1.9, 2.4, "ok", 1)]


def test_rich_captions_strip_override_characters_from_words():
    ass = tts._ass(HOSTILE, motion=2)
    for line in ass.splitlines():
        if line.startswith("Dialogue"):
            body = line.split(",", 4)[4]
            visible = body
            import re

            visible = re.sub(r"\{\\[^{}]*\}", "", body)  # remove the tags we add ourselves
            assert "{" not in visible and "}" not in visible and "\\" not in visible.replace("\\N", "")
    assert "AN9" in ass.upper()  # the word survives, only the control characters go


def test_plain_captions_and_documentary_subtitles_strip_them_too():
    assert "{" not in "".join(l for l in tts._ass(HOSTILE, motion=0).splitlines() if l.startswith("Dialogue"))
    cues = [{"start": 0.0, "end": 2.0, "text": "He said {\\an9}hello}\nback\\slash"}]
    body = subtitles.to_ass(cues).splitlines()[-1].split(",", 4)[4]
    import re

    assert "{\\an9}" not in body and "{" not in re.sub(r"\{\\[^{}]*\}", "", body)


# ---- 24/7 housekeeping ----
def test_prune_uploaded_is_off_by_default_and_only_removes_old_uploaded_videos(tmp_path):
    def video(name, uploaded_days_ago, video_id):
        d = tmp_path / name
        d.mkdir()
        (d / "video.mp4").write_bytes(b"x" * 100)
        meta = {"video_id": video_id}
        if uploaded_days_ago is not None:
            meta["uploaded_at"] = (NOW - dt.timedelta(days=uploaded_days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
        (d / "meta.json").write_text(json.dumps(meta))

    video("old-up", 40, "abc")
    video("new-up", 3, "def")
    video("never-up", None, None)
    assert worker.prune_uploaded(tmp_path, 0, NOW) == 0 and (tmp_path / "old-up" / "video.mp4").exists()  # off
    assert worker.prune_uploaded(tmp_path, 14, NOW) == 100
    assert not (tmp_path / "old-up" / "video.mp4").exists()
    assert (tmp_path / "new-up" / "video.mp4").exists() and (tmp_path / "never-up" / "video.mp4").exists()
    assert (tmp_path / "old-up" / "meta.json").exists()  # the record stays


def test_prune_logs_removes_only_old_job_logs(tmp_path):
    old, new, keep = tmp_path / "101010-make.log", tmp_path / "111111-make.log", tmp_path / "worker.log"
    for f in (old, new, keep):
        f.write_text("x")
    past = time.time() - 40 * 86400
    for f in (old, keep):
        os.utime(f, (past, past))
    assert worker.prune_logs(tmp_path, 14, NOW) == 1
    assert not old.exists() and new.exists() and keep.exists()  # named logs are never pruned


def test_low_disk_raises_one_event(tmp_path, monkeypatch):
    monkeypatch.setattr(agentlog, "FILE", tmp_path / "e.jsonl")
    monkeypatch.setattr(agentlog.subprocess, "run", lambda *a, **k: None)
    monkeypatch.setattr(worker.shutil, "disk_usage", lambda p: types.SimpleNamespace(total=100 * 10**9, used=95 * 10**9, free=5 * 10**9))
    assert worker.check_disk(tmp_path, min_free_gb=10) is True
    assert any(e["kind"] == "error" and "disk" in e["title"].lower() for e in agentlog.recent())
    monkeypatch.setattr(worker.shutil, "disk_usage", lambda p: types.SimpleNamespace(total=100 * 10**9, used=10 * 10**9, free=90 * 10**9))
    assert worker.check_disk(tmp_path, min_free_gb=10) is False


def test_autopilot_log_rotates(tmp_path, monkeypatch):
    import autopilot

    monkeypatch.setattr(autopilot, "LOG", tmp_path / "autopilot.log")
    (tmp_path / "autopilot.log").write_text("x" * 2_100_000)
    autopilot._log("hello")
    assert (tmp_path / "autopilot.log.1").exists() and "hello" in (tmp_path / "autopilot.log").read_text()
    assert (tmp_path / "autopilot.log").stat().st_size < 1000


def test_encoder_probe_runs_once(monkeypatch):
    import render

    calls = []
    real = render.subprocess.run
    monkeypatch.setattr(render.subprocess, "run", lambda *a, **k: calls.append(1) or real(*a, **k))
    render._encoder_flags.cache_clear()
    render._venc("22", "veryfast")
    render._venc("21", "medium")
    assert len(calls) == 1


def test_failed_topic_goes_to_the_back_then_is_dropped(tmp_path, monkeypatch):
    import config, topicqueue
    monkeypatch.setattr(config, "TOPICS_FILE", tmp_path / "topics.json")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    topicqueue._write(["A", "B", "C"])
    assert topicqueue.requeue_failed("A") is True
    assert topicqueue.items() == ["B", "C", "A"]  # the next run tries B, not A again
    assert topicqueue.requeue_failed("A") is False
    assert topicqueue.items() == ["B", "C"]
