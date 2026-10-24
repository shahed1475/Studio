import json
import multiprocessing
import os

import pytest

import records


def _bump(args):
    folder, key = args
    for _ in range(20):
        records.update(folder, lambda d: d.__setitem__(key, d.get(key, 0) + 1))


def test_create_read_merge_roundtrip(tmp_path):
    f = tmp_path / "v"
    records.create(f, {"title": "T"})
    assert records.read(f) == {"title": "T"}
    records.merge(f, {"hold": True})
    assert records.read(f) == {"title": "T", "hold": True}
    assert json.loads((f / "meta.json").read_text())["hold"] is True  # the format is a plain meta.json


def test_create_refuses_an_existing_record(tmp_path):
    f = tmp_path / "v"
    records.create(f, {"a": 1})
    with pytest.raises(records.RecordError):
        records.create(f, {"a": 2})
    assert records.read(f) == {"a": 1}


def test_update_keeps_keys_written_by_someone_else(tmp_path):
    f = tmp_path / "v"
    records.create(f, {"a": 1})
    records.merge(f, {"b": 2})          # another writer
    records.merge(f, {"c": 3})          # this writer re-reads, so b survives
    assert records.read(f) == {"a": 1, "b": 2, "c": 3}


def test_parallel_writers_lose_no_update(tmp_path):
    f = tmp_path / "v"
    records.create(f, {})
    with multiprocessing.Pool(4) as pool:
        pool.map(_bump, [(f, "n")] * 4)
    assert records.read(f)["n"] == 80


def test_a_crash_inside_update_keeps_the_old_record_and_leaves_no_temp(tmp_path):
    f = tmp_path / "v"
    records.create(f, {"a": 1})

    def boom(d):
        d["a"] = 99
        raise RuntimeError("crash")

    with pytest.raises(RuntimeError):
        records.update(f, boom)
    assert records.read(f) == {"a": 1}
    assert not (f / "meta.json.tmp").exists()


def test_a_held_lock_times_out_with_a_clear_error(tmp_path, monkeypatch):
    f = tmp_path / "v"
    records.create(f, {"a": 1})
    monkeypatch.setattr(records, "LOCK_WAIT_SECONDS", 0.2)
    with records._lock(f):
        with pytest.raises(records.RecordError, match="could not lock"):
            # a second lock from another descriptor in the same process blocks like another process would
            records.read(f)
    assert records.read(f) == {"a": 1}


def test_lock_file_is_private(tmp_path):
    f = tmp_path / "v"
    records.create(f, {})
    assert oct(os.stat(f / ".meta.lock").st_mode & 0o777) == "0o600"


def test_controls_release_and_recheck_heal_use_the_record_writer(tmp_path, monkeypatch):
    import config
    import controls
    import recheck

    monkeypatch.setattr(config, "OUT", tmp_path)
    f = tmp_path / "draft"
    records.create(f, {"hold": True, "publish_at": "2026-01-01T00:00:00Z", "autopilot_fails": 2, "keep": 1})
    controls.release("draft")
    assert records.read(f) == {"hold": False, "autopilot_fails": 0, "keep": 1}  # a released draft loses its stale slot
    g = tmp_path / "up"
    records.create(g, {"video_id": "x", "upload_check": {"ok": True, "publishAt": "2026-02-02T00:00:00Z"}, "extra": 5})
    assert recheck.heal() == ["up"]
    healed = records.read(g)
    assert healed["publish_at"] == "2026-02-02T00:00:00Z" and healed["approved"] is True and healed["extra"] == 5 and "healed" in healed


def test_autopilot_writers_keep_keys_saved_by_others(tmp_path, monkeypatch):
    import autopilot
    import config

    monkeypatch.setattr(config, "OUT", tmp_path)
    f = tmp_path / "v"
    records.create(f, {"format": "short", "title": "T", "other": 1})
    records.merge(f, {"added_by_dashboard": True})
    monkeypatch.setattr(autopilot, "visually_ok", lambda slug: True)
    autopilot._approve("v")
    now = records.read(f)
    assert now["approved"] is True and now["approved_by"] == "reviewer-agent" and now["added_by_dashboard"] is True and now["other"] == 1


def test_fixer_save_replaces_the_record_atomically_and_upload_merge_keeps_other_keys(tmp_path):
    import fixer

    f = tmp_path / "v"
    records.create(f, {"a": 1, "b": 2})
    fixer._save(f, {"a": 1, "b": 3, "c": 4})
    assert records.read(f) == {"a": 1, "b": 3, "c": 4}
    assert not (f / "meta.json.tmp").exists()
    records.merge(f, {"video_id": "x", "upload_check": {"ok": True}})  # what upload() now saves in one merge
    assert records.read(f)["c"] == 4 and records.read(f)["video_id"] == "x"
