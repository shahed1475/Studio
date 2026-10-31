"""My Downloads: the download queue: one video at a time, skip what is saved, stop, and carry on after a power cut."""
import json

import pytest

from mydownloads import engine, jobs, store


def vid(n):
    return "v" + f"{n:010d}"


class FakeEngine:
    """Stands in for the real engine. `plan` maps a video id to what happens: 'ok', 'mine' (not my channel), 'boom', or 'stop' (the owner presses Stop)."""

    def __init__(self, plan=None):
        self.plan, self.calls, self.runner = plan or {}, [], None

    def download(self, video_id, folder, on_progress, stop):
        self.calls.append(video_id)
        what = self.plan.get(video_id, "ok")
        if what == "mine":
            raise engine.NotMine("This video is on “Other”, which is not one of your channels, so I will not download it.")
        if what == "boom":
            raise Exception("ERROR: Unable to download webpage: getaddrinfo failed")
        if what == "stop":
            self.runner.stop()
            raise engine.Cancelled("stopped")
        on_progress({"percent": 40.0, "speed": 1000.0, "eta": 5, "bytes": 400, "stage": "downloading"})
        if self.runner is not None:
            self.seen = self.runner.snapshot()
        out = folder / "The Sleeping Library" / f"T [{video_id}].mp4"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"x" * 2048)
        return out


@pytest.fixture(autouse=True)
def private_home(tmp_path, monkeypatch):
    monkeypatch.setenv("MYDL_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("MYDL_FOLDER", str(tmp_path / "Downloads"))


def runner(plan=None, **kw):
    eng = FakeEngine(plan)
    r = jobs.Runner(eng, threaded=False, sleep=kw.pop("sleep", lambda s: None), free_bytes=kw.pop("free_bytes", lambda p: 50 << 30), **kw)
    eng.runner = r
    return r, eng


def items(*ns):
    return [{"id": vid(n), "title": f"Video {n}", "kind": "long"} for n in ns]


def statuses(r):
    return [i["status"] for i in r.snapshot()["items"]]


def test_runs_every_item_in_order_and_records_the_file():
    r, eng = runner()
    r.start(items(1, 2, 3))
    r.run()
    s = r.snapshot()
    assert eng.calls == [vid(1), vid(2), vid(3)]
    assert s["state"] == "done" and statuses(r) == ["done"] * 3
    assert s["items"][0]["file"].endswith(f"T [{vid(1)}].mp4") and s["items"][0]["bytes"] == 2048


def test_progress_is_visible_while_a_video_downloads():
    r, eng = runner()
    r.start(items(1))
    r.run()
    cur = eng.seen["items"][0]
    assert cur["status"] == "downloading" and cur["percent"] == 40.0 and cur["speed"] == 1000.0


def test_a_video_already_in_the_folder_is_skipped_not_downloaded_again(tmp_path):
    d = tmp_path / "Downloads" / "The Sleeping Library"
    d.mkdir(parents=True)
    (d / f"Old [{vid(2)}].mp4").write_bytes(b"x")
    r, eng = runner()
    r.start(items(1, 2, 3))
    r.run()
    assert eng.calls == [vid(1), vid(3)] and statuses(r) == ["done", "skipped", "done"]


def test_a_video_that_is_not_mine_is_refused_and_the_rest_carry_on():
    r, eng = runner({vid(1): "mine"})
    r.start(items(1, 2))
    r.run()
    s = r.snapshot()
    assert statuses(r) == ["refused", "done"] and "not one of your channels" in s["items"][0]["error"] and s["state"] == "done"


def test_a_failed_video_gets_a_plain_message_and_the_rest_carry_on():
    r, eng = runner({vid(1): "boom"})
    r.start(items(1, 2))
    r.run()
    s = r.snapshot()
    assert statuses(r) == ["failed", "done"] and "internet" in s["items"][0]["error"].lower()


def test_three_failures_in_a_row_stop_the_job_and_keep_the_rest_for_later():
    r, eng = runner({vid(n): "boom" for n in range(1, 6)})
    r.start(items(1, 2, 3, 4, 5))
    r.run()
    s = r.snapshot()
    assert statuses(r) == ["failed"] * 3 + ["queued"] * 2 and s["state"] == "stopped" and s["resumable"] is True
    assert "three" in s["message"].lower()


def test_pressing_stop_puts_the_current_video_back_in_the_queue():
    r, eng = runner({vid(2): "stop"})
    r.start(items(1, 2, 3))
    r.run()
    s = r.snapshot()
    assert statuses(r) == ["done", "queued", "queued"] and s["state"] == "stopped" and s["resumable"] is True and eng.calls == [vid(1), vid(2)]


def test_resume_downloads_only_what_is_left():
    r, eng = runner({vid(2): "stop"})
    r.start(items(1, 2, 3))
    r.run()
    eng.plan = {}
    eng.calls.clear()
    r.resume()
    r.run()
    assert eng.calls == [vid(2), vid(3)] and r.snapshot()["state"] == "done"


def test_only_one_job_at_a_time():
    r, _ = runner()
    r.start(items(1))
    with pytest.raises(jobs.Busy):
        r.start(items(2))


def test_a_polite_pause_separates_downloads():
    pauses = []
    r, _ = runner(sleep=pauses.append)
    r.start(items(1, 2, 3))
    r.run()
    assert len(pauses) == 2 and all(p >= 1 for p in pauses)


@pytest.mark.parametrize("bad", [[], [{"id": "../../x", "title": "t"}], [{"id": "", "title": "t"}], [{"title": "no id"}], "nope", [{"id": vid(1)}] * 0])
def test_start_refuses_a_bad_list(bad):
    r, _ = runner()
    with pytest.raises(ValueError):
        r.start(bad)


def test_start_refuses_more_than_the_batch_limit():
    r, _ = runner()
    with pytest.raises(ValueError, match="at most"):
        r.start([{"id": f"v{n:010d}", "title": "t"} for n in range(300)])


def test_start_ignores_a_repeated_id_and_cleans_the_title():
    r, _ = runner()
    r.start([{"id": vid(1), "title": "A\n<b>x</b>" + "y" * 400}, {"id": vid(1), "title": "again"}])
    its = r.snapshot()["items"]
    assert len(its) == 1 and len(its[0]["title"]) <= 200 and "\n" not in its[0]["title"]


def test_not_enough_disk_space_refuses_to_start():
    r, _ = runner(free_bytes=lambda p: 10 << 20)
    with pytest.raises(ValueError, match="disk space"):
        r.start(items(1))
    assert r.snapshot() is None


def test_the_queue_is_saved_so_a_power_cut_can_be_recovered():
    store.save_job({"id": "j1", "state": "running", "folder": str(store.folder()), "message": "", "started": "2026-10-31T10:00:00Z",
                    "items": [{"id": vid(1), "title": "A", "kind": "long", "status": "done", "percent": 100, "file": "f"},
                              {"id": vid(2), "title": "B", "kind": "long", "status": "downloading", "percent": 61},
                              {"id": vid(3), "title": "C", "kind": "long", "status": "queued", "percent": 0}]})
    r, eng = runner()
    s = r.snapshot()
    assert s["state"] == "interrupted" and s["resumable"] is True
    assert [i["status"] for i in s["items"]] == ["done", "queued", "queued"]
    r.resume()
    r.run()
    assert eng.calls == [vid(2), vid(3)]  # the finished one is not repeated


def test_every_outcome_is_written_to_the_log():
    r, _ = runner({vid(2): "mine", vid(3): "boom"})
    r.start(items(1, 2, 3))
    r.run()
    rows = [json.loads(l) for l in (store.home() / "downloads.log").read_text().splitlines()]
    assert [(x["id"], x["status"]) for x in rows] == [(vid(1), "done"), (vid(2), "refused"), (vid(3), "failed")]


def test_a_finished_job_can_be_cleared_by_starting_a_new_one():
    r, _ = runner()
    r.start(items(1))
    r.run()
    r.start(items(2))
    assert [i["id"] for i in r.snapshot()["items"]] == [vid(2)]
