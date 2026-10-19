import reviewer

SOURCE = "Delphi was originally called Pytho. French archaeologists began excavating in 1893. The temple was closed in 392 AD."
LINES = ["The sanctuary was originally called Pytho in ancient times.", "French diggers arrived in 1893 and uncovered the site.",
         "A famous oracle foretold the fall in 1938."]


def test_claims_found_in_the_source_article_are_verified_and_not_counted():
    assert reviewer.unhedged_claims(LINES) == ["called Pytho", "1893", "1938"]  # without a source every specific is a claim
    assert reviewer.unhedged_claims(LINES, SOURCE) == ["1938"]  # only the one the article never mentions is left


def test_one_unsupported_claim_no_longer_needs_a_human_but_two_do():
    base = {"format": "short", "lines": [{"text": t} for t in LINES], "title": "A fine title here", "description": "d" * 100, "tags": list("abcdef")}
    probe = {"duration": 60, "width": 1080, "height": 1920, "has_audio": True, "mean_db": -16, "black_ratio": 0}
    claims = lambda src: next(c for c in reviewer.rule_checks(base, probe, [], None, source=src) if c["name"] == "claims")
    assert claims("")["ok"] is False and "check them" in claims("")["detail"]
    ok = claims(SOURCE)
    assert ok["ok"] is True  # one left: below the limit of two


def test_source_title_is_read_from_the_source_line():
    assert reviewer.source_title({"sources": ["Wikipedia: Delphi (CC BY-SA 4.0), retold in our own words", "https://en.wikipedia.org/wiki/Delphi"]}) == "Delphi"
    assert reviewer.source_title({"sources": []}) == "" and reviewer.source_title({}) == ""


def test_source_text_is_fetched_once_then_cached(tmp_path, monkeypatch):
    import config, wikipedia
    monkeypatch.setattr(config, "CACHE", tmp_path)
    calls = []
    monkeypatch.setattr(wikipedia, "article_text", lambda t, chars=80000: calls.append(t) or "Article text 1893")
    meta = {"grounded": True, "sources": ["Wikipedia: Pied Piper of Hamelin (CC BY-SA 4.0), retold"]}
    assert reviewer.source_text(meta) == "Article text 1893" and reviewer.source_text(meta) == "Article text 1893"
    assert calls == ["Pied Piper of Hamelin"]
    assert reviewer.source_text({**meta, "grounded": False}) == ""  # an ungrounded script has nothing to check against
