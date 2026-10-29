"""A quotation is sourced when its own words are in the article (30 Oct 2026). The Cambyses script quoted Hawass as calling reports "unfounded and misleading," (comma inside the quote marks,
as US typing does). The article has: reports of the discovery "are unfounded and misleading" and that ... The ledger looked for the whole string with its quote marks and comma, found nothing,
left the claim UNVERIFIED and the quality gate blocked a correct, sourced quotation. An invented quotation must still stay open."""
import ledger
import reviewer

SOURCE = ('The Secretary General of the Egyptian Supreme Council of Antiquities, Zahi Hawass, has said in a press release that media reports of the discovery "are unfounded and misleading" '
          'and that "The Castiglioni brothers have not been granted permission by the\nSCA to excavate in Egypt". Thermoluminescence later dated the fragments to 1500 BC.')
HAWASS = 'Zahi Hawass, the council\'s Secretary General, called the reports "unfounded and misleading," noting the brothers had no permission to excavate in Egypt.'
INVENTED = 'Hawass also called the whole affair "a shameful circus run by treasure hunters," in that same press release.'


def rows(*lines):
    return ledger.build({"title": "T", "lines": [{"text": t} for t in lines], "sources": ["Wikipedia: Lost Army of Cambyses (CC BY-SA 4.0), retold in our own words"]}, SOURCE)


def test_a_quotation_whose_own_words_are_in_the_source_is_found_whatever_surrounds_it():
    for claim in ('"unfounded and misleading,"', '“unfounded and misleading,”', '"unfounded and misleading."', '"Unfounded and Misleading"',
                  '"The Castiglioni brothers have not been granted permission by the SCA to excavate in Egypt,"'):
        assert reviewer._in_source(claim, SOURCE), claim  # punctuation, quote marks, case and a line break in the source do not matter


def test_a_quotation_the_source_does_not_contain_is_not_found_and_a_year_is_matched_as_before():
    assert not reviewer._in_source('"a shameful circus run by treasure hunters,"', SOURCE)
    assert not reviewer._in_source('"unfounded and deeply misleading,"', SOURCE)  # one added word is a different quotation
    assert reviewer._in_source("1500", SOURCE) and not reviewer._in_source("1501", SOURCE)


def test_the_ledger_verifies_the_sourced_quotation_with_its_passage_and_leaves_the_invented_one_open():
    got = {r["claim_text"]: r for r in rows(HAWASS, INVENTED)}
    ok, bad = got['"unfounded and misleading,"'], got['"a shameful circus run by treasure hunters,"']
    assert ok["verification_status"] == "VERIFIED" and "unfounded and misleading" in ok["evidence_excerpt"] and ok["evidence_excerpt"].strip()
    assert bad["verification_status"] == "UNVERIFIED" and bad["evidence_excerpt"] == ""  # nothing is verified without a passage to show


def test_claim_lines_no_longer_report_the_sourced_quotation_but_still_report_the_invented_one():
    found = [c for _, c, _ in reviewer.claim_lines([HAWASS, INVENTED], SOURCE)]
    assert '"unfounded and misleading,"' not in found and '"a shameful circus run by treasure hunters,"' in found
