"""The daily behaviour evaluation runs in production. On 30 Oct 2026 the owner's real action log held nine invented edits ("V2", "Mami Wata", title "t") written by it, because its sandbox
redirected four shared files and tests/conftest.py (which redirects more) applies only under pytest. A full run must write nothing outside its own temporary folder."""
import hashlib
import importlib

import actionlog
import agenteval


def test_a_full_evaluation_run_writes_nothing_to_the_real_shared_files(tmp_path, monkeypatch):
    watched = {}
    for i, (mod, attr) in enumerate(agenteval.SHARED_FILES):
        m = importlib.import_module(mod)
        p = tmp_path / "real" / f"{i}-{mod}-{attr}"
        monkeypatch.setattr(m, attr, p)  # where a real file would be: the evaluation must never create or change anything here
        watched[(mod, attr)] = p
    import rulesfile

    shipped = rulesfile.FILE
    before = hashlib.sha256(shipped.read_bytes()).hexdigest()
    agenteval.run(write=False)
    touched = sorted(f"{mod}.{attr}" for (mod, attr), p in watched.items() if p.exists())
    assert not touched, f"the evaluation wrote to: {touched}"
    assert hashlib.sha256(shipped.read_bytes()).hexdigest() == before, "the shipped rules file was changed"


def test_the_per_case_sandbox_also_redirects_the_action_log(tmp_path, monkeypatch):
    real = tmp_path / "real_actions.json"
    monkeypatch.setattr(actionlog, "ACTIONS", real)
    with agenteval.sandbox():
        actionlog.record("V9", {"title": "a"}, {"title": "b"}, "test")
        assert actionlog.ACTIONS != real
    assert not real.exists() and actionlog.ACTIONS == real


def test_every_listed_file_is_a_real_attribute_of_its_module():
    for mod, attr in agenteval.SHARED_FILES:
        assert hasattr(importlib.import_module(mod), attr), f"{mod}.{attr} no longer exists: the isolation table is stale"


def test_the_table_always_covers_the_files_a_real_owner_would_be_hurt_by_losing_or_polluting():
    must = {("actionlog", "ACTIONS"), ("actionlog", "EDITS"), ("policyclass", "HOLD_FILE"), ("rulesfile", "STATE"), ("agentbus", "FILE"), ("agentlog", "FILE"), ("lessons", "FILE"),
            ("autopilot", "LOG")}
    assert must <= set(agenteval.SHARED_FILES)


def test_a_future_case_that_forgets_its_sandbox_still_cannot_reach_the_real_files(tmp_path, monkeypatch):
    """The net under the per-case sandbox: a case that writes straight to the shared files is the next 'V2' waiting to happen."""
    import agentbus
    import agentlog

    real = {}
    for i, (mod, attr) in enumerate(agenteval.SHARED_FILES):
        m = importlib.import_module(mod)
        real[(mod, attr)] = tmp_path / "real" / f"{i}-{mod}-{attr}"
        monkeypatch.setattr(m, attr, real[(mod, attr)])

    def case_leaky():
        actionlog.record("V9", {"title": "t"}, {"title": "x"}, "guardian", "a case with no sandbox")
        agentlog.event("found", "an invented event", "from a leaky case")
        agentbus.post("triage_family", "triage", "trainer", "invented", reason="from a leaky case")
        return True, "leaked"

    monkeypatch.setattr(agenteval, "CASES", [case_leaky])
    agenteval.run(write=False)
    assert not any(p.exists() for p in real.values())
