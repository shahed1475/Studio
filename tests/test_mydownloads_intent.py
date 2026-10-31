"""My Downloads: turning what the owner types or says into a request (fixed rules, no model, no network)."""
import pytest

from mydownloads import intent


def p(text):
    return intent.parse(text)


def test_last_five_videos():
    r = p("download my last 5 videos")
    assert (r.count, r.order, r.kind, r.keywords, r.urls) == (5, "newest", "any", [], [])


def test_punctuation_and_case_from_speech_do_not_matter():
    r = p("Download, my LAST 5 videos!")
    assert (r.count, r.order, r.kind, r.keywords) == (5, "newest", "any", [])


@pytest.mark.parametrize("text,n", [("get the latest three videos", 3), ("download a dozen of my videos", 12), ("fetch twenty five videos", 25),
                                    ("save one video", 1), ("download my couple of videos", 2), ("give me ninety nine videos", 99)])
def test_numbers_in_words(text, n):
    assert p(text).count == n


def test_all_means_no_count_limit():
    assert p("download all my videos").count is None
    assert p("get every video I made").count is None


def test_no_count_assumes_five_and_says_so():
    r = p("download my videos")
    assert r.count == 5
    assert any("5" in n for n in r.notes)


def test_a_huge_number_is_cut_to_the_batch_limit_with_a_note():
    r = p("download 500 videos")
    assert r.count == intent.MAX_BATCH
    assert any(str(intent.MAX_BATCH) in n for n in r.notes)


def test_a_year_is_a_keyword_not_a_count():
    r = p("download my videos from 2024")
    assert "2024" in r.keywords
    assert r.count == 5


def test_shorts_and_long_kinds_are_not_keywords():
    r = p("get my last 4 shorts")
    assert (r.kind, r.count, r.keywords) == ("short", 4, [])
    r = p("download my 2 documentaries")
    assert (r.kind, r.count, r.keywords) == ("long", 2, [])
    assert p("all my Shorts").count is None


def test_both_kinds_named_means_any():
    assert p("my shorts and documentaries").kind == "any"


def test_oldest_and_first_mean_oldest_first():
    assert p("download my oldest 2 videos").order == "oldest"
    assert p("download the first 3 videos").order == "oldest"
    assert p("download the newest 3 videos").order == "newest"
    assert p("download the recent 3 videos").order == "newest"


def test_topic_words_become_keywords():
    r = p("I want to download the videos about Bell Witch please")
    assert r.keywords == ["bell", "witch"]
    r = p("download 3 videos about Cambyses")
    assert (r.count, r.keywords) == (3, ["cambyses"])


def test_keywords_are_not_repeated():
    assert p("videos about witch witch witch").keywords == ["witch"]


def test_links_are_found_and_not_read_as_words():
    r = p("please download https://youtu.be/abc123XYZ_-, thanks")
    assert r.urls == ["https://youtu.be/abc123XYZ_-"]
    assert r.keywords == []
    r = p("get youtube.com/watch?v=w5crV5QVfvo and www.youtube.com/shorts/IJMODrVC7Uk")
    assert r.urls == ["https://youtube.com/watch?v=w5crV5QVfvo", "https://www.youtube.com/shorts/IJMODrVC7Uk"]


def test_other_sites_are_not_treated_as_links():
    assert p("download https://example.com/video.mp4").urls == []


def test_blank_text_is_a_plain_default_request():
    r = p("   ")
    assert (r.urls, r.keywords) == ([], [])


def test_describe_says_the_request_in_plain_words():
    d = intent.describe
    assert d(p("download my last 5 videos")) == "The 5 newest of your videos"
    assert d(p("all my shorts")) == "All of your Shorts"
    assert d(p("download my oldest 2 documentaries about Cambyses")) == "The 2 oldest of your long videos about “cambyses”"
    assert d(p("download 1 video")) == "Your newest video"
    assert d(p("get my first short")) == "Your oldest Short"
    assert d(p("download the videos about bell witch")) == "The 5 newest of your videos about “bell witch”"
    assert d(p("download https://youtu.be/abc123XYZ_-")) == "1 link you pasted"
    assert d(p("download https://youtu.be/abc123XYZ_- and youtu.be/def456UVW_-")) == "2 links you pasted"


def test_match_score_counts_keywords_found_as_word_starts():
    s = intent.match_score
    assert s("The Lost Army of Cambyses", ["cambyses"]) == 1
    assert s("The Lost Army of Cambyses", ["cambyses", "desert"]) == 1
    assert s("The Lost Army of Cambyses", ["gyses"]) == 0  # a word start, not any part of a word
    assert s("Hong Gildong: Korea's Outlaw Hero", ["gild"]) == 1
    assert s("Anything", []) == 0


def test_match_score_ignores_case_accents_and_a_plural_s():
    s = intent.match_score
    assert s("Why Tradition Credits Hŏ Kyun", ["ho", "KYUN"]) == 2
    assert s("Legend of the Thunderbird", ["legends"]) == 1
    assert s("Thunderbird Mythology", ["thunderbirds", "myths"]) == 1  # "myths" is not "mythology"
