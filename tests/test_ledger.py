import json

import ledger

SOURCE = "Delphi was originally called Pytho. French archaeologists began excavating in 1893 near the temple."
META = {"sources": ["Wikipedia: Delphi (CC BY-SA 4.0), retold", "Checked against: https://example.org/elgin"], "verified_claims": ["1938"],
        "conflicting_claims": [{"claim": "1799", "fact": "The removals began in 1801."}],
        "lines": [{"text": "The sanctuary was originally called Pytho in ancient times."}, {"text": "French diggers arrived in 1893 and found the site."},
                  {"text": "A fire swept the site in 1938 according to one report."}, {"text": "Lord Elgin took the marbles in 1799."},
                  {"text": "Some historians believe it fell in 1500."}, {"text": "Visitors asked the priestess a question."}]}


def test_every_claim_gets_a_status_and_the_evidence_behind_it():
    rows = {r["claim_text"]: r for r in ledger.build(META, SOURCE)}
    assert rows["called Pytho"]["verification_status"] == "VERIFIED" and "Pytho" in rows["called Pytho"]["evidence_excerpt"]
    assert rows["1893"]["source_url"] == "https://en.wikipedia.org/wiki/Delphi" and rows["1893"]["confidence"] == "high"
    assert rows["1799"]["verification_status"] == "CONFLICTING" and "1801" in rows["1799"]["notes"]
    assert rows["1500"]["verification_status"] == "PARTIALLY_VERIFIED"  # hedged in the narration
    assert all(r["verification_status"] in ledger.STATUSES for r in rows.values())


def test_a_claim_nothing_supports_stays_unverified_and_the_file_is_written(tmp_path):
    meta = {**META, "verified_claims": [], "lines": [{"text": "The temple burned in 1666."}]}
    counts = ledger.write(tmp_path, meta, SOURCE)
    saved = json.loads((tmp_path / "claims.json").read_text())
    assert counts["UNVERIFIED"] == 1 and saved[0]["verification_status"] == "UNVERIFIED" and set(saved[0]) >= {"claim_id", "claim_text", "source_url", "evidence_excerpt", "confidence", "notes"}
