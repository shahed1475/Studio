import json

import config
import topicqueue


def test_subjects_pass_and_instructions_do_not():
    for ok in ("The Jersey Devil", "The Mystery of the Benin Bronzes", "Titanic's Greek Secret"):
        assert topicqueue.looks_like_topic(ok)
    for bad in ("Create content around unsolved mysteries from the US.", "Focus on unsolved mysteries with surprising endings.",
                "Make some videos that retell a public-domain folk legend in your own words", "Build the next video around one well-documented mystery",
                "Produce a deep dive on the Lost Colony.", "x"):
        assert not topicqueue.looks_like_topic(bad)


def test_an_instruction_naming_one_story_is_cut_down_to_it_and_pure_advice_is_turned_away():
    chat = lambda p: {"topic": "The Jersey Devil"} if "Jersey" in p.splitlines()[-1] else {"topic": ""}
    assert topicqueue.subject_of("Create a retelling of the public-domain legend of the Jersey Devil.", chat) == "The Jersey Devil"
    assert topicqueue.subject_of("Focus on unsolved mysteries with surprising endings.", chat) is None
    assert topicqueue.subject_of("The Hanging Gardens", lambda p: 1 / 0) == "The Hanging Gardens"  # a subject needs no model
    assert topicqueue.subject_of("Create something good", lambda p: 1 / 0) is None  # a model failure never queues junk


def test_clean_queue_keeps_subjects_once(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "TOPICS_FILE", tmp_path / "topics.json")
    config.TOPICS_FILE.write_text(json.dumps(["The Mary Celeste", "Create content around mysteries.", "Create a video on the Jersey Devil, a legend.",
                                              "Retell the legend of the Jersey Devil with a twist", "The Talking Drum"]))
    chat = lambda p: {"topic": "The Jersey Devil"} if "Jersey" in p.splitlines()[-1] else {"topic": ""}
    removed, kept = topicqueue.clean_queue(chat)
    assert kept == ["The Mary Celeste", "The Jersey Devil", "The Talking Drum"] and len(removed) == 2
    assert json.loads(config.TOPICS_FILE.read_text()) == kept


def test_a_pinned_topic_is_taken_before_any_queued_one_once_and_per_format(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "TOPICS_FILE", tmp_path / "topics.json")
    topicqueue._write(["The Jersey Devil", "The Oracle of Delphi: Myth, Sanctuary and Excavation"])
    topicqueue.pin("The Oracle of Delphi: Myth, Sanctuary and Excavation", "doc")
    topicqueue.pin("A Short Topic", "short")
    topicqueue.pin("The Oracle of Delphi: Myth, Sanctuary and Excavation", "doc")  # pinning twice changes nothing
    assert topicqueue.pop_pinned("doc") == "The Oracle of Delphi: Myth, Sanctuary and Excavation"
    assert topicqueue.pop_pinned("doc") is None and topicqueue.pop_pinned("short") == "A Short Topic" and topicqueue.pop_pinned("short") is None
    assert topicqueue.items() == ["The Jersey Devil"]  # the pinned one left the queue too, so it is not made twice


def test_run_takes_a_pinned_topic_before_the_ranking(tmp_path, monkeypatch):
    import run
    import topicrank

    monkeypatch.setattr(config, "TOPICS_FILE", tmp_path / "topics.json")
    topicqueue._write(["A", "B"])
    monkeypatch.setattr(topicrank, "pop_best", lambda fmt, **k: "A")
    assert run._best_topic("doc") == "A"
    topicqueue.pin("B", "doc")
    assert run._best_topic("doc") == "B" and run._best_topic("doc") == "A"
