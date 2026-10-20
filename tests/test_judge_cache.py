import datetime as dt

import footage
import freemodels
import llm
import pytest

NOW = dt.datetime(2026, 10, 19, 12, 0, tzinfo=dt.timezone.utc)


@pytest.fixture(autouse=True)
def iso(tmp_path, monkeypatch):
    monkeypatch.setattr(footage, "JUDGE_CACHE", tmp_path / "judge.json")
    monkeypatch.setattr(freemodels, "FILE", tmp_path / "free.json")


def test_each_title_is_judged_once_per_topic():
    asked = []

    def ask(titles):
        asked.append(list(titles))
        return [t for t in titles if "delphi" in t.lower()]

    judge = footage.cached_judge("Oracle of Delphi", ask)
    assert judge(["Delphi temple.jpg", "Apollo 11.jpg"]) == ["Delphi temple.jpg"]
    assert judge(["Delphi temple.jpg", "Apollo 11.jpg", "Delphi theatre.jpg"]) == ["Delphi temple.jpg", "Delphi theatre.jpg"]
    assert asked == [["Delphi temple.jpg", "Apollo 11.jpg"], ["Delphi theatre.jpg"]]  # the second call asks only about the new title
    assert footage.cached_judge("Oracle of Delphi", lambda t: pytest.fail("known"))(["Apollo 11.jpg"]) == []  # a later run remembers too


def test_failure_keeps_everything_and_is_not_remembered():
    def boom(titles):
        raise RuntimeError("model down")

    assert footage.cached_judge("T", boom)(["a.jpg", "b.jpg"]) == ["a.jpg", "b.jpg"]
    asked = []
    footage.cached_judge("T", lambda t: asked.append(t) or [])(["a.jpg"])
    assert asked == [["a.jpg"]]  # the failed verdict was not stored


def test_topics_do_not_share_verdicts():
    footage.cached_judge("Delphi", lambda t: [])(["x.jpg"])
    asked = []
    footage.cached_judge("Pied Piper", lambda t: asked.append(t) or t)(["x.jpg"])
    assert asked == [["x.jpg"]]


def test_empty_list_asks_nothing():
    assert footage.cached_judge("T", lambda t: pytest.fail("no titles"))([]) == []


# ---- free quota is shared fairly between big and small jobs ----
class Resp:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return {"data": self.data}


@pytest.fixture
def router(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "CONFIG_FILE", tmp_path / "llm.json")
    monkeypatch.setattr(llm, "USAGE_FILE", tmp_path / "usage.json")
    monkeypatch.setattr(llm, "api_key", lambda: "k")
    llm.save_config({**llm.load_config(), "free": True, "free_daily_limit": 10})
    freemodels.refresh(NOW, get=lambda *a, **k: Resp([{"id": "a/m:free", "context_length": 65536, "pricing": {"prompt": "0", "completion": "0"},
                                                       "architecture": {"output_modalities": ["text"]}, "supported_parameters": ["response_format"]}]))
    llm._last_free.clear()
    monkeypatch.setattr(llm, "_post", lambda payload, key: {"choices": [{"message": {"content": "{}"}}], "usage": {}})


def test_small_jobs_stop_at_their_share_but_script_can_use_the_rest(router):
    used = lambda role: llm.chat("p", role, fallback=lambda p: {"local": 1}, now=NOW) != {"local": 1}
    assert [used("cheap") for _ in range(6)] == [True, True, True, True, False, False]  # 40% of 10 = 4
    assert freemodels.requests_today(NOW) == 4
    assert all(used("script") for _ in range(6)) and not used("script")  # the other 6 go to the script, then the limit
    assert freemodels.requests_today(NOW) == 10
    assert freemodels.requests_today(NOW, "cheap") == 4


def test_review_is_never_answered_by_a_free_model(router):
    assert llm.chat("p", "review", fallback=lambda p: {"local": 1}, now=NOW) == {"local": 1}  # only the (off by default) local fallback may stand in
