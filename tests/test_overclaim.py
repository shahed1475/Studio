"""The reviewer flags a line that calls proven what its source only suggests (reviewer.overclaims, 20 Nov 2026)."""
import reviewer

TENALI = ("Popular legend conflicts with the historical record over the timing of his court tenure. Internal textual evidence and dedications in his works suggest that "
          "he survived the fall of the Tuluva dynasty's golden age and flourished well into the second half of the 16th century, receiving patronage from later Aravidu "
          "dynasty rulers and nobles like Venkatapati Raya and Manuri Venkatadri, despite oral tradition placing him solely as a contemporary of Krishnadevaraya.")
VOYNICH = "The first confirmed owner was Georg Baresch, an alchemist from Prague, who may have bought it in the 1630s."


def test_proven_where_the_source_only_suggests_is_flagged():
    got = reviewer.overclaims(["Born in Tenali, he served Vijayanagara.", "Yet textual dedications prove he actually served later ruler Venkatapati Raya."], TENALI)
    assert [i for i, _, _ in got] == [1] and "suggest" in got[0][2]


def test_honest_lines_are_not_flagged():
    assert reviewer.overclaims(["Dedications suggest that Venkatapati Raya was one of his patrons."], TENALI) == []  # no certainty word
    assert reviewer.overclaims(["Nobody has ever proven that Venkatapati Raya paid him."], TENALI) == []  # a negated certainty
    assert reviewer.overclaims(["The first confirmed owner was Georg Baresch of Prague."], VOYNICH) == []  # the source itself says confirmed
    assert reviewer.overclaims(["Yet textual dedications prove he served Venkatapati Raya."], "") == []  # no source, nothing to compare


def test_the_review_carries_the_check_as_a_human_decision():
    meta = {"title": "Tenali Rama", "description": "d", "tags": ["a"], "format": "short",
            "lines": [{"text": "Yet textual dedications prove he actually served later ruler Venkatapati Raya.", "visual": "v"}]}
    probe = {"duration": 50.0, "width": 1080, "height": 1920, "has_audio": True, "mean_db": -17.0, "black_ratio": 0.0}
    rows = {r["name"]: r for r in reviewer.rule_checks(meta, probe, [], None, [], TENALI)}
    assert rows["overclaim"]["ok"] is False and rows["overclaim"]["severity"] == "human" and "line 1" in rows["overclaim"]["detail"]
    rows = {r["name"]: r for r in reviewer.rule_checks({**meta, "lines": [{"text": "Dedications suggest Venkatapati Raya was a patron.", "visual": "v"}]}, probe, [], None, [], TENALI)}
    assert rows["overclaim"]["ok"] is True


def test_the_behaviour_check_holds_and_fails_on_each_broken_rule(monkeypatch):
    import re

    import agenteval

    ok, why = agenteval.case_the_reviewer_flags_a_line_that_calls_proven_what_its_source_only_suggests()
    assert ok, why
    never = re.compile(r"(?!x)x")
    for name, value in (("CERTAIN", never),        # mutation: certainty words are not seen
                        ("SOURCE_HEDGE", never),   # mutation: the source's hedges are not seen
                        ("overclaims", lambda lines, source: [(0, "x", "y")])):  # mutation: everything is flagged, honest lines too
        with monkeypatch.context() as m:
            m.setattr(reviewer, name, value)
            assert not agenteval.case_the_reviewer_flags_a_line_that_calls_proven_what_its_source_only_suggests()[0], name
