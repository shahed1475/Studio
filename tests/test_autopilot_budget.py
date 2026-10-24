import autopilot
from tests.test_autopilot import CFG, NOW, plan, state


def test_a_documentary_is_not_started_without_the_money_to_finish_it():
    assert ("make", None) in plan(state(cap_left=2.0))
    assert ("make", None) not in plan(state(cap_left=0.9))


def test_a_short_needs_far_less_than_a_documentary():
    cfg = {**CFG, "shorts": True}
    st = dict(state(cap_left=0.6), clippable=0)
    acts = plan(st, cfg)
    assert ("make_short", None) in acts or ("make_clip", None) in acts or all(a[0] != "make" for a in acts)
    assert ("make_short", None) not in plan(dict(state(cap_left=0.1), clippable=0), cfg)


def test_an_unknown_cap_does_not_block_work():
    assert ("make", None) in plan(state())


def test_what_the_cap_blocks_is_named_in_the_plan_notes():
    assert autopilot.can_afford("doc", 0.9) is False and autopilot.can_afford("doc", 1.4) is True
    assert autopilot.can_afford("short", 0.1) is False and autopilot.can_afford("short", 0.5) is True
    assert autopilot.can_afford("doc", None) is True


def _meta(root, slug, **kw):
    import json
    d = root / slug
    d.mkdir(parents=True)
    (d / "meta.json").write_text(json.dumps({"title": slug, "format": "short", "uploaded_at": "2026-10-19T05:00:00Z", **kw}))


def test_a_held_upload_does_not_use_up_the_days_pace_limit(tmp_path, monkeypatch):
    import config
    import upload
    monkeypatch.setattr(config, "OUT", tmp_path / "output")
    _meta(config.OUT, "held-old", video_id="a", hold=True, publish_at="2026-10-19T17:00:00Z")
    _meta(config.OUT, "live", video_id="b", publish_at="2026-10-19T16:00:00Z")
    assert upload.uploads_today(config.OUT, NOW) == 1
    st = autopilot.build_state(NOW, {**autopilot.load_config()})
    assert st["uploads_today"] == 1 and st["uploads_by_format"] == {"short": 1}
