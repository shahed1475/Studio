"""A century written in words is a specific claim too (20 Nov 2026: the Tenali Rama Short said "sixteenth century" and its claim ledger came out empty)."""
import ledger
import reviewer

SOURCE = "Tenali Ramakrishna was a 16th-century Indian poet, scholar and thinker in the court of the Vijayanagara Empire."


def test_a_written_century_is_found_where_the_article_writes_it_in_figures():
    assert reviewer.unhedged_claims(["He was a sixteenth century poet."], SOURCE) == []
    assert reviewer.unhedged_claims(["He was a fourteenth century poet."], SOURCE) == ["fourteenth century"]  # a different century is still an open claim
    assert reviewer._numeric_century("twenty-first century") == ["21st century", "21st-century"] and reviewer._numeric_century("Tenali") == []


def test_the_ledger_now_lists_a_written_century_with_its_status():
    rows = ledger.build({"lines": [{"text": "Why was the sixteenth century poet remembered as a trickster?"}],
                         "sources": ["Wikipedia: Tenali Rama (CC BY-SA 4.0), retold in our own words"]}, SOURCE)
    assert [(r["claim_text"], r["verification_status"]) for r in rows] == [("sixteenth century", "VERIFIED")]
    assert rows[0]["source_url"].endswith("Tenali_Rama")
