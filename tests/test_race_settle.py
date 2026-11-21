"""A free-model race leaves the losing request running. When it finishes it records into data/free_models.json, so anything that redirects that
file for a while must wait for it (llm.settle) before putting the real path back (20 Nov 2026: invented test models replaced the real history).
Events, not time.sleep: tests/conftest.py makes time.sleep a no-op."""
import datetime as dt
import threading

import agenteval
import freemodels
import llm


def _race_with_a_slow_loser(monkeypatch, written):
    release = threading.Event()

    def ask(model, prompt, role, cfg, key, now):
        if model == "fast":
            return {"ok": 1}
        release.wait(5)
        freemodels._save({"late": model})  # what a real loser does when it finally answers: freemodels.record writes the file
        written.set()
        return None

    monkeypatch.setattr(llm, "_ask_free", ask)
    threading.Timer(0.2, release.set).start()  # the loser answers 0.2 s after the winner
    return llm._race(["fast", "slow"], "p", "script", {}, "k", dt.datetime(2026, 11, 20, tzinfo=dt.timezone.utc))


def test_a_late_loser_never_writes_the_real_file_after_the_evaluation(monkeypatch, tmp_path):
    real, written = tmp_path / "real_free_models.json", threading.Event()
    monkeypatch.setattr(freemodels, "FILE", real)
    with agenteval.isolated():
        assert _race_with_a_slow_loser(monkeypatch, written) == {"ok": 1}
    assert written.wait(5)  # the loser did answer, while the redirect was still in place
    assert not real.exists() and freemodels.FILE == real and llm.settle(1) == 0


def test_without_settle_the_late_loser_reaches_the_real_file(monkeypatch, tmp_path):
    real, written = tmp_path / "real_free_models.json", threading.Event()
    monkeypatch.setattr(freemodels, "FILE", real)
    monkeypatch.setattr(llm, "settle", lambda timeout=30.0: 0)  # mutation: nobody waits, as before 20 Nov 2026
    with agenteval.isolated():
        _race_with_a_slow_loser(monkeypatch, written)
    assert written.wait(5) and real.exists()  # this is the pollution the real settle prevents
