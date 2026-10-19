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


# ---- policy page watch ----
PAGE_A = ("<html><script>var x=1;</script><body><p>Inauthentic content means content that is repetitive or mass-produced.</p>"
          "<p>Reused content is allowed if viewers can tell there is a meaningful difference.</p>"
          "<p>Channels earn money only after they reach the subscriber and watch hour thresholds.</p>"
          "<p>AI tools may be used to write scripts and to generate unique background visuals.</p>"
          "<p>Videos that are made from generic templates are not eligible for monetization.</p><p>Short.</p></body></html>")
PAGE_B = PAGE_A.replace("<p>Short.</p>", "<p>Channels must disclose realistic synthetic scenes made with AI tools in the upload settings.</p>")


def _pw(tmp_path, monkeypatch, pages):
    import agentlog
    monkeypatch.setattr(newswatch, "DATA_DIR", tmp_path / "nw")
    monkeypatch.setattr(newswatch, "POLICY_PAGES", pages)
    monkeypatch.setattr(agentlog, "FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(agentlog, "subprocess", __import__("types").SimpleNamespace(run=lambda *a, **k: None))


def test_page_sentences_drop_scripts_and_short_noise():
    s = newswatch.page_sentences(PAGE_A)
    assert len(s) == 5 and s[0].startswith("Inauthentic content") and not any("var x" in x for x in s)


def test_policy_watch_baseline_then_reports_added_sentences(tmp_path, monkeypatch):
    _pw(tmp_path, monkeypatch, {"Monetization policies": "https://support.example/m"})
    assert newswatch.policy_watch(NOW, get=lambda u: PAGE_A) == []  # first run only records the baseline
    assert newswatch.policy_watch(NOW, get=lambda u: PAGE_A) == []  # unchanged
    got = newswatch.policy_watch(NOW, get=lambda u: PAGE_B)
    assert len(got) == 1 and got[0]["page"] == "Monetization policies" and "disclose realistic" in got[0]["added"][0]
    import agentlog
    assert "Monetization policies" in agentlog.recent(1)[0]["title"]
    assert json.loads((tmp_path / "nw" / "policy_log.json").read_text())[0]["url"] == "https://support.example/m"


def test_policy_watch_keeps_baseline_when_a_page_cannot_be_read(tmp_path, monkeypatch):
    _pw(tmp_path, monkeypatch, {"P": "https://support.example/p"})
    newswatch.policy_watch(NOW, get=lambda u: PAGE_A)
    def down(u):
        raise OSError("503")
    assert newswatch.policy_watch(NOW, get=down) == []
    assert newswatch.policy_watch(NOW, get=lambda u: "<html>blocked</html>") == []  # unreadable text never wipes the baseline
    assert newswatch.policy_watch(NOW, get=lambda u: PAGE_A) == []


def test_digest_carries_policy_changes_and_self_audit(tmp_path, monkeypatch):
    _pw(tmp_path, monkeypatch, {"P": "https://support.example/p"})
    monkeypatch.setattr(newswatch, "TOPICS_FILE", tmp_path / "news_topics.json")
    monkeypatch.setattr(newswatch, "fetch_items", lambda days=10, now=None: [])
    newswatch.policy_watch(NOW, get=lambda u: PAGE_A)
    newswatch.policy_watch(NOW, get=lambda u: PAGE_B)
    data = json.loads(newswatch.run(NOW).read_text())
    assert data["items"][0]["title"].startswith("Policy page changed: P") and data["items"][0]["link"] == "https://support.example/p"
    assert isinstance(data["self_audit"], list) and data["self_audit"][0]["name"] == "file_modes"


def test_relevant_filter_knows_policy_words():
    assert newswatch.is_relevant({"title": "Update on inauthentic content and quota", "summary": ""})


def test_page_noise_is_not_a_policy_change():
    """Live pages carry menu text and per-request ids; two reads of the same page must look identical."""
    noise = lambda n: f"<p>This help content General Help Center Main menu {n}1234567890123 true Search Help Center false true true 59 false false</p>"
    a, b = noise(1) + PAGE_A, noise(2) + PAGE_A
    assert newswatch.page_sentences(a) == newswatch.page_sentences(b)
    assert len(newswatch.page_sentences(a)) >= 4  # the sentence the menu text ran into is dropped, the rest stay
