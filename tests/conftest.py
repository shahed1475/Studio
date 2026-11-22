import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


import pytest


@pytest.fixture(autouse=True, scope="session")
def _session_safety_net(tmp_path_factory):
    """For the whole run, the files a background thread may still write after its test ended point at a session folder, so a late writer
    can never reach the owner's real data. llm._race leaves the losing request running (an HTTP call cannot be recalled); it recorded its
    outcome after the test's own redirect was undone and replaced data/free_models.json with invented models (20 Nov 2026). Each test still
    redirects these to its own folder; on undo they come back here, not to data/."""
    import freemodels
    import llm

    net = tmp_path_factory.mktemp("safety_net")
    saved = [(freemodels, "FILE", freemodels.FILE), (llm, "USAGE_FILE", llm.USAGE_FILE)]
    freemodels.FILE, llm.USAGE_FILE = net / "free_models.json", net / "llm_usage.json"
    yield
    llm.settle(30)
    for m, attr, old in saved:
        setattr(m, attr, old)


@pytest.fixture(autouse=True)
def _judge_cascade_off_unless_a_test_turns_it_on(tmp_path_factory, monkeypatch):
    """The judge cascade (judges.py) asks real providers. Every test sees it switched off (a copy of config/judges.json with enabled false), so a test that
    fakes only part of llm can never fall through to a real request; tests of the cascade write their own config."""
    import judges

    d = tmp_path_factory.getbasetemp() / "judge-cascade-off"  # a folder of its own: tests that list their tmp_path or its parent must not see the file
    d.mkdir(exist_ok=True)
    f = d / "judges.json"
    if not f.exists():
        f.write_text('{"enabled": false}')
    monkeypatch.setattr(judges, "CONFIG_FILE", f)


@pytest.fixture(autouse=True)
def _isolate_autopilot_log(tmp_path, monkeypatch):
    import autopilot

    monkeypatch.setattr(autopilot, "LOG", tmp_path / "autopilot.log")
    # and its lock (22 Nov 2026): a real Autopilot make holding ~/studio/autopilot.lock disabled the Autopilot page's buttons inside two browser tests,
    # which then failed; a test must never see, or take, the lock the running studio holds
    monkeypatch.setattr(autopilot, "LOCK_FILE", tmp_path / "autopilot.lock")


@pytest.fixture(autouse=True)
def _no_real_provider_model_list(monkeypatch):
    """The owner's model provider (llm.extra_catalog) runs on this PC at the address the tests use: no test reads its real model list.
    A test of the catalog itself replaces llm._catalog_get with its own fake."""
    import llm

    def refuse(url, key):
        raise OSError("tests never read a real provider's model list")

    llm._catalog.clear()
    monkeypatch.setattr(llm, "_catalog_get", refuse)
    yield
    llm._catalog.clear()
    llm._WRITERS.clear()
    llm._served.clear()


@pytest.fixture(autouse=True)
def _isolate_alert_files(tmp_path, monkeypatch):
    """No test may read the owner's saved Gmail or Telegram settings, write the hub's mail bridge, or send an alert."""
    import alerts

    monkeypatch.setattr(alerts, "SETTINGS", tmp_path / "alerts-settings.json")
    monkeypatch.setattr(alerts, "BRIDGE", tmp_path / "hubmail" / "mail.json")
    monkeypatch.setattr(alerts, "STATE", tmp_path / "alerts_state.json")


@pytest.fixture(autouse=True)
def _isolate_agent_files(tmp_path, monkeypatch):
    """No test may write the owner's real activity feed, inbox or lessons (tests/test_duplicates.py once filled the local feed with 34 invented 'Roswell Incident' events)."""
    import agentbus
    import agentlog
    import lessons

    monkeypatch.setattr(agentlog, "FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(agentbus, "FILE", tmp_path / "tasks.json")
    monkeypatch.setattr(lessons, "FILE", tmp_path / "lessons.jsonl")


@pytest.fixture(autouse=True)
def _isolate_craft_files(tmp_path, monkeypatch):
    """No test may write the owner's craft advice (data/channels/craft.json): channelwatch.run() saves it, and a stray craft.json
    once sorted last in data/channels and was read as the weekly digest."""
    import craftlearn

    monkeypatch.setattr(craftlearn, "FILE", tmp_path / "craft.json")


@pytest.fixture(autouse=True)
def _isolate_research_files(tmp_path, monkeypatch):
    """No test may write the real search-demand cache (trendwatch.run refreshes it) or the comment insights (channelwatch.run makes them)."""
    import commentinsights
    import searchdemand

    monkeypatch.setattr(searchdemand, "DIR", tmp_path / "demand")
    monkeypatch.setattr(commentinsights, "FILE", tmp_path / "comment_insights.json")
    monkeypatch.setattr(commentinsights, "api_key", lambda: "")  # a key the owner saved in Settings must never take a test onto the real API


@pytest.fixture(autouse=True)
def _isolate_growth_files(tmp_path, monkeypatch):
    """No test may write the shipped rules file (a fake policy change once left a pending change in config/rules.json) or the growth, policy-hold and action files."""
    import shutil

    import actionlog
    import diagnose
    import drift
    import growthdata
    import policyclass
    import rulesfile

    import newswatch

    monkeypatch.setattr(newswatch, "_staff_service", lambda: None)  # no test builds a real YouTube client from a login that happens to be on this machine
    shipped = rulesfile.FILE
    iso = tmp_path / "_growth_isolated"
    iso.mkdir()
    private = iso / "rules.json"
    shutil.copy(shipped, private)
    monkeypatch.setattr(rulesfile, "FILE", private)
    monkeypatch.setattr(rulesfile, "STATE", iso / "rules_state.json")
    monkeypatch.setattr(policyclass, "CLASS_FILE", iso / "policy_class.json")
    monkeypatch.setattr(policyclass, "HOLD_FILE", iso / "policy_hold.json")
    monkeypatch.setattr(actionlog, "ACTIONS", iso / "actions.json")
    monkeypatch.setattr(actionlog, "EDITS", iso / "edits.json")
    monkeypatch.setattr(growthdata, "FILE", iso / "metrics_videos.json")
    monkeypatch.setattr(growthdata, "DAILY", iso / "metrics_daily.json")
    monkeypatch.setattr(drift, "FILE", iso / "metrics_daily.json")
    monkeypatch.setattr(diagnose, "FILE", iso / "diagnoses.json")
    import learner

    monkeypatch.setattr(learner, "WEEKLY", iso / "weekly.json")
    monkeypatch.setattr(learner, "QUEUED", iso / "queued_longs.json")
    monkeypatch.setattr(learner, "REPORTS", iso / "reports")


@pytest.fixture(autouse=True)
def _isolate_trend_inbox(tmp_path, monkeypatch):
    """Trends typed in by a person are the owner's data: no test may read or write the real file."""
    import trendinbox

    monkeypatch.setattr(trendinbox, "FILE", tmp_path / "trend_inbox.json")


@pytest.fixture(autouse=True)
def _isolate_scriptreview(tmp_path, monkeypatch):
    """The script reviewer keeps results and held scripts under data/agent: a test that goes through the gate must never write the real ones."""
    import scriptreview

    monkeypatch.setattr(scriptreview, "FILE", tmp_path / "scriptreview.json")
    monkeypatch.setattr(scriptreview, "HELD", tmp_path / "scriptreview_held")


@pytest.fixture(autouse=True)
def _local_fallback_for_old_tests(monkeypatch):
    """The production default is no local model; most older tests exercise the fallback path, so they opt in here."""
    import llm

    monkeypatch.setitem(llm.DEFAULTS, "local_fallback", True)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    import freemodels

    monkeypatch.setattr(freemodels, "quota", lambda *a, **k: None)  # tests never ask the real OpenRouter
    import risk

    real = risk.credit_left
    monkeypatch.setattr(risk, "credit_left", lambda key, get=None, now=None: real(key, get, now) if get else None)  # only an injected fake reaches the code


@pytest.fixture(autouse=True)
def _isolate_owner_model_settings(tmp_path, monkeypatch):
    """No test may read the owner's llm.json, settings.json, spend records, free-picture account or downloaded depth model: on the owner's PC
    (17 Nov 2026) free review, free Cloudflare pictures and the depth model made 10 tests pass on a clean checkout and fail there. Every test
    starts from the shipped defaults, as on a clean checkout; a test that needs a setting writes or patches its own."""
    import freeart
    import llm

    iso = tmp_path / "_model_settings_isolated"
    iso.mkdir()
    monkeypatch.setattr(llm, "CONFIG_FILE", iso / "llm.json")
    monkeypatch.setattr(llm, "SETTINGS_FILE", iso / "settings.json")
    monkeypatch.setattr(llm, "USAGE_FILE", iso / "llm_usage.json")
    monkeypatch.setattr(freeart, "USAGE", iso / "cloudflare_usage.json")
    monkeypatch.setattr(llm, "_costs_file", lambda: iso / "video_costs.json")  # tests booked invented spend into the real data/video_costs.json
    import freemodels
    import videoinspect

    # 20 Nov 2026: full test runs wrote invented models (a/m1:free, b/m2:free, b/slow:free) into the real data/free_models.json and wiped the
    # learned reliability and timings of the real free models; the two OpenRouter list caches are the real ones too
    monkeypatch.setattr(freemodels, "FILE", iso / "free_models.json")
    monkeypatch.setattr(videoinspect, "MODALITY_CACHE", iso / "or_modalities.json")
    monkeypatch.setattr(llm, "PRICES_FILE", iso / "or_prices.json")
    import governor

    import config

    real_root = config.ROOT  # a test wrote the real data/governor.json and, once a day, posted a 'caps changed' notice into the next test's feed
    monkeypatch.setattr(governor, "caps_file", lambda: iso / "governor.json" if config.ROOT == real_root else config.ROOT / governor.FILE)
    for key in ("CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"):  # the owner's real free-picture keys; tests of the free account set their own
        monkeypatch.delenv(key, raising=False)
    yield
    llm.settle(10)  # a raced request that lost finishes in a thread after its test: it must count in that test's files, not the next test's (20 Nov 2026: a
    # loser's count reached test_paid_claude_is_used_while_credit_lasts, which then saw 2 free requests instead of 0, about one full run in two)


@pytest.fixture(autouse=True)
def _no_listening_in_tests(monkeypatch):
    """The studio listens to the narration of a video it approves (a model call). No test may do that by accident; the tests of the check itself switch it on and use a fake model."""
    import voicecheck

    monkeypatch.setattr(voicecheck, "ENABLED", False)


@pytest.fixture(autouse=True)
def _no_real_music(tmp_path, monkeypatch):
    """No test mixes the owner's real music folder into a video (musicbed.py); a test of the bed itself points DIR at its own tracks."""
    import musicbed

    monkeypatch.setattr(musicbed, "DIR", tmp_path / "_no_music")


@pytest.fixture(autouse=True)
def _no_real_blender(tmp_path, monkeypatch):
    """No test starts the owner's real Blender or asks Wikipedia for coordinates through a producer (blenderscenes.py). The smoke test of Blender itself sets its own path."""
    import blenderscenes
    import ccrender

    monkeypatch.setattr(ccrender, "BLENDER", tmp_path / "_no_blender" / "blender")
    monkeypatch.setattr(blenderscenes, "coordinates", lambda title: None)


@pytest.fixture(autouse=True)
def _no_real_draft(tmp_path, monkeypatch):
    """No test writes or resumes the real saved documentary draft (scriptgen.DRAFT_FILE)."""
    import scriptgen

    monkeypatch.setattr(scriptgen, "DRAFT_FILE", tmp_path / "_draft" / "pending_draft.json")


@pytest.fixture(autouse=True)
def _no_real_saved_scripts(tmp_path, monkeypatch):
    """No test may read or write the real data/pending_doc.json or data/pending_short.json (20 Nov 2026: the waiting Seven Sleepers film's script lives there, and a
    test that made a video without a topic would have resumed it or written over it)."""
    import run

    monkeypatch.setattr(run, "PENDING_DOC", tmp_path / "_iso_pending_doc.json")
    monkeypatch.setattr(run, "PENDING_SHORT", tmp_path / "_iso_pending_short.json")
