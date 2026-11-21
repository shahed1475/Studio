"""Load-shedding recovery (20 Nov 2026): finished scenes, voice lines and the saved script survive a cut; nothing half-written is ever trusted. Real ffmpeg on
tiny disposable videos; nothing here touches output/, data/ or the live studio."""
import json
import shutil
import subprocess

import pytest

import checkpoint
import render

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="ffmpeg missing")
SIZE = (160, 90)


def _tone(path, seconds):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}", "-ar", "44100", str(path)], check=True)


def _picture(path, colour="red"):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c={colour}:s=320x180", "-frames:v", "1", str(path)], check=True)


def _job(tmp_path, n=4):
    work = tmp_path / "work"
    work.mkdir(parents=True)
    _tone(work / "narration.wav", n)
    pics = []
    for i in range(n):
        p = tmp_path / f"p{i}.png"
        _picture(p, ["red", "green", "blue", "yellow", "white", "black"][i % 6])
        pics.append(p)
    return work, pics, [1.0] * n


def _stamps(work):
    return {p.name: (p.stat().st_ino, p.stat().st_mtime_ns) for p in sorted(work.glob("seg??.mp4"))}


def test_a_second_run_keeps_every_checked_scene_and_the_finished_video(tmp_path):
    work, pics, durs = _job(tmp_path)
    out = tmp_path / "video.mp4"
    render._render_ungated(pics, durs, work / "narration.wav", None, work, out, size=SIZE)
    assert checkpoint.check_media(out, seconds=4.0, need=("video", "audio"), tol=0.5, full=True) is None
    before, video = _stamps(work), out.stat().st_mtime_ns
    render._render_ungated(pics, durs, work / "narration.wav", None, work, out, size=SIZE)
    assert _stamps(work) == before and out.stat().st_mtime_ns == video  # nothing rendered twice
    man = json.loads((work / "segments.json").read_text())
    assert len(man["segments"]) == 4 and all(r["sha256"] and r["bytes"] for r in man["segments"].values())


def test_a_cut_mid_render_keeps_the_scenes_before_it_and_renders_only_the_rest(tmp_path, monkeypatch):
    work, pics, durs = _job(tmp_path)
    out = tmp_path / "video.mp4"
    real = render._ff
    calls = {"n": 0}

    def cut_on_third_scene(*args, cwd):
        if any(str(a).startswith("seg02") for a in args):
            raise KeyboardInterrupt("power cut")
        calls["n"] += 1
        return real(*args, cwd=cwd)

    monkeypatch.setattr(render, "_ff", cut_on_third_scene)
    with pytest.raises(KeyboardInterrupt):
        render._render_ungated(pics, durs, work / "narration.wav", None, work, out, size=SIZE)
    assert not out.exists()
    kept = _stamps(work)
    assert set(kept) == {"seg00.mp4", "seg01.mp4"}
    monkeypatch.setattr(render, "_ff", real)
    made = []
    monkeypatch.setattr(render, "_ff", lambda *a, cwd: (made.append([str(x) for x in a]), real(*a, cwd=cwd))[1])
    render._render_ungated(pics, durs, work / "narration.wav", None, work, out, size=SIZE)
    scene_cmds = [c for c in made if any(x.startswith("seg") and x.endswith(".part.mp4") for x in c)]
    assert len(scene_cmds) == 2  # scenes 3 and 4 only
    assert {k: v for k, v in _stamps(work).items() if k in kept} == kept
    assert checkpoint.check_media(out, seconds=4.0, need=("video", "audio"), tol=0.5, full=True) is None


def test_a_damaged_or_changed_scene_is_made_again_and_the_others_are_kept(tmp_path):
    work, pics, durs = _job(tmp_path)
    out = tmp_path / "video.mp4"
    render._render_ungated(pics, durs, work / "narration.wav", None, work, out, size=SIZE)
    before = _stamps(work)
    with open(work / "seg01.mp4", "r+b") as f:  # a cut while the disk wrote this file
        f.truncate(200)
    _picture(pics[3], "purple")  # an input that changed
    render._render_ungated(pics, durs, work / "narration.wav", None, work, out, size=SIZE)
    after = _stamps(work)
    assert after["seg00.mp4"] == before["seg00.mp4"] and after["seg02.mp4"] == before["seg02.mp4"]
    assert after["seg01.mp4"] != before["seg01.mp4"] and after["seg03.mp4"] != before["seg03.mp4"]
    assert checkpoint.check_media(work / "seg01.mp4", seconds=1.0) is None


def test_a_cut_during_the_final_assembly_never_leaves_a_video_that_looks_finished(tmp_path, monkeypatch):
    work, pics, durs = _job(tmp_path)
    out = tmp_path / "video.mp4"
    real = render._ff

    def cut_in_final(*args, cwd):
        if str(args[-1]).endswith("video.part.mp4"):
            real(*args, cwd=cwd)
            with open(args[-1], "r+b") as f:
                f.truncate(1000)  # half the file reached the disk
            raise KeyboardInterrupt("power cut")
        return real(*args, cwd=cwd)

    monkeypatch.setattr(render, "_ff", cut_in_final)
    with pytest.raises(KeyboardInterrupt):
        render._render_ungated(pics, durs, work / "narration.wav", None, work, out, size=SIZE)
    assert not out.exists() and (tmp_path / "video.part.mp4").exists()
    assert checkpoint.check_media(tmp_path / "video.part.mp4") is not None  # the half file is recognised as broken
    monkeypatch.setattr(render, "_ff", real)
    before = _stamps(work)
    render._render_ungated(pics, durs, work / "narration.wav", None, work, out, size=SIZE)
    assert _stamps(work) == before  # assembly again from the kept scenes, no scene made again
    assert not (tmp_path / "video.part.mp4").exists()
    assert checkpoint.check_media(out, seconds=4.0, need=("video", "audio"), tol=0.5, full=True) is None


def test_a_finished_video_changed_afterwards_is_assembled_again_not_trusted(tmp_path):
    work, pics, durs = _job(tmp_path, 2)
    out = tmp_path / "video.mp4"
    render._render_ungated(pics, durs, work / "narration.wav", None, work, out, size=SIZE)
    out.write_bytes(out.read_bytes()[:500])
    render._render_ungated(pics, durs, work / "narration.wav", None, work, out, size=SIZE)
    assert checkpoint.check_media(out, seconds=2.0, need=("video", "audio"), tol=0.5, full=True) is None


def test_a_second_render_of_the_same_job_is_refused_while_one_runs(tmp_path):
    work, pics, durs = _job(tmp_path, 1)
    with checkpoint.lock(work):
        with pytest.raises(checkpoint.Busy):
            render._render_ungated(pics, durs, work / "narration.wav", None, work, tmp_path / "v.mp4", size=SIZE)


def test_no_render_starts_without_room_on_the_disk_and_nothing_is_deleted(tmp_path, monkeypatch):
    work, pics, durs = _job(tmp_path, 1)
    keep = sorted(p.name for p in tmp_path.rglob("*"))
    monkeypatch.setattr(checkpoint.shutil, "disk_usage", lambda p: shutil._ntuple_diskusage(10, 9, 1))
    with pytest.raises(RuntimeError, match="not rendering"):
        render._render_ungated(pics, durs, work / "narration.wav", None, work, tmp_path / "v.mp4", size=SIZE)
    assert sorted(p.name for p in tmp_path.rglob("*")) == keep


def test_the_state_file_is_atomic_and_falls_back_to_its_previous_version(tmp_path):
    p = tmp_path / "state.json"
    checkpoint.write_json(p, {"v": 1})
    checkpoint.write_json(p, {"v": 2})
    assert checkpoint.read_json(p) == {"v": 2}
    p.write_text('{"v": 3, "half')  # a write the cut stopped half way
    assert checkpoint.read_json(p) == {"v": 1} or checkpoint.read_json(p) == {"v": 2}
    assert not list(tmp_path.glob("*.tmp"))


def test_an_unfinished_run_from_another_boot_is_seen_as_interrupted_and_an_ended_one_is_not(tmp_path):
    work = tmp_path / "work"
    checkpoint.write_json(work / checkpoint.MANIFEST, {"run": {"pid": 1, "boot": "an-earlier-boot", "started": "2026-11-20T10:00:00+00:00"}})
    assert checkpoint.was_interrupted(work)
    began = checkpoint.start_run(work, "doc")
    assert began["interrupted"] and not checkpoint.was_interrupted(work)  # this run is alive
    checkpoint.end_run(work, "done")
    assert not checkpoint.was_interrupted(work)
    assert checkpoint.read_json(work / checkpoint.MANIFEST)["history"][0]["interrupted"] is True


def test_voice_lines_made_before_a_cut_are_kept_with_their_timing(tmp_path, monkeypatch):
    import tts

    calls = []

    async def fake_synth(text, mp3, prosody=None):
        calls.append(text)
        _tone(mp3.with_suffix(".wav"), 0.6)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(mp3.with_suffix(".wav")), "-f", "mp3", str(mp3)], check=True)
        return [(0.0, 0.5, text.split()[0])]

    monkeypatch.setattr(tts, "_synth_line", fake_synth)
    monkeypatch.setattr(tts.audiofinish, "finish", lambda *a, **k: False)
    work = tmp_path / "work"
    lines = ["First line here.", "Second line here.", "Third line here."]
    _, _, d1 = tts.narrate(lines, work, 0.12)
    assert len(calls) == 3
    _, _, d2 = tts.narrate(lines, work, 0.12)
    assert len(calls) == 3 and d1 == d2  # nothing asked again, same timing
    (work / "line01.mp3").write_bytes(b"half")  # a cut while this line was written
    tts.narrate([lines[0], lines[1], "A changed third line."], work, 0.12)
    assert calls[3:] == ["Second line here.", "A changed third line."]
    assert not list(work.glob("*.part.mp3"))


def test_a_power_cut_does_not_use_up_one_of_a_films_three_tries(tmp_path, monkeypatch):
    import run

    pend = tmp_path / "pending_doc.json"
    out = tmp_path / "output"
    (out / "doc-x" / "work").mkdir(parents=True)
    monkeypatch.setattr(run, "PENDING_DOC", pend)
    monkeypatch.setattr(run.config, "OUT", out)
    lines = [{"text": "word " * 60}] * 70
    monkeypatch.setattr(run.scriptgen, "min_doc_words", lambda: 100)
    seen = []
    monkeypatch.setattr(run, "_produce_doc", lambda data, folder=None: seen.append(folder))
    run._write_pending({"data": {"title": "X", "lines": lines}, "folder": "doc-x", "tries": 1})
    checkpoint.write_json(out / "doc-x" / "work" / checkpoint.MANIFEST, {"run": {"pid": 1, "boot": "an-earlier-boot"}})
    run._cmd_doc()
    assert checkpoint.read_json(pend)["tries"] == 1 and seen == [out / "doc-x"]
    checkpoint.end_run(out / "doc-x" / "work", "stopped: a real failure")
    run._cmd_doc()
    assert checkpoint.read_json(pend)["tries"] == 2  # a real failure still counts


def test_a_half_written_saved_script_falls_back_to_the_previous_copy(tmp_path, monkeypatch):
    import run

    pend = tmp_path / "pending_doc.json"
    monkeypatch.setattr(run, "PENDING_DOC", pend)
    monkeypatch.setattr(run.scriptgen, "min_doc_words", lambda: 10)
    saved = {"data": {"title": "Kept", "lines": [{"text": "word " * 20}]}, "folder": "", "tries": 0}
    run._write_pending(saved)
    run._write_pending({**saved, "tries": 1})
    pend.write_text('{"data": {"title": "Ke')
    assert run._pending_doc()["data"]["title"] == "Kept"


def test_the_recovery_scan_names_an_interrupted_film_and_the_step_that_continues_it(tmp_path):
    import recovery

    out = tmp_path / "output"
    work, pics, durs = _job(out / "doc-x", 2)
    render._render_ungated(pics, durs, work / "narration.wav", None, work, out / "doc-x" / "video.mp4", size=SIZE)
    (out / "doc-x" / "video.mp4").unlink()
    checkpoint.write_json(work / checkpoint.MANIFEST, {"job": "doc", "run": {"pid": 1, "boot": "an-earlier-boot", "started": "t"}, "stages": {"voice": {}}})
    (out / "doc-done" / "work").mkdir(parents=True)
    (out / "doc-done" / "meta.json").write_text("{}")  # a finished video is never reported
    pend = tmp_path / "pending_doc.json"
    checkpoint.write_json(pend, {"folder": "doc-x", "data": {}})
    items = recovery.scan(out, pend, thorough=True)
    assert [i["folder"] for i in items] == ["doc-x"]
    assert items[0]["interrupted"] and items[0]["scenes_kept"] == 2 and items[0]["stages"] == ["voice"] and "autopilot make doc" in items[0]["resume"]
    assert "INTERRUPTED" in recovery.report(items)


def test_a_deleted_state_file_is_never_brought_back_from_its_previous_copy(tmp_path):
    """A finished film deletes its saved script; its .prev must not revive it (or the same film would be made again)."""
    p = tmp_path / "pending.json"
    checkpoint.write_json(p, {"v": 1})
    checkpoint.write_json(p, {"v": 2})
    p.unlink()
    assert checkpoint.read_json(p) == {}


def test_an_unfinished_short_continues_in_its_own_folder_and_a_cut_is_not_a_try(tmp_path, monkeypatch):
    import run

    out = tmp_path / "output"
    (out / "short-x" / "work").mkdir(parents=True)
    monkeypatch.setattr(run.config, "OUT", out)
    seen = []
    monkeypatch.setattr(run, "_produce_short", lambda data, topic, folder=None, pending=False, **k: seen.append((topic, folder, pending)))
    monkeypatch.setattr(run, "_best_topic", lambda kind: pytest.fail("a saved Short comes before a new topic"))
    checkpoint.write_json(run.PENDING_SHORT, {"data": {"title": "X", "lines": []}, "topic": "T", "folder": "short-x", "tries": 1})
    checkpoint.write_json(out / "short-x" / "work" / checkpoint.MANIFEST, {"run": {"pid": 1, "boot": "an-earlier-boot"}})
    run._cmd_make()
    assert seen == [("T", out / "short-x", True)] and checkpoint.read_json(run.PENDING_SHORT)["tries"] == 1
    checkpoint.end_run(out / "short-x" / "work", "stopped: a real failure")
    run._cmd_make()
    assert checkpoint.read_json(run.PENDING_SHORT)["tries"] == 2
    checkpoint.write_json(run.PENDING_SHORT, {"data": {"title": "X"}, "topic": "T", "folder": "short-x", "tries": run.MAX_RESUMES})
    monkeypatch.setattr(run, "_best_topic", lambda kind: None)
    monkeypatch.setattr(run, "cmd_ideas", lambda n: None)
    with pytest.raises(SystemExit, match="no topics"):
        run._cmd_make()  # three real failures: the saved Short is not tried a fourth time


def test_a_short_with_a_topic_given_by_the_owner_never_picks_up_the_saved_one(tmp_path, monkeypatch):
    import run

    checkpoint.write_json(run.PENDING_SHORT, {"data": {"title": "X"}, "topic": "T", "folder": "", "tries": 0})
    monkeypatch.setattr(run.wikipedia if hasattr(run, "wikipedia") else __import__("wikipedia"), "facts_for", lambda t, chars=0: None)
    monkeypatch.setattr(run.scriptgen, "script", lambda *a, **k: (_ for _ in ()).throw(ValueError("stop here")))
    with pytest.raises(SystemExit, match="could not generate"):
        run._cmd_make("Another topic")
    assert checkpoint.read_json(run.PENDING_SHORT)["topic"] == "T"


def test_a_restarted_container_that_gives_the_old_pid_to_a_new_process_still_counts_as_a_cut(tmp_path):
    """21 Nov 2026: inside a container, pids start from 1 again after a restart, so the old run's pid can belong to a live, unrelated process. The run's
    recorded start time tells them apart; a record without one (older runs) is judged by pid and boot as before."""
    import os

    work = tmp_path / "work"
    me, boot = os.getpid(), checkpoint.boot_id()
    checkpoint.write_json(work / checkpoint.MANIFEST, {"run": {"pid": me, "pstart": "1", "boot": boot, "started": "t"}})
    assert checkpoint.proc_start(me) not in ("", "1")
    assert checkpoint.was_interrupted(work)  # same boot, the pid is alive, but it is not the process that started the run
    checkpoint.write_json(work / checkpoint.MANIFEST, {"run": {"pid": me, "pstart": checkpoint.proc_start(me), "boot": boot, "started": "t"}})
    assert not checkpoint.was_interrupted(work)  # the very process is still running
    checkpoint.write_json(work / checkpoint.MANIFEST, {"run": {"pid": me, "boot": boot, "started": "t"}})
    assert not checkpoint.was_interrupted(work)  # an old record: pid and boot only
    began = checkpoint.start_run(work, "doc")
    assert checkpoint.read_json(work / checkpoint.MANIFEST)["run"]["pstart"] == checkpoint.proc_start(me) and not began["interrupted"]


@pytest.mark.parametrize("kind", ["doc", "short"])
def test_a_cut_after_the_record_is_saved_never_makes_the_same_video_twice(tmp_path, monkeypatch, kind):
    """21 Nov 2026: a cut between records.save and clearing the saved script left both. The resume found meta.json, passed no folder, and the producer
    made the same video again in a new folder. Now the finished folder is returned, its work folder removed, the saved script cleared."""
    import run

    out = tmp_path / "output"
    folder = out / f"{kind}-x"
    (folder / "work").mkdir(parents=True)
    (folder / "work" / "seg00.mp4").write_bytes(b"x")
    (folder / "video.mp4").write_bytes(b"finished")
    (folder / "meta.json").write_text(json.dumps({"title": "A polished title", "topic": "T"}))  # the title was polished after the save; the topic is the same
    monkeypatch.setattr(run.config, "OUT", out)
    pend = tmp_path / f"pending_{kind}.json"
    monkeypatch.setattr(run, "PENDING_DOC" if kind == "doc" else "PENDING_SHORT", pend)
    monkeypatch.setattr(run.scriptgen, "min_doc_words", lambda: 10)
    monkeypatch.setattr(run, "_produce_doc", lambda *a, **k: pytest.fail("the finished film was made again"))
    monkeypatch.setattr(run, "_produce_short", lambda *a, **k: pytest.fail("the finished Short was made again"))
    checkpoint.write_json(pend, {"data": {"title": "X", "topic": "T", "lines": [{"text": "word " * 20}]}, "topic": "T", "folder": folder.name, "tries": 0})
    checkpoint.write_json(pend, {**checkpoint.read_json(pend), "tries": 1})  # a .prev exists too: it must not revive the saved script
    got = run._cmd_doc() if kind == "doc" else run._cmd_make()
    assert got == folder and not (folder / "work").exists() and (folder / "video.mp4").read_bytes() == b"finished"
    assert not pend.exists() and checkpoint.read_json(pend) == {}


def test_a_saved_script_whose_folder_holds_another_video_is_still_made(tmp_path, monkeypatch):
    """Only the saved video's own finished record ends the resume: a folder whose record is a different story is not taken as finished."""
    import run

    out = tmp_path / "output"
    (out / "doc-x").mkdir(parents=True)
    (out / "doc-x" / "video.mp4").write_bytes(b"v")
    (out / "doc-x" / "meta.json").write_text(json.dumps({"title": "Another film", "topic": "Other"}))
    monkeypatch.setattr(run.config, "OUT", out)
    pend = tmp_path / "pending_doc.json"
    monkeypatch.setattr(run, "PENDING_DOC", pend)
    monkeypatch.setattr(run.scriptgen, "min_doc_words", lambda: 10)
    seen = []
    monkeypatch.setattr(run, "_produce_doc", lambda data, folder=None: seen.append(folder))
    run._write_pending({"data": {"title": "X", "topic": "T", "lines": [{"text": "word " * 20}]}, "folder": "doc-x", "tries": 0})
    run._cmd_doc()
    assert seen == [None] and pend.exists()


def test_the_recovery_scan_names_an_interrupted_short_with_its_own_resume_step_and_counts_kept_parts(tmp_path):
    """21 Nov 2026: a cut Short resumes in its own folder (data/pending_short.json); the scan once told the owner it would start a new folder."""
    import recovery

    out = tmp_path / "output"
    (out / "short-x" / "work").mkdir(parents=True)
    checkpoint.write_json(out / "short-x" / "work" / checkpoint.MANIFEST, {"job": "short", "run": {"pid": 1, "boot": "an-earlier-boot", "started": "t"}})
    (out / "short-x" / "work" / "part00.mp4").write_bytes(b"12345")
    checkpoint.write_json(out / "short-x" / "work" / "segments.json", {"segments": {}, "parts": {"part00.mp4": {"bytes": 5}}})
    checkpoint.write_json(tmp_path / "pending_short.json", {"folder": "short-x", "data": {}, "topic": "T"})
    items = recovery.scan(out, tmp_path / "pending_doc.json")
    assert items[0]["resume"] == recovery.RESUME_SHORT and items[0]["final_parts_kept"] == 1
    assert "final-video parts kept: 1" in recovery.report(items)
