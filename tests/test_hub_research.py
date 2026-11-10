"""The hub's research store and the niche research run. The article reader is replaced by a fake: no network, no cost."""
import pytest

from hub import auth, db, research

SRC = {"url": "https://en.wikipedia.org/wiki/Petra", "title": "Petra", "passage": "Petra is an archaeological site in southern Jordan.", "revised": "2026-10-01T00:00:00Z"}


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "PATH", tmp_path / "hub" / "hub.db")
    monkeypatch.setattr(auth, "SECRET_FILE", tmp_path / "hub" / "secret")


def account(email="a@example.com"):
    with db.tx() as con:
        return auth._account_for_email(con, email, 1000.0)


def test_topic_with_source_is_partially_verified_never_verified():
    a = account()
    t = research.add_topic(a, "Petra", SRC, now=1.0)
    o = research.overview(a)
    assert t["label"] == "PARTIALLY_VERIFIED" and o["topics"][0]["label"] == "PARTIALLY_VERIFIED"
    assert o["sources"][0]["url"] == SRC["url"] and o["sources"][0]["revised"] == SRC["revised"] and o["topics"][0]["source_id"] == o["sources"][0]["id"]
    assert "VERIFIED" not in research.LABELS_ALLOWED


def test_topic_without_source_is_unverified():
    a = account()
    t = research.add_topic(a, "Atlantis", None)
    assert t["label"] == "UNVERIFIED" and t["source_id"] is None and research.overview(a)["sources"] == []


@pytest.mark.parametrize("url", ["http://example.com/a", "javascript:alert(1)", "ftp://x/y", ""])
def test_a_source_that_is_not_https_is_dropped(url):
    a = account()
    t = research.add_topic(a, "Petra", {**SRC, "url": url})
    assert t["label"] == "UNVERIFIED" and research.overview(a)["sources"] == []


def test_a_source_without_a_passage_does_not_make_a_topic_partially_verified():
    a = account()
    assert research.add_topic(a, "Petra", {**SRC, "passage": "   "})["label"] == "UNVERIFIED"


def test_passage_is_cut_at_600_characters():
    a = account()
    research.add_topic(a, "Petra", {**SRC, "passage": "x" * 2000})
    assert len(research.overview(a)["sources"][0]["passage"]) == 600


def test_same_topic_twice_is_one_row():
    a = account()
    research.add_topic(a, "Petra", SRC)
    research.add_topic(a, "Petra", SRC)
    o = research.overview(a)
    assert len(o["topics"]) == 1 and len(o["sources"]) == 1


def test_a_blank_title_is_refused():
    with pytest.raises(ValueError):
        research.add_topic(account(), "   ", None)


def test_accounts_never_see_each_others_rows():
    a, b = account("a@example.com"), account("b@example.com")
    research.add_topic(a, "Petra", SRC)
    assert research.overview(b) == {"sources": [], "topics": []}
    research.add_topic(b, "Petra", SRC)
    assert len(research.overview(a)["topics"]) == 1 and len(research.overview(b)["topics"]) == 1


def test_deleting_an_account_removes_its_research():
    a = account()
    research.add_topic(a, "Petra", SRC)
    with db.tx() as con:
        con.execute("delete from accounts where id=?", (a,))
    assert research.overview(a) == {"sources": [], "topics": []}
