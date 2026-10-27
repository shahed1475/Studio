import datetime as dt
from pathlib import Path

import governor

NOW = dt.datetime(2026, 10, 27, 12, 0, tzinfo=dt.timezone.utc)


def at(days, hours=0):
    return (NOW + dt.timedelta(days=days, hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def v(fmt="doc", when=0, **kw):
    return {"format": fmt, "publish_at": at(when), **kw}


def vs_of(metas):
    return [(Path(f"v{i}"), m) for i, m in enumerate(metas)]


OPENINGS = ["alpha river storm", "silver mountain bell", "a lighthouse keeper once", "deep under frozen lake", "nobody remembers the harbour", "three sisters crossed",
            "the map was wrong", "long before the road", "an old bridge refused", "salt on the windowsill"]


def varied(i, fmt="doc", when=None, topic=None, lines=None, **kw):
    """A video whose structure, opening and topic differ from every other one."""
    n = lines if lines is not None else 10 + i * 3
    return {"format": fmt, "publish_at": at(-i if when is None else when), "made_at": at(-i), "topic": topic or f"subject{'abcdefghij'[i]}{'klmnopqrst'[i]}",
            "lines": [{"text": OPENINGS[i]}] + [{"text": "line"}] * n, "slug": f"s{i}", **kw}


def mostly_one_structure(count=5):
    """Eight videos, `count` of them cut to the same shape, every opening and topic different."""
    return [varied(i, lines=13 if i < count else 40 + i * 5) for i in range(8)]


# ---- window_load: the busiest real 7-day span, not 14 days added together
def test_window_load_counts_a_true_seven_day_span_not_fourteen_days():
    daily = [v(when=d) for d in range(-7, 7)]  # one a day for two weeks
    assert governor.window_load(daily, NOW) == 7


def test_window_load_finds_a_burst_and_ignores_held_and_undated_videos():
    burst = [v(when=1, hold=True)] + [v(when=1 + i / 10) for i in range(5)] + [{"format": "doc"}, {"format": "doc", "publish_at": "garbage"}]
    assert governor.window_load(burst, NOW) == 5
    assert governor.window_load([], NOW) == 0


def test_window_load_uses_the_upload_time_when_there_is_no_publish_time():
    assert governor.window_load([{"format": "short", "uploaded_at": at(-2)}, v("short", -1)], NOW) == 2


# ---- caps: base, tighten only, never raised
def test_caps_are_the_base_when_there_is_nothing_to_worry_about():
    c = governor.caps([], NOW)
    assert (c["doc"], c["short"], c["level"]) == (3, 7, "ok") and c["why"] == []


def test_caps_never_go_above_the_base_even_when_everything_is_varied():
    c = governor.caps(vs_of([varied(i) for i in range(8)]), NOW)
    assert c["doc"] <= 3 and c["short"] <= 7


def test_the_owner_can_change_the_base_and_the_tightening_still_applies():
    assert governor.caps([], NOW, {"doc": 5, "short": 9})["doc"] == 5
    assert governor.caps(vs_of(mostly_one_structure()), NOW, {"doc": 5, "short": 9})["doc"] == 4  # one shared structure: documentaries minus one


def test_one_shared_structure_cuts_documentaries_by_one_and_says_why():
    c = governor.caps(vs_of(mostly_one_structure()), NOW)
    assert c["doc"] == 2 and c["short"] == 7 and c["level"] == "watch" and any("structure" in w for w in c["why"])


def test_near_identical_openings_cut_both_formats():
    twins = [varied(i) for i in range(6)]
    twins[1]["lines"][0]["text"] = twins[0]["lines"][0]["text"]  # two openings alike
    c = governor.caps(vs_of(twins), NOW)
    assert c["doc"] == 2 and c["short"] == 6 and any("opening" in w for w in c["why"])


def test_repetition_at_the_act_level_freezes_new_videos():
    twins = [varied(i) for i in range(8)]
    for t in twins[:4]:
        t["lines"][0]["text"] = "the very same opening line for everyone"
    c = governor.caps(vs_of(twins), NOW)
    assert (c["doc"], c["short"], c["level"]) == (0, 0, "act")


def test_one_theme_in_half_of_the_recent_stories_cuts_both_formats():
    korea = [varied(i, topic="Hong Gildong legend") for i in range(5)] + [varied(i) for i in range(5, 8)]
    c = governor.caps(vs_of(korea), NOW)
    assert c["doc"] < 3 and c["short"] < 7 and any("theme" in w for w in c["why"])


def test_a_short_clipped_from_a_documentary_does_not_count_as_a_second_story():
    docs = [varied(i) for i in range(1, 8)]
    base = varied(0, topic="Mami Wata")
    clip = {**varied(0, fmt="short", topic="Mami Wata"), "slug": "clip", "source_doc": "s0"}
    assert governor.theme_share(vs_of([base, clip] + docs)) < 0.5


def test_a_tiny_or_broken_record_set_never_crashes_and_never_tightens():
    for vs in ([], vs_of([{}]), vs_of([{"format": "doc"}] * 3), [(Path("x"), {"lines": None, "topic": None})]):
        assert governor.caps(vs, NOW)["doc"] == 3


# ---- allowed: one more video must keep every 7-day window within the cap
CAPS = {"doc": 3, "short": 7, "level": "ok", "why": []}


def test_a_fourth_documentary_in_a_week_is_not_allowed_but_the_next_week_is():
    week = [v("doc", d) for d in (1, 3, 5)]
    assert governor.allowed(week, "doc", NOW + dt.timedelta(days=6), CAPS) is False
    assert governor.allowed(week, "doc", NOW + dt.timedelta(days=8, hours=1), CAPS) is True


def test_formats_are_counted_separately_and_held_videos_do_not_count():
    week = [v("doc", d) for d in (1, 2)] + [v("doc", 3, hold=True)] + [v("short", d) for d in range(1, 7)]
    assert governor.allowed(week, "doc", NOW + dt.timedelta(days=4), CAPS) is True
    assert governor.allowed(week, "short", NOW + dt.timedelta(days=7), CAPS) is True
    assert governor.allowed(week + [v("short", 7)], "short", NOW + dt.timedelta(days=6), CAPS) is False


def test_a_slot_between_two_busy_weeks_counts_both_sides():
    around = [v("doc", d) for d in (0, 1)] + [v("doc", 5)]
    assert governor.allowed(around, "doc", NOW + dt.timedelta(days=3), CAPS) is False


def test_a_frozen_cap_allows_nothing_and_no_caps_allows_everything():
    assert governor.allowed([], "doc", NOW, {**CAPS, "doc": 0}) is False
    assert governor.allowed([v("doc", d) for d in range(10)], "doc", NOW + dt.timedelta(days=3), None) is True


# ---- hooks: planner, scheduler, Risks card, config
import json

import autopilot
import config
import planner
import risk

SLOTS = [{"day": d, "time": "18:00"} for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")]
PCFG = {**autopilot.DEFAULTS, "slots": SLOTS, "short_slots": SLOTS, "review_window_hours": 2, "prepare_hours": 400}


def pvid(slug, fmt="doc", **kw):
    return {"slug": slug, "format": fmt, "verdict": None, "approved": False, "hold": False, "video_id": None, "publish_at": None, "fix_attempts": 0, "title": slug, **kw}


def test_planner_pauses_slots_beyond_the_weekly_cap_and_makes_nothing_for_them():
    slots = planner.slot_times(SLOTS, NOW)
    sched = [pvid(f"d{i}", publish_at=slots[i].strftime("%Y-%m-%dT%H:%M:%SZ"), approved=True, verdict="pass") for i in range(3)]
    free = {**PCFG, "_caps": None}
    capped = {**PCFG, "_caps": {"doc": 3, "short": 7, "level": "ok", "why": []}}
    row = lambda cfg: [r for r in planner.rows(cfg, sched, NOW) if r["format"] == "doc"][3]["status"]
    assert row(free) == "empty" and row(capped) == "paused"
    assert planner.needs(capped, sched, NOW)["doc"] < planner.needs(free, sched, NOW)["doc"]


def test_a_paused_slot_is_not_taken_by_a_passed_video():
    ready = [pvid("r", verdict="pass", approved=True)]
    frozen = {**PCFG, "_caps": {"doc": 0, "short": 0, "level": "act", "why": []}}
    assert all(r["status"] == "paused" or r["status"] == "too_soon" for r in planner.rows(frozen, ready, NOW))


def _folder(tmp, slug, fmt, **meta):
    d = tmp / slug
    d.mkdir()
    (d / "meta.json").write_text(json.dumps({"title": slug, "format": fmt, "review": {"verdict": "pass", "checks": []}, "approved": True, "topic": slug, **meta}))


def test_do_schedule_skips_slots_that_would_pass_the_weekly_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path)
    for i, t in enumerate((1, 2, 3)):
        _folder(tmp_path, f"old{i}", "doc", publish_at=at(t, 6))
    _folder(tmp_path, "new", "doc")
    cfg = {**autopilot.DEFAULTS, "slots": SLOTS, "review_window_hours": 2, "_caps": {"doc": 3, "short": 7, "level": "ok", "why": []}}
    autopilot.do_schedule("new", cfg, NOW)
    when = dt.datetime.fromisoformat(json.loads((tmp_path / "new" / "meta.json").read_text())["publish_at"].replace("Z", "+00:00"))
    assert when > NOW + dt.timedelta(days=8, hours=-6)  # the first slot after the busy week, not tomorrow
    _folder(tmp_path, "free", "doc")
    autopilot.do_schedule("free", {**cfg, "_caps": None}, NOW)
    assert json.loads((tmp_path / "free" / "meta.json").read_text())["publish_at"] < json.loads((tmp_path / "new" / "meta.json").read_text())["publish_at"]


def test_governed_adds_caps_and_leaves_the_config_alone_when_off_or_unreadable(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path)
    monkeypatch.setattr(config, "ROOT", tmp_path)
    cfg = dict(autopilot.DEFAULTS)
    assert autopilot.governed(cfg, NOW)["_caps"]["doc"] == 3
    assert "_caps" not in autopilot.governed({**cfg, "governor": {"enabled": False}}, NOW)
    monkeypatch.setattr(risk, "videos", lambda *a, **k: 1 / 0)
    assert "_caps" not in autopilot.governed(cfg, NOW)


def test_governed_records_a_change_once_and_says_why(tmp_path, monkeypatch):
    import agentlog

    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(agentlog, "FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(agentlog.subprocess, "run", lambda *a, **k: None)
    c = {"doc": 2, "short": 6, "level": "watch", "why": ["2 pair(s) of near-identical openings: one fewer of each a week"]}
    governor.record(c, NOW)
    governor.record(c, NOW)
    events = [e for e in agentlog.recent() if e["title"].startswith("Autopilot changed its weekly pace")]
    assert len(events) == 1 and "near-identical" in events[0]["detail"]
    assert json.loads((tmp_path / "data" / "governor.json").read_text())["doc"] == 2


def test_the_risks_card_counts_the_busiest_real_week_and_agrees_with_the_governor():
    daily = [{"format": "doc", "publish_at": at(d), "made_at": at(d), "lines": [{"text": OPENINGS[abs(d) % 10] + str(d)}] + [{"text": "l"}] * (10 + abs(d) * 2)} for d in range(-7, 7)]
    row = risk.pattern(vs_of(daily), NOW)
    assert row["pace"] == 7 and row["level"] != "act" and risk.PACE_WATCH == governor.WATCH_ABOVE + 1
    burst = [{"format": "short", "publish_at": at(1, h)} for h in range(14)]
    assert risk.pattern(vs_of(burst), NOW)["level"] == "act"


def test_an_old_overloaded_week_does_not_block_a_slot_that_is_not_in_it():
    crowded = [v("doc", d) for d in (-20, -19, -18, -17)]  # already over the cap of 3, three weeks ago
    assert governor.allowed(crowded, "doc", NOW + dt.timedelta(days=2), CAPS) is True
