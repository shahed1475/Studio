import discover


class Req:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return self.data


class FakeYT:
    """search() returns the ids in `hits` for every query; channels() looks up `stats`."""

    def __init__(self, hits, stats):
        self.hits, self.stats, self.searches = hits, stats, 0

    def search(self):
        outer = self

        class S:
            def list(self, **kw):
                outer.searches += 1
                assert kw["type"] == "channel" and kw["regionCode"] == "US"
                return Req({"items": [{"id": {"channelId": i}} for i in outer.hits]})

        return S()

    def channels(self):
        outer = self

        class C:
            def list(self, **kw):
                ids = kw["id"].split(",")
                return Req({"items": [{"id": i, "snippet": {"title": f"T-{i}", "description": "d"},
                                       "statistics": outer.stats[i]} for i in ids if i in outer.stats]})

        return C()


def st(subs, views, videos):
    return {"subscriberCount": str(subs), "viewCount": str(views), "videoCount": str(videos)}


def test_score_zero_below_10k_subs():
    assert discover.score({"subscribers": 9999, "views": 10**6, "videos": 10}) == 0
    assert discover.score({"subscribers": 10000, "views": 1000, "videos": 10}) == 100


def test_search_excludes_known_ids():
    yt = FakeYT(["A", "B"], {"A": st(50000, 5000000, 50), "B": st(50000, 5000000, 50)})
    got = discover.search(yt, ["q"], exclude={"A"})
    assert [c["id"] for c in got] == ["B"]


def test_search_drops_small_and_hidden_channels():
    yt = FakeYT(["A", "B"], {"A": st(500, 5000000, 50), "B": {"hiddenSubscriberCount": True, "viewCount": "9", "videoCount": "1"}})
    assert discover.search(yt, ["q"], exclude=set()) == []


def test_search_caps_calls_at_six():
    yt = FakeYT(["A"], {"A": st(50000, 5000000, 50)})
    discover.search(yt, [f"q{i}" for i in range(10)], exclude=set())
    assert yt.searches == 6


def test_fit_niche_failure_marks_unchecked():
    def boom(prompt):
        raise RuntimeError("down")

    got = discover.fit_niche([{"id": "A", "title": "x"}], boom)
    assert got == [{"id": "A", "title": "x", "unchecked": True}]


def test_fit_niche_filters_by_model_answer():
    got = discover.fit_niche([{"id": "A", "title": "x"}, {"id": "B", "title": "y"}], lambda p: {"fits": ["B"]})
    assert [c["id"] for c in got] == ["B"]


def test_run_caps_at_15_keeping_best_and_never_returns_own_or_refs(tmp_path, monkeypatch):
    monkeypatch.setattr(discover, "FILE", tmp_path / "d.json")
    import agentlog

    monkeypatch.setattr(agentlog, "FILE", tmp_path / "events.jsonl")
    ids = [f"UC{i:022d}" for i in range(20)]
    stats = {i: st(20000, 1000 * (n + 1) * 100, 100) for n, i in enumerate(ids)}
    yt = FakeYT(ids, stats)
    new = discover.run(yt, own_id=ids[19], refs=[ids[18]], chat=lambda p: {"fits": ids})
    saved = discover.load()
    assert len(saved) == discover.MAX_FOUND == 15
    assert ids[19] not in [c["id"] for c in saved] and ids[18] not in [c["id"] for c in saved]
    assert saved[0]["id"] == ids[17]  # best remaining score first
    assert {c["id"] for c in new} == {c["id"] for c in saved}
    assert discover.run(yt, own_id=ids[19], refs=[ids[18]], chat=lambda p: {"fits": ids}) == []  # nothing new the second time
