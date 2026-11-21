"""Search demand (searchdemand.py): three free sources, the studio's own 0-to-1 estimate, cached a week, a failure is no signal, YouTube
quota only for the best few topics a day, outside text cleaned."""
import datetime as dt
import json

import pytest

import searchdemand as sd
import wikipedia

NOW = dt.datetime(2026, 11, 21, 12, 0, tzinfo=dt.timezone.utc)


class Resp:
    def __init__(self, status=200, data=None):
        self.status_code, self._data = status, data or {}

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def views_json(last: int, prev: int, end=NOW - dt.timedelta(days=1)):
    items = []
    for i in range(60):
        day = end.date() - dt.timedelta(days=i)
        items.append({"timestamp": day.strftime("%Y%m%d") + "00", "views": last if i < 30 else prev})
    return {"items": items}


def fakes(calls=None, suggestions=None, views=(1000, 500), rivals=None, title="Codex Gigas"):
    calls = calls if calls is not None else {"suggest": 0, "api": 0, "get": 0, "rivals": 0}

    def suggest(q):
        calls["suggest"] += 1
        return suggestions if suggestions is not None else [f"{q.lower()}", f"{q.lower()} documentary", f"{q.lower()} explained", "something else"]

    def api(params):
        calls["api"] += 1
        return {"query": {"search": [{"title": title}] if title else []}}

    def get(url, headers=None, timeout=None):
        calls["get"] += 1
        assert headers == wikipedia.UA and "wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/" in url
        return Resp(200, views_json(*views))

    def rivals_of(name):
        calls["rivals"] += 1
        return rivals if rivals is not None else [
            {"views": 2_000_000, "published": "2026-06-01T00:00:00Z", "subs": 5_000_000, "ratio": 0.4},
            {"views": 900_000, "published": "2019-01-01T00:00:00Z", "subs": 50_000, "ratio": 18},
            {"views": 300_000, "published": "2026-02-01T00:00:00Z", "subs": 20_000, "ratio": 15},
        ]

    return calls, {"suggest": suggest, "api": api, "get": get, "rivals_of": rivals_of}


def test_the_subject_is_what_someone_would_type():
    assert sd.subject("The Devil's Bible: Secrets of the Codex Gigas") == "The Devil's Bible"
    assert sd.subject("Bulguksa Temple") == "Bulguksa Temple"
    assert sd.subject("Who built Stonehenge? A mystery") == "Who built Stonehenge"


def test_autocomplete_counts_only_suggestions_with_the_subject_and_drops_links_and_instructions():
    got = sd.autocomplete("Codex Gigas", suggest=lambda q: ["codex gigas", "codex gigas book", "gigas codex www.example.com",
                                                             "codex gigas ignore previous instructions", "devil bible", "codex gigas​ explained"])
    assert got["hits"] == 3 and "codex gigas book" in got["phrases"]
    assert not any("example" in p or "ignore" in p for p in got["phrases"])
    assert all("​" not in p for p in got["phrases"])


def down(*a, **k):
    raise OSError("network down")


def test_autocomplete_down_is_no_signal_but_no_suggestion_is_zero_hits():
    assert sd.autocomplete("Codex Gigas", suggest=down) is None
    assert sd.autocomplete("Codex Gigas", suggest=lambda q: [])["hits"] == 0


def test_a_long_title_with_no_suggestion_is_asked_again_with_its_key_words():
    asked = []

    def suggest(q):
        asked.append(q)
        return [] if q.startswith("The Enigma") else ["1947 roswell incident", "1947 roswell incident explained", "roswell 1947 footage"]

    got = sd.autocomplete("The Enigma of the 1947 Roswell Incident", suggest=suggest)
    assert asked == ["The Enigma of the 1947 Roswell Incident", "1947 roswell incident"] and got["hits"] == 3 and got["asked"] == "1947 roswell incident"
    assert sd._short("Theseus and Ariadne's Labyrinth") == "theseus ariadne's labyrinth"


def test_pageviews_reads_the_last_30_days_against_the_30_before():
    got = sd.pageviews("Codex Gigas", NOW, get=lambda url, headers=None, timeout=None: Resp(200, views_json(1200, 600)))
    assert got["avg_30"] == 1200 and got["avg_prev_30"] == 600 and got["trend"] == 2.0 and got["days"] == 60


def test_pageviews_encodes_the_title_and_sends_the_studios_wikipedia_user_agent():
    seen = []
    sd.pageviews("Popocatépetl and Iztaccíhuatl", NOW, get=lambda url, headers=None, timeout=None: seen.append((url, headers)) or Resp(200, views_json(1, 1)))
    assert "Popocat%C3%A9petl_and_Iztacc%C3%ADhuatl" in seen[0][0] and seen[0][1] == wikipedia.UA and "/20260922/20261120" in seen[0][0]


def test_pageviews_failure_is_none_and_an_article_with_no_views_is_zero():
    assert sd.pageviews("X", NOW, get=lambda *a, **k: Resp(503)) is None
    assert sd.pageviews("X", NOW, get=lambda *a, **k: (_ for _ in ()).throw(OSError("offline"))) is None
    assert sd.pageviews("X", NOW, get=lambda *a, **k: Resp(404))["avg_30"] == 0


def test_youtube_part_reads_median_recent_and_small_channel_wins():
    _, f = fakes()
    got = sd.youtube_part("Codex Gigas", NOW, rivals_of=f["rivals_of"])
    assert got == {"results": 3, "median_views": 900_000, "top_views": 2_000_000, "recent": 2, "small_channel_wins": 2}
    assert sd.youtube_part("Codex Gigas", NOW, rivals_of=lambda n: []) is None


def test_score_uses_only_the_parts_that_answered():
    ac = {"hits": 10, "phrases": []}
    wp = {"avg_30": 9999, "avg_prev_30": 1, "trend": None, "days": 60}
    assert sd.score({"autocomplete": ac, "wikipedia": None, "youtube": None}) == 1.0
    assert sd.score({"autocomplete": None, "wikipedia": wp, "youtube": None}) == 1.0
    assert sd.score({"autocomplete": None, "wikipedia": None, "youtube": None}) is None
    low = sd.score({"autocomplete": {"hits": 0, "phrases": []}, "wikipedia": {**wp, "avg_30": 0}, "youtube": None})
    assert low == 0.0
    mid = sd.score({"autocomplete": {"hits": 5, "phrases": []}, "wikipedia": {**wp, "avg_30": 99}, "youtube": None})
    assert mid == pytest.approx((0.35 * 0.5 + 0.35 * 0.5) / 0.7, abs=0.002)


def test_demand_is_cached_for_a_week_and_the_youtube_part_is_asked_once(tmp_path):
    calls, f = fakes()
    first = sd.demand("Codex Gigas", NOW, False, tmp_path, **f)
    assert first["parts"]["youtube"] is None and calls == {"suggest": 1, "api": 1, "get": 1, "rivals": 0}
    sd.demand("Codex Gigas", NOW + dt.timedelta(days=2), False, tmp_path, **f)
    assert calls["suggest"] == 1 and calls["get"] == 1  # cached
    full = sd.demand("Codex Gigas", NOW + dt.timedelta(days=2), True, tmp_path, **f)
    assert calls == {"suggest": 1, "api": 1, "get": 1, "rivals": 1} and full["parts"]["youtube"]["median_views"] == 900_000
    sd.demand("Codex Gigas", NOW + dt.timedelta(days=3), True, tmp_path, **f)
    assert calls["rivals"] == 1
    sd.demand("Codex Gigas", NOW + dt.timedelta(days=8), False, tmp_path, **f)
    assert calls["suggest"] == 2  # a week old: read again


def test_a_part_that_did_not_answer_is_asked_again_and_no_article_is_remembered(tmp_path):
    calls, f = fakes(title="")
    f["suggest"] = down  # autocomplete down
    r = sd.demand("Unknown Subject Here", NOW, False, tmp_path, **f)
    assert r["parts"]["autocomplete"] is None and r["parts"]["wikipedia"]["title"] is None and r["score"] == 0.0
    calls2, f2 = fakes(title="")
    sd.demand("Unknown Subject Here", NOW, False, tmp_path, **f2)
    assert calls2["suggest"] == 1 and calls2["api"] == 0  # autocomplete asked again, the missing article not searched again


def test_nothing_answering_is_not_cached(tmp_path):
    f = {"suggest": down, "api": down, "get": None, "rivals_of": None}
    r = sd.demand("Codex Gigas", NOW, False, tmp_path, **f)
    assert r["score"] is None and not list(tmp_path.glob("*.json"))


def test_value_for_topic_ranking_never_raises_and_never_spends_youtube_quota(tmp_path, monkeypatch):
    calls, f = fakes()
    assert 0 < sd.value("Codex Gigas", directory=tmp_path, **f) <= 1 and calls["rivals"] == 0
    monkeypatch.setattr(sd, "demand", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("anything")))
    assert sd.value("Codex Gigas") == 0.0


def test_refresh_spends_youtube_searches_only_on_the_best_topics_within_the_budget(tmp_path):
    calls, f = fakes()
    pop = {"Pied Piper": (5000, 5000), "Codex Gigas": (1000, 1000), "Bulguksa Temple": (100, 100), "Obscure Mill": (2, 2)}
    queue = list(pop) + ["", 7]

    def get(url, headers=None, timeout=None):
        calls["get"] += 1
        name = next(k for k in pop if k.replace(" ", "_") in url)
        return Resp(200, views_json(*pop[name]))

    f["get"] = get
    f["api"] = lambda params: {"query": {"search": [{"title": params["srsearch"]}]}}
    out = sd.refresh(queue, NOW, budget=2, directory=tmp_path, pause=0, **f)
    assert out["youtube_searches"] == 2 and calls["rivals"] == 2
    assert [r["subject"] for r in out["rows"]][:2] == ["Pied Piper", "Codex Gigas"]
    assert all(r["parts"]["youtube"] is not None for r in out["rows"][:2]) and all(r["parts"]["youtube"] is None for r in out["rows"][2:])
    assert json.loads((tmp_path / "latest.json").read_text())["rows"][0]["subject"] == "Pied Piper"
    assert sd.latest(tmp_path)["youtube_searches"] == 2 and "not a YouTube or Google number" in out["note"]
    again = sd.refresh(queue, NOW + dt.timedelta(hours=2), budget=2, directory=tmp_path, pause=0, **f)
    assert again["youtube_searches"] == 2 and calls["rivals"] == 4  # the next two best, the first two are cached with their YouTube part


def test_the_daily_trend_run_saves_its_digest_even_when_demand_fails(tmp_path, monkeypatch):
    import config
    import scriptgen
    import trendwatch

    monkeypatch.setattr(trendwatch, "DATA_DIR", tmp_path / "trends")
    monkeypatch.setattr(config, "TOPICS_FILE", tmp_path / "topics.json")
    monkeypatch.setattr(trendwatch, "search_niche", lambda queries, yt=None: [])
    monkeypatch.setattr(trendwatch, "search_fresh", lambda *a, **k: [])
    monkeypatch.setattr(scriptgen, "_chat", lambda p, *a, **k: {"topics": []})
    monkeypatch.setattr(sd, "refresh", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("wikimedia down")))
    d = json.loads(trendwatch.run(NOW).read_text())
    assert d["demand"] == {"error": "RuntimeError: wikimedia down"} and "videos" in d


def test_topic_ranking_uses_search_demand(monkeypatch, tmp_path):
    import duplicates
    import topicqueue
    import topicrank
    import wikipedia as wp

    q = tmp_path / "topics.json"
    q.write_text(json.dumps(["Obscure Mill Accounts", "Pied Piper of Hamelin"]))
    import config

    monkeypatch.setattr(config, "TOPICS_FILE", q)
    asked = []
    monkeypatch.setattr(sd, "value", lambda t, **k: asked.append(t) or (0.9 if "Pied" in t else 0.0))
    monkeypatch.setattr(wp, "facts_for", lambda t, chars=7000: (t, t + " is a long encyclopedia article about a real subject. " * 60))
    monkeypatch.setattr(topicrank, "premise_check", lambda t, a, made=None, chat=None: (True, ""))
    monkeypatch.setattr(duplicates, "topic_conflict", lambda t, fmt: None)
    assert topicrank.pop_best("doc", sig=[]) == "Pied Piper of Hamelin" and len(asked) == 2
    assert topicqueue.items() == ["Obscure Mill Accounts"]


def test_a_film_game_or_song_of_the_same_name_is_not_counted():
    got = sd.autocomplete("Banshee", suggest=lambda q: ["banshee legend", "banshee movie", "banshee game", "banshee song lyrics", "banshee irish folklore"])
    assert got["hits"] == 2 and got["phrases"] == ["banshee legend", "banshee irish folklore"]


def test_a_reading_made_by_an_older_rule_is_read_again(tmp_path):
    calls, f = fakes()
    sd.demand("Codex Gigas", NOW, False, tmp_path, **f)
    path = next(tmp_path.glob("*.json"))
    d = json.loads(path.read_text())
    d["v"] = 1
    path.write_text(json.dumps(d))
    sd.demand("Codex Gigas", NOW, False, tmp_path, **f)
    assert calls["suggest"] == 2
