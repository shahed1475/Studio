"""free_models.json under concurrent writers (20 Nov 2026): the raced requests of llm._race, other jobs and the dashboard record at the same time. A reader that caught the file
half written read it as empty and the next save wiped every model's history and the day's request count (about 40 models down to 3)."""
import datetime as dt
import json
import subprocess
import sys
import threading
from pathlib import Path

import freemodels

NOW = dt.datetime(2026, 11, 20, 12, 0, tzinfo=dt.timezone.utc)
ROOT = Path(__file__).resolve().parent.parent


def test_threads_recording_at_once_lose_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(freemodels, "FILE", tmp_path / "free_models.json")
    models = [f"m{i}/x:free" for i in range(8)]

    def work(m):
        for _ in range(25):
            freemodels.record(m, True, NOW, role="review", seconds=1.0)
            freemodels.count_request(NOW, "review")

    threads = [threading.Thread(target=work, args=(m,)) for m in models]
    [t.start() for t in threads]
    [t.join() for t in threads]
    d = json.loads(freemodels.FILE.read_text())
    assert sorted(d["health"]) == sorted(models) and all(d["health"][m]["ok"] == 25 for m in models)
    assert d["usage"]["2026-11-20"] == 8 * 25


def test_separate_processes_recording_at_once_lose_nothing_and_never_leave_half_a_file(tmp_path):
    f = tmp_path / "free_models.json"
    code = ("import sys, datetime as dt; sys.path.insert(0, {root!r}); import freemodels, pathlib; freemodels.FILE = pathlib.Path({f!r}); "
            "now = dt.datetime(2026, 11, 20, 12, 0, tzinfo=dt.timezone.utc)\n"
            "for _ in range(30): freemodels.record('p{n}/x:free', True, now, role='script', seconds=1.0); freemodels.count_request(now, 'script')")
    procs = [subprocess.Popen([sys.executable, "-c", code.format(root=str(ROOT), f=str(f), n=n)]) for n in range(4)]
    bad_reads = 0
    while any(p.poll() is None for p in procs):
        try:
            if f.exists():
                json.loads(f.read_text())
        except ValueError:
            bad_reads += 1
    assert all(p.wait() == 0 for p in procs)
    d = json.loads(f.read_text())
    assert bad_reads == 0  # a reader never sees half a file
    assert sorted(d["health"]) == [f"p{n}/x:free" for n in range(4)] and all(v["ok"] == 30 for v in d["health"].values())
    assert d["usage"]["2026-11-20"] == 4 * 30
