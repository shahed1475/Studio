import json

import autopilot
import clipper
import config
import duplicates
import topicrank

NOW = autopilot.dt.datetime(2026, 10, 26, 12, 0, tzinfo=autopilot.dt.timezone.utc)


def video(root, slug, topic, fmt="short", source=None, **kw):
    d = root / slug
    d.mkdir(parents=True)
    meta = {"topic": topic, "format": fmt, "title": topic + " title", "sources": [f"Wikipedia: {source or topic} (CC BY-SA 4.0), retold in our own words"], "review": {"verdict": "pass"}, **kw}
    (d / "meta.json").write_text(json.dumps(meta))
    return d


def test_same_subject_ignores_generic_words_and_matches_variants_of_one_story():
    t = duplicates.tokens
    assert duplicates.same_subject(t("Thunderbird"), t("The Thunderbird: A Name That Keeps Flying")) and duplicates.same_subject(t("Hong Gildong"), t("Hong Gildong jeon"))
    assert not duplicates.same_subject(t("Korea's Gentle Water Dragons"), t("Hong Gildong Korean Novel")) and not duplicates.same_subject(t("Legend of the Story"), t("The Myth Mystery"))
    assert not duplicates.same_subject(t("Heungbu and Nolbu"), t("Mami Wata")) and t("Hŏ Kyun Hong Gildong") >= {"gildong", "kyun"}


def test_one_documentary_and_one_short_per_story_but_a_clip_may_sit_beside_its_documentary(tmp_path):
    video(tmp_path, "doc-a", "Hong Gildong", "doc")
    rows = duplicates.catalogue(tmp_path)
    subj = duplicates.tokens("Hong Gildong")
    assert duplicates.conflict(subj, "doc", rows)["slug"] == "doc-a"                         # a second documentary on the story
    assert duplicates.conflict(subj, "short", rows)["slug"] == "doc-a"                       # a queue-made Short on a documentary's story: clip it instead
    assert duplicates.conflict(subj, "short", rows, clip_of="doc-a") is None                 # a clip of that documentary is fine
    video(tmp_path, "short-a", "Hong Gildong", "short", source_doc="doc-a")
    rows = duplicates.catalogue(tmp_path)
    assert duplicates.conflict(subj, "short", rows, clip_of="doc-a")["slug"] == "short-a"     # but not a second Short
    assert duplicates.conflict(duplicates.tokens("Mami Wata"), "short", rows) is None


def test_a_video_on_hold_does_not_take_its_story_so_a_demo_or_a_dealt_with_duplicate_blocks_nothing(tmp_path):
    video(tmp_path, "demo", "Kitsune", "short", hold=True)
    video(tmp_path, "pulled", "Thunderbird", "short", hold=True, video_id="V1", publish_at="2026-10-24T17:00:00Z")
    rows = duplicates.catalogue(tmp_path)
    assert duplicates.conflict(duplicates.tokens("Kitsune"), "short", rows) is None and duplicates.conflict(duplicates.tokens("Thunderbird"), "short", rows) is None
    video(tmp_path, "keep", "Thunderbird", "short", publish_at="2026-10-26T16:30:00Z")
    assert duplicates.taken_by("keep", out=tmp_path) is None                                   # the private pulled-back copy does not block the real one


def test_taken_by_names_the_earlier_video_so_the_later_of_two_scheduled_duplicates_waits(tmp_path):
    video(tmp_path, "first", "Hong Gildong", "short", publish_at="2026-10-27T16:30:00Z")
    video(tmp_path, "second", "Hong Gildong", "short", publish_at="2026-10-28T16:30:00Z")
    video(tmp_path, "unscheduled", "Hong Gildong", "short")
    assert duplicates.taken_by("first", out=tmp_path) is None
    assert duplicates.taken_by("second", out=tmp_path)["slug"] == "first"
    assert duplicates.taken_by("unscheduled", out=tmp_path)["slug"] == "first"                # about to be scheduled: the story is taken


def test_the_real_topic_run_drops_a_topic_whose_story_is_already_made_and_a_test_run_does_not(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path)
    video(tmp_path, "doc-made", "Hong Gildong", "doc")
    q = ["Hong Gildong: Who Really Wrote It", "Roswell Incident"]
    monkeypatch.setattr(topicrank.topicqueue, "items", lambda: list(q))
    monkeypatch.setattr(topicrank.topicqueue, "remove_topic", lambda t: q.remove(t))
    got = topicrank.pop_best("doc", sig={}, article_of=lambda t: t + " is a subject with a long encyclopedia article. " * 60, premise_of=lambda t, a: (True, ""), demand_of=lambda t: 0.0, dup_of=duplicates.topic_conflict)
    assert got == "Roswell Incident" and q == []
    q[:] = ["Hong Gildong: Who Really Wrote It"]
    assert topicrank.pop_best("doc", sig={}, article_of=lambda t: t + " is a subject with a long encyclopedia article. " * 60, premise_of=lambda t, a: (True, ""), demand_of=lambda t: 0.0) == "Hong Gildong: Who Really Wrote It"


def test_a_documentary_whose_story_already_has_a_short_is_not_clipped_again(tmp_path, monkeypatch):
    import test_clipper
    monkeypatch.setattr(config, "OUT", tmp_path)
    doc = test_clipper.make_doc(tmp_path, "doc-a")
    meta = json.loads((doc / "meta.json").read_text())
    meta.update(topic="Fall of Constantinople", sources=["Wikipedia: Fall of Constantinople (CC BY-SA 4.0), retold in our own words"])
    (doc / "meta.json").write_text(json.dumps(meta))
    made = []
    produce = lambda data, topic, **kw: made.append(data) or tmp_path / "short-new"
    chat = lambda p: {"hook": "Why did it fall?", "title": "The fall"}
    assert clipper.make_next(produce=produce, chat=chat) == tmp_path / "short-new" and len(made) == 1          # control: with no Short on the story, one is made
    video(tmp_path, "short-a", "Fall of Constantinople", "short")                                              # now a Short on this story exists
    assert clipper.make_next(produce=lambda *a, **k: made.append("second"), chat=chat) is None and made[-1] != "second"


def test_a_video_the_approval_just_sent_back_is_not_scheduled_and_keeps_no_slot(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path)
    video(tmp_path, "needs-eyes", "Heungbu and Nolbu", "doc", review={"verdict": "needs_human", "checks": []})
    video(tmp_path, "yours", "Mami Wata", "doc", review={"verdict": "needs_human", "checks": []}, approved_by="you", approved=True)
    cfg = {**autopilot.DEFAULTS, "slots": [{"day": "tue", "time": "18:00"}], "review_window_hours": 24}
    assert autopilot.do_schedule("needs-eyes", cfg, NOW) == {"skipped": "not eligible"}
    assert "publish_at" not in json.loads((tmp_path / "needs-eyes" / "meta.json").read_text())
    autopilot.do_schedule("yours", cfg, NOW)                                                   # the owner's own approval always counts
    assert json.loads((tmp_path / "yours" / "meta.json").read_text()).get("publish_at")


def test_scheduling_and_uploading_hold_the_later_duplicate_tell_the_owner_and_never_send_it(tmp_path, monkeypatch):
    import agentbus
    import agentlog
    import upload
    from agenteval import sandbox
    monkeypatch.setattr(config, "OUT", tmp_path)
    with sandbox():
        video(tmp_path, "first", "Hong Gildong", "short", publish_at="2026-10-27T16:30:00Z", approved=True)
        video(tmp_path, "second", "Hong Gildong", "short", publish_at="2026-10-28T16:30:00Z", approved=True)
        sent = []
        monkeypatch.setattr(upload, "upload", lambda folder, privacy, at: sent.append(folder.name))
        autopilot.do_upload("first", {}, NOW)
        res = autopilot.do_upload("second", {}, NOW)
        assert sent == ["first"] and res == {"skipped": "duplicate"}
        m = json.loads((tmp_path / "second" / "meta.json").read_text())
        assert m["hold"] is True and "same story" in m["hold_reason"]
        assert any(t["kind"] == "duplicate_subject" and t["slug"] == "second" for t in agentbus.tasks())
        assert any("Held a duplicate" in e["title"] for e in agentlog.recent(5))
        video(tmp_path, "third", "Hong Gildong", "short", approved=True)
        cfg = {**autopilot.DEFAULTS, "short_slots": [{"day": "fri", "time": "16:00"}], "review_window_hours": 24}
        assert autopilot.do_schedule("third", cfg, NOW) == {"skipped": "duplicate"} and "publish_at" not in json.loads((tmp_path / "third" / "meta.json").read_text())


def test_a_chapter_about_a_films_box_office_is_never_cut_as_a_short_and_the_next_chapter_is_used(tmp_path, monkeypatch):
    import test_clipper
    monkeypatch.setattr(config, "OUT", tmp_path)
    doc = test_clipper.make_doc(tmp_path, "doc-a")
    meta = json.loads((doc / "meta.json").read_text())
    meta["topic"] = "Fall of Constantinople"
    meta["lines"] = [dict(l, text=(l["text"] + " The 2019 horror film grossed millions at the box office and critics panned it.") if i < 4 else l["text"]) for i, l in enumerate(meta["lines"])]
    (doc / "meta.json").write_text(json.dumps(meta))
    made = []
    clipper.make_next(produce=lambda data, topic, **kw: made.append(data) or tmp_path / "s", chat=lambda p: {"hook": "Why did it fall?", "title": "The fall"})
    assert made and not any("box office" in l["text"] for l in made[0]["lines"])
    after = json.loads((doc / "meta.json").read_text())
    assert 0 in after.get("clips_failed", []) and made[0]["clip_start_line"] not in (0,)


def test_a_hold_that_cannot_be_saved_does_not_stop_the_pass_and_the_owner_is_still_told(tmp_path, monkeypatch):
    import agentbus
    import records
    import upload
    from agenteval import sandbox
    monkeypatch.setattr(config, "OUT", tmp_path)
    with sandbox():
        video(tmp_path, "first", "Hong Gildong", "short", publish_at="2026-10-27T16:30:00Z", approved=True)
        video(tmp_path, "second", "Hong Gildong", "short", publish_at="2026-10-28T16:30:00Z", approved=True)
        monkeypatch.setattr(records, "merge", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
        monkeypatch.setattr(upload, "upload", lambda *a, **k: pytest_fail())
        assert autopilot.do_upload("second", {}, NOW) == {"skipped": "duplicate"}
        assert any(t["kind"] == "duplicate_subject" for t in agentbus.tasks())


def pytest_fail():
    raise AssertionError("a duplicate must never be uploaded")
