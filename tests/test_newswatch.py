import json
from datetime import datetime, timezone

import newswatch
import scriptgen

RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>Blog</title>
<item><title>New protections against account takeovers</title><link>https://blog.youtube/a</link>
<pubDate>Mon, 12 Oct 2026 15:00:00 +0000</pubDate><description>&lt;p&gt;We are adding passkey sign-in.&lt;/p&gt;</description></item>
<item><title>Summer playlist</title><link>https://blog.youtube/b</link><pubDate>Mon, 12 Oct 2026 10:00:00 +0000</pubDate><description>Music picks</description></item>
</channel></rss>"""
ATOM = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>Sec</title>
<entry><title>Spotting phishing links</title><link rel="alternate" href="https://sec.example/p"/><published>2026-10-14T09:30:00Z</published>
<summary>New scam warning for creators.</summary></entry></feed>"""
NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)


def test_parse_rss():
    items = newswatch.parse_feed(RSS)
    assert [i["title"] for i in items][0] == "New protections against account takeovers"
    assert items[0]["link"] == "https://blog.youtube/a" and items[0]["published"].startswith("2026-10-12T15:00")
    assert "<p>" not in items[0]["summary"] and "passkey" in items[0]["summary"]


def test_parse_atom():
    items = newswatch.parse_feed(ATOM)
    assert items[0]["link"] == "https://sec.example/p" and items[0]["published"] == "2026-10-14T09:30:00Z"


def test_parse_malformed_returns_empty():
    assert newswatch.parse_feed("<rss><channel><item>") == []
    assert newswatch.parse_feed("") == []


def test_is_relevant_filters():
    a, b = newswatch.parse_feed(RSS)
    assert newswatch.is_relevant(a) and not newswatch.is_relevant(b)


def test_fetch_items_skips_dead_feeds_and_old_items(monkeypatch):
    def fake_get(url):
        if "bad" in url:
            raise OSError("404")
        return RSS
    monkeypatch.setattr(newswatch, "FEEDS", {"good": "https://good", "bad": "https://bad"})
    monkeypatch.setattr(newswatch, "_get", fake_get)
    got = newswatch.fetch_items(days=10, now=NOW)
    assert len(got) == 2 and got[0]["feed"] == "good"
    assert newswatch.fetch_items(days=3, now=NOW) == []


def test_summarize_uses_only_given_text(monkeypatch):
    seen = []
    def fake(prompt, *a, **k):
        seen.append(prompt)
        return {"items": [{"title": "T", "what_changed": "w", "why_it_matters": "y", "steps": ["s"], "link": "l"}], "video_ideas": ["Idea"]}
    monkeypatch.setattr(scriptgen, "_chat", fake)
    out = newswatch.summarize(newswatch.parse_feed(RSS)[:1])
    assert "passkey" in seen[0] and "ONLY" in seen[0]
    assert out["video_ideas"] == ["Idea"]


def test_run_survives_empty_feeds(tmp_path, monkeypatch):
    monkeypatch.setattr(newswatch, "DATA_DIR", tmp_path / "nw")
    monkeypatch.setattr(newswatch, "TOPICS_FILE", tmp_path / "news_topics.json")
    monkeypatch.setattr(newswatch, "fetch_items", lambda days=10, now=None: [])
    p = newswatch.run(NOW)
    data = json.loads(p.read_text())
    assert p.name == "2026-W43.json" and data["items"] == [] and data["video_ideas"] == []


def test_run_writes_digest_and_proposals(tmp_path, monkeypatch):
    monkeypatch.setattr(newswatch, "DATA_DIR", tmp_path / "nw")
    monkeypatch.setattr(newswatch, "TOPICS_FILE", tmp_path / "news_topics.json")
    monkeypatch.setattr(newswatch, "fetch_items", lambda days=10, now=None: [{**newswatch.parse_feed(RSS)[0], "feed": "YT"}])
    monkeypatch.setattr(newswatch, "summarize", lambda items: {"items": [{"title": "T", "what_changed": "w", "why_it_matters": "y", "steps": [], "link": "https://blog.youtube/a"}], "video_ideas": ["How passkeys protect your channel"]})
    newswatch.run(NOW)
    newswatch.run(NOW)  # twice: proposals are not duplicated
    topics = json.loads((tmp_path / "news_topics.json").read_text())
    assert [t["topic"] for t in topics] == ["How passkeys protect your channel"] and topics[0]["status"] == "proposed"


def test_queue_news_topic(tmp_path, monkeypatch):
    monkeypatch.setattr(newswatch, "NEWS_QUEUE", tmp_path / "news_queue.json")
    newswatch.queue_news_topic("How passkeys protect your channel", ["https://blog.youtube/a"], "2026-W43")
    q = json.loads((tmp_path / "news_queue.json").read_text())
    assert q[0]["status"] == "queued" and q[0]["sources"] == ["https://blog.youtube/a"]


def test_doc_script_with_facts_says_only(monkeypatch):
    prompts = []
    def fake(prompt, *a, **k):
        prompts.append(prompt)
        raise RuntimeError("stop")
    monkeypatch.setattr(scriptgen, "_chat", fake)
    try:
        scriptgen.doc_script("Topic", facts="FACT: passkeys launched")
    except RuntimeError:
        pass
    assert "ONLY" in prompts[0] and "FACT: passkeys launched" in prompts[0]
