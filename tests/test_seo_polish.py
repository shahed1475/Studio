import seo


def test_titles_are_capitalised_and_cleaned():
    assert seo.polish_title("oracle of delphi: was the pythia truly divine?") == "Oracle of Delphi: Was the Pythia Truly Divine?"
    assert seo.polish_title('  "The Pied Piper — Real or Legend."  ') == "The Pied Piper - Real or Legend"
    assert seo.polish_title("Already Fine: Title Here") == "Already Fine: Title Here"
    assert seo.polish_title("a" * 40 + " " + "b" * 40, limit=50) == "A" + "a" * 39  # cut at a word, not in the middle of one
    assert len(seo.polish_title("x " * 60)) <= 70


def test_tags_from_other_things_are_dropped():
    meta = {"title": "Was the Oracle of Delphi Real?", "topic": "The Oracle of Delphi", "description": "The Pythia of Delphi gave prophecy at Apollo's temple.",
            "lines": [{"text": "Visitors asked the Pythia a question and received a prophecy."}]}
    tags = ["oracle of delphi", "oracle of delphi explained", "oracle delphi percy jackson", "oracle delphi assassins creed", "oracle of delphi music",
            "oracle of delphi lady d", "history stories for sleep", "oracle of delphi", "pythia prophecy", "unsolved mysteries season 1"]
    assert seo.relevant_tags(tags, seo.corpus_of(meta)) == ["oracle of delphi", "oracle of delphi explained", "history stories for sleep", "pythia prophecy"]
