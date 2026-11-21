"""The owner sets the documentary length on the Autopilot page (20 Nov 2026): one action, kept in the rules file's history, read by every new job.
tests/conftest.py points rulesfile at a private copy, so the real data/rules_state.json is never written here."""
import json
import subprocess
import sys

import pytest

import config
import dashboard
import rulesfile


def test_the_page_shows_the_length_new_videos_are_written_for():
    v = dashboard.doc_length_view()
    assert (v["min"], v["max"]) == (20.0, 26.0) and v["lines"] == [84, 100] and 3350 <= v["words"] <= 3450 and v["limits"] == [5, 30]  # 23 min at the measured long-film rate, 148.3 words a minute (21 Nov 2026)


def test_saving_a_length_is_an_approved_rules_change_that_a_new_job_reads():
    got = dashboard.set_doc_length({"min": 18, "max": 24})
    assert got["ok"] and "approved" in got["result"] and (got["min"], got["max"]) == (18.0, 24.0)
    assert (rulesfile.get("benchmarks", "long_min_minutes"), rulesfile.get("benchmarks", "long_max_minutes")) == (18, 24)
    state = json.loads(rulesfile.STATE.read_text())
    assert state["benchmarks"] == {"long_min_minutes": 18, "long_max_minutes": 24} and state["history"][-1]["decision"] == "approved"
    # a new process (each worker job is one) reads the saved length: the writer's numbers follow it, Shorts do not
    code = ("import sys; sys.path.insert(0, %r); import rulesfile; rulesfile.FILE = __import__('pathlib').Path(%r); rulesfile.STATE = __import__('pathlib').Path(%r); "
            "import scriptgen; print(scriptgen.DOC_MINUTES, scriptgen.MIN_DOC_LINES, scriptgen.MAX_DOC_LINES, rulesfile.get('benchmarks', 'shorts_max_seconds'))"
            % (str(config.ROOT), str(rulesfile.FILE), str(rulesfile.STATE)))
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=config.ROOT, timeout=60).stdout.strip()
    assert out.startswith("(18.0, 24.0)") and out.endswith(" 58"), out


@pytest.mark.parametrize("body", [{"min": 26, "max": 20}, {"min": 4, "max": 10}, {"min": 20, "max": 31}, {"min": "20", "max": 26}, {"min": True, "max": 26}, {}])
def test_a_wrong_length_is_refused_and_nothing_changes(body):
    with pytest.raises(ValueError):
        dashboard.set_doc_length(body)
    assert rulesfile.get("benchmarks", "long_min_minutes") == 20


def test_the_rules_section_has_the_control_and_posts_to_the_route():
    html = (config.ROOT / "dashboard.html").read_text()
    assert 'id="ap_dl0"' in html and 'id="ap_dl1"' in html and 'api("/api/rules/doc-length"' in html
    assert 'path == "/api/rules/doc-length"' in __import__("inspect").getsource(dashboard)
