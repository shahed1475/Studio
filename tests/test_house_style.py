import autopilot
import llm
import risk
import run


def cfg(**k):
    base = {"enabled": True, "doc": {"clips": 4, "budget": 1.5}, "short": {"clips": 1, "budget": 0.5}, "min_credit": 8.0}
    return {"house_style": {**base, **k}}


def fund(monkeypatch, credit, config=None):
    monkeypatch.setattr(autopilot, "load_config", lambda: config if config is not None else cfg())
    monkeypatch.setattr(llm, "api_key", lambda: "k")
    monkeypatch.setattr(risk, "credit_left", lambda key, *a, **k: credit)


def test_autopilot_adds_the_realistic_look_motion_and_clips_to_a_new_documentary_when_the_account_can_pay(monkeypatch):
    """The owner's choice (30 Oct 2026): every new video looks like the Lost Army film: realistic AI scenes, a few real moving clips, free camera motion on the rest, chapter cards
    and date badges on a documentary, and the shorter voice tail."""
    fund(monkeypatch, 12.0)
    got = run._house_style("doc")
    assert got == {"art_style": "photo", "animate": 4, "animate_budget": 1.5, "art_first": True, "house_style": True, "parallax": True, "graphics": True, "voice_tail": 0.15}
    short = run._house_style("short")
    assert short == {"art_style": "photo", "animate": 1, "animate_budget": 0.5, "art_first": True, "house_style": True, "parallax": True}


def test_the_look_can_be_set_back_to_the_3d_storybook_style_and_an_unknown_look_falls_back_to_the_default(monkeypatch):
    fund(monkeypatch, 12.0, cfg(look="3d"))
    assert run._house_style("doc") == {"art_style": "3d", "animate": 4, "animate_budget": 1.5, "art_first": True, "house_style": True}
    fund(monkeypatch, 12.0, cfg(look="oil painting"))
    assert run._house_style("doc")["art_style"] == "photo"


def test_nothing_is_added_when_it_is_off_the_credit_is_low_or_unknown_or_the_kind_is_not_listed(monkeypatch):
    fund(monkeypatch, 12.0, cfg(enabled=False))
    assert run._house_style("doc") == {}
    fund(monkeypatch, 7.99)
    assert run._house_style("doc") == {}  # the stricter floor: animation is not worth a stopped render
    fund(monkeypatch, None)
    assert run._house_style("doc") == {}  # an unreadable balance counts as not funded here
    fund(monkeypatch, 12.0, cfg(short={}))
    assert run._house_style("short") == {} and run._house_style("doc")["animate"] == 4


def test_only_a_new_video_gets_the_house_style_never_a_redo_a_repair_or_a_video_that_chose_its_own(monkeypatch, tmp_path):
    fund(monkeypatch, 12.0)
    assert run._apply_house_style({"title": "t"}, "doc", None)["art_style"] == "photo"
    assert "art_style" not in run._apply_house_style({"title": "t"}, "doc", tmp_path)  # a folder means a re-render in place (redo, repair)
    assert run._apply_house_style({"title": "t", "art_style": "3d", "animate": 8}, "doc", None)["animate"] == 8  # a remake's own settings win
    assert "house_style" not in run._apply_house_style({"title": "t", "art_style": "3d"}, "doc", None)


def test_the_setting_is_part_of_autopilots_known_settings_and_off_by_default():
    assert autopilot.DEFAULTS["house_style"]["enabled"] is False and autopilot.DEFAULTS["house_style"]["min_credit"] >= 8.0
    assert autopilot.DEFAULTS["house_style"]["look"] == "photo"
