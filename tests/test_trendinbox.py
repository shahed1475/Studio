from datetime import datetime, timedelta, timezone

import pytest

import topicrank
import trendinbox

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def inbox_file(tmp_path, monkeypatch):
    monkeypatch.setattr(trendinbox, "FILE", tmp_path / "inbox.json")


def test_add_keeps_a_cleaned_title_and_numbers_and_marks_where_it_came_from():
    item = trendinbox.add("  Lost Army of​ Cambyses?  ", channel="Unsuljhi Tales", views=34_803, age_days=4.9, seconds=61, url="https://www.youtube.com/watch?v=zhNaw5cz200", source="studio_trends", now=NOW)
    assert item["title"] == "Lost Army of Cambyses?" and item["source"] == "studio_trends" and item["views"] == 34_803
    assert trendinbox.active(NOW) == [item]


@pytest.mark.parametrize("bad", ["", "   ", "x" * 300])
def test_add_refuses_an_empty_or_absurdly_long_title(bad):
    with pytest.raises(ValueError):
        trendinbox.add(bad, now=NOW)


def test_add_refuses_a_link_that_is_not_a_youtube_video_address():
    with pytest.raises(ValueError):
        trendinbox.add("A Story", url="https://evil.example/watch?v=1", now=NOW)
    assert trendinbox.add("A Story", url="https://youtu.be/abc123", now=NOW)["url"] == "https://youtu.be/abc123"


def test_the_same_title_twice_is_kept_once_and_the_list_is_capped():
    trendinbox.add("The Same Story", now=NOW)
    trendinbox.add("the same story!", now=NOW)
    assert len(trendinbox.active(NOW)) == 1
    for i in range(trendinbox.MAX_ITEMS + 5):
        trendinbox.add(f"Story number {i} unique", now=NOW)
    assert len(trendinbox.active(NOW)) == trendinbox.MAX_ITEMS


def test_an_item_expires_after_the_fresh_window():
    trendinbox.add("Old News Story", now=NOW - timedelta(days=15))
    trendinbox.add("Recent Story Idea", now=NOW - timedelta(days=2))
    assert [i["title"] for i in trendinbox.active(NOW)] == ["Recent Story Idea"]


def test_topic_ranking_counts_an_inbox_item_like_a_video_taking_off(monkeypatch):
    import channelwatch
    import trendwatch

    monkeypatch.setattr(trendwatch, "latest", lambda: None)
    monkeypatch.setattr(channelwatch, "latest", lambda: None)
    trendinbox.add("Lost Army of Cambyses", views=34_803, now=datetime.now(timezone.utc))
    sig = topicrank.signals()
    assert len(sig) == 1 and topicrank.score("Lost Army of Cambyses", sig) > 0


def test_import_items_keeps_the_good_rows_and_reports_each_bad_one_instead_of_stopping():
    rows = [{"title": "How People Slept Inside a Medieval Castle in Winter", "channel": "History Reconstructed", "views": 79_500, "age_days": 7, "seconds": 1862},
            {"title": "", "views": 5},
            {"title": "Bad link", "url": "https://evil.example/x"},
            "not a row"]
    done, problems = trendinbox.import_items(rows, source="studio_trends", now=NOW)
    assert [d["title"] for d in done] == ["How People Slept Inside a Medieval Castle in Winter"] and done[0]["source"] == "studio_trends"
    assert len(problems) == 3 and "row 2" in problems[0]


def test_taking_off_combines_niche_search_reference_channels_and_the_inbox_best_first(monkeypatch):
    import channelwatch
    import trendwatch

    monkeypatch.setattr(trendwatch, "latest", lambda: {"fresh": {"docs": [{"title": "Doc A", "score": 2.0}], "shorts": [{"title": "Short A", "score": 9.0}], "hint": {"doc_minutes": 9.0}}})
    monkeypatch.setattr(channelwatch, "latest", lambda: {"channels": [{"channel": "Legend Lab", "fresh": [{"title": "Hit B", "score": 6.0, "channel": "Legend Lab"}]}, {"channel": "Quiet", "fresh": []}]})
    trendinbox.add("Studio pick", views=5000, now=datetime.now(timezone.utc))
    got = trendinbox.taking_off()
    assert [v["title"] for v in got["docs"]] == ["Doc A"] and [v["title"] for v in got["shorts"]] == ["Short A"]
    assert [v["title"] for v in got["channels"]] == ["Hit B"] and [v["title"] for v in got["inbox"]] == ["Studio pick"]
    assert got["hint"] == {"doc_minutes": 9.0}


def test_taking_off_is_empty_not_an_error_before_any_study_has_run(monkeypatch):
    import channelwatch
    import trendwatch

    monkeypatch.setattr(trendwatch, "latest", lambda: None)
    monkeypatch.setattr(channelwatch, "latest", lambda: None)
    assert trendinbox.taking_off() == {"docs": [], "shorts": [], "channels": [], "inbox": [], "hint": {}}
