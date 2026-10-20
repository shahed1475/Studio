import compliance
import aiart

SOURCE = ("Delphi was an ancient sanctuary on the slope of Mount Parnassus where the Pythia, the priestess of Apollo, gave answers to those who came to ask. "
          "The French Archaeological School began the Great Excavation in 1893 after the village of Kastri was moved to a new site nearby. " * 2)


def meta(**kw):
    base = {"title": "Delphi: The Oracle and Its Ruins", "description": "A calm look at Delphi.\n\nSources:\nWikipedia\n\nChapters:\n0:00 One\n1:00 Two\n2:00 Three",
            "tags": ["delphi", "oracle of delphi", "history stories for sleep", "greek history", "archaeology"], "lines": [{"text": "The oracle was consulted on important decisions across the classical world."}]}
    return {**base, **kw}


def test_a_normal_video_passes_the_metadata_limits():
    assert compliance.metadata_check(meta())["ok"] is True


def test_each_documented_metadata_limit_fails_and_names_the_problem():
    cases = {"title": meta(title="x" * 101), "title <": meta(title="Delphi <b>"), "description <": meta(description="a > b " * 20), "description bytes": meta(description="é" * 2600),
             "tags": meta(tags=[f"tag number {i}" for i in range(60)]), "empty title": meta(title="  ")}
    for name, m in cases.items():
        row = compliance.metadata_check(m)
        assert row["name"] == "metadata_valid" and row["ok"] is False and row["severity"] == "block", name


def test_tag_length_counts_commas_and_the_quotes_around_multi_word_tags():
    assert compliance.tags_length(["Foo-Baz"]) == 7 and compliance.tags_length(["Foo Baz"]) == 9 and compliance.tags_length(["a", "b c"]) == 1 + 1 + 5


def test_sanitize_repairs_what_it_can_and_says_what_it_did():
    m = meta(title="Delphi <b>Oracle</b> " + "word " * 30, description="Intro > text\n\nChapters:\n0:00 A\n1:00 B\n2:00 C", tags=[f"tag number {i}" for i in range(60)])
    changes = compliance.sanitize(m)
    assert changes and compliance.metadata_check(m)["ok"] is True and "<" not in m["title"] and len(m["title"]) <= 100 and not m["title"].endswith(" ")
    assert "Chapters:\n0:00 A" in m["description"]


def test_sanitize_shortens_an_oversized_description_but_keeps_three_chapters():
    chapters = "\n".join(f"{i}:00 Chapter {i}" + " x" * 80 for i in range(1, 60))
    m = meta(description="Intro.\n\nChapters:\n0:00 Start\n" + chapters)
    compliance.sanitize(m)
    assert len(m["description"].encode()) <= 5000 and m["description"].count("\n0:00") + m["description"].count(":00 Chapter") >= 3


def test_copied_wording_is_measured_against_the_source():
    copied = meta(lines=[{"text": s.strip() + "."} for s in SOURCE.split(".") if s.strip()])
    row = compliance.originality(copied, SOURCE)
    assert row["name"] == "originality" and row["ok"] is False and row["severity"] == "block" and compliance.copied_lines(copied, SOURCE)
    own = meta(lines=[{"text": "People travelled for days to ask the priestess a single question about war, marriage or a journey across the sea."}] * 3)
    assert compliance.originality(own, SOURCE)["ok"] is True and compliance.copied_lines(own, SOURCE) == []
    assert compliance.originality(copied, "")["ok"] is True  # nothing to compare with


def test_kid_directed_wording_in_the_metadata_warns_but_a_story_about_children_does_not():
    assert compliance.kids_signals(meta(title="Fairy tale for kids: The Piper"))["ok"] is False
    assert compliance.kids_signals(meta(tags=["cartoon", "delphi"]))["severity"] == "warn"
    assert compliance.kids_signals(meta(title="Pied Piper of Hamelin: Did a Piper Lead 130 Children Away?"))["ok"] is True


def test_a_hook_is_supported_when_the_narration_says_what_it_promises():
    text = "The ancient Greeks considered Delphi the centre of the world, a spot marked by the stone monument called the Omphalos."
    assert compliance.hook_supported("CENTER OF THE WORLD?", text.replace("centre", "center")) is True
    assert compliance.hook_supported("PROPHECY OR PERFORMANCE?", text) is False
    assert compliance.hook_supported("THE", text) is True  # nothing to check


def test_every_rule_has_a_source_a_date_and_an_honest_status():
    for r in compliance.RULES:
        assert r["source"].startswith("https://") and r["verified"] and r["status"] in ("VERIFIED", "CONFLICTING", "UNVERIFIED"), r["id"]
    assert {r["status"] for r in compliance.RULES} >= {"VERIFIED", "CONFLICTING"}


def test_the_ai_art_style_stays_an_illustration_so_no_realistic_synthetic_disclosure_is_needed():
    assert "illustration" in aiart.STYLE.lower() and "photo" not in aiart.STYLE.lower()
