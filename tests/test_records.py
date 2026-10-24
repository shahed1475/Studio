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
