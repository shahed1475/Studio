import datetime as dt

import monetization

NOW = dt.datetime(2026, 10, 19, tzinfo=dt.timezone.utc)


def vid(i, views, seconds, days_ago):
    return {"id": i, "title": i, "views": views, "seconds": seconds, "published": (NOW - dt.timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")}


def snap(subs, recent=()):
    return {"date": "2026-10-19", "subscribers": subs, "views": sum(v["views"] for v in recent), "videos": len(recent), "recent": list(recent)}


def test_empty_channel_is_zero_everywhere_and_says_to_publish_first():
    p = monetization.progress(snap(0), NOW, ready=3)
    assert p["subs"] == 0 and p["uploads_90d"] == 0 and p["shorts_views_90d"] == 0
    assert p["early"]["subs"] == {"have": 0, "need": 500, "pct": 0}
    assert p["full"]["subs"]["need"] == 1000 and p["full"]["shorts_views"]["need"] == 10_000_000
    assert p["watch_hours"] is None  # the public API cannot tell; needs the Analytics permission
    assert "3 videos" in p["next"][0] and "not on YouTube" in p["next"][0]


def test_counts_only_the_last_90_days_and_splits_shorts():
    recent = [vid("a", 1000, 45, 10), vid("b", 2000, 55, 100), vid("c", 500, 600, 5), vid("d", 300, 30, 80)]
    p = monetization.progress(snap(250, recent), NOW)
    assert p["uploads_90d"] == 3  # b is older than 90 days
    assert p["shorts_views_90d"] == 1300  # a and d: Shorts inside 90 days
    assert p["early"]["subs"]["pct"] == 50 and p["early"]["uploads"] == {"have": 3, "need": 3, "pct": 100}


def test_percentages_cap_at_100_and_unknown_hours_are_not_guessed():
    p = monetization.progress(snap(5000, [vid("a", 20_000_000, 50, 3)]), NOW)
    assert p["early"]["subs"]["pct"] == 100 and p["full"]["shorts_views"]["pct"] == 100
    assert p["watch_hours"] is None and p["early"]["watch_hours"]["have"] is None


def test_next_steps_name_the_nearest_gap_in_plain_words():
    p = monetization.progress(snap(400, [vid("a", 100, 50, 3), vid("b", 100, 50, 4), vid("c", 100, 50, 5)]), NOW)
    text = " ".join(p["next"])
    assert "100 more subscribers" in text and "first step" in text
    done = monetization.progress(snap(1200, [vid("a", 11_000_000, 50, 3)] * 3), NOW)
    assert "apply" in " ".join(done["next"]).lower()


def test_rule_note_marks_the_february_2027_change_as_unconfirmed():
    assert "1 February 2027" in monetization.progress(snap(0), NOW)["note"] and "check" in monetization.progress(snap(0), NOW)["note"].lower()


def test_view_has_progress_for_dashboard(tmp_path, monkeypatch):
    import agentlog, dashboard, growth, strategy, agent, discover, editprofile, channelwatch, config, json

    monkeypatch.setattr(agentlog, "FILE", tmp_path / "e.jsonl")
    monkeypatch.setattr(growth, "DIR", tmp_path / "own")
    monkeypatch.setattr(strategy, "FILE", tmp_path / "s.json")
    monkeypatch.setattr(agent, "REPORTS", tmp_path / "r")
    monkeypatch.setattr(agent, "CONFIG_FILE", tmp_path / "a.json")
    monkeypatch.setattr(discover, "FILE", tmp_path / "d.json")
    monkeypatch.setattr(editprofile, "FILE", tmp_path / "p.json")
    monkeypatch.setattr(channelwatch, "REF_FILE", tmp_path / "refs.json")
    monkeypatch.setattr(config, "OUT", tmp_path / "out")
    (tmp_path / "out" / "v1").mkdir(parents=True)
    (tmp_path / "out" / "v1" / "meta.json").write_text(json.dumps({"review": {"verdict": "pass"}, "approved": True}))
    assert dashboard.agent_view()["monetization"] is None  # no snapshot yet
    growth.DIR.mkdir(parents=True)
    (growth.DIR / "2026-10-19.json").write_text(json.dumps(snap(10)))
    view = dashboard.agent_view()["monetization"]
    assert view["subs"] == 10 and "1 video" in view["next"][0]
