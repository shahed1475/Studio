import thumbnail

META = {"title": "Delphi: Myth, Excavation and Ruins of the Oracle's Sanctuary", "chapters": [{"title": "The Navel of the World", "start_line": 0}, {"title": "Unearthing the Sanctuary", "start_line": 1}],
        "lines": [{"text": "The ancient Greeks considered Delphi the center of the world, marked by the stone called the Omphalos."},
                  {"text": "In 1893 the French Archaeological School uncovered the sanctuary after the village of Kastri was moved."}]}


def test_the_hook_is_one_the_narration_supports_and_not_one_already_used():
    asked = []
    chat = lambda p: asked.append(p) or {"hooks": ["PROPHECY OR PERFORMANCE?", "THE NAVEL OF THE WORLD", "CENTER OF THE WORLD?"]}
    assert thumbnail.hook_for(META, avoid=["the navel of the world"], chat=chat) == "CENTER OF THE WORLD?"  # the first is not in the story, the second was used
    assert "Navel of the World" in asked[0] and "1893" in asked[0] and "PROPHECY" not in asked[0].split("Not these")[0]


def test_the_hook_falls_back_to_the_title_words_when_nothing_usable_comes_back():
    def broken(p):
        raise RuntimeError("model down")
    assert thumbnail.hook_for(META, chat=broken) == "DELPHI: MYTH, EXCAVATION".replace(":", "").replace(",", "")
    assert thumbnail.hook_for(META, chat=lambda p: {"hooks": ["WHO KILLED THE ORACLE TONIGHT", "SECRET ALIEN PROPHECY"]}) == "DELPHI MYTH EXCAVATION"


def test_the_old_single_hook_answer_still_works():
    assert thumbnail.hook_for(META, chat=lambda p: {"hook": "Center of the world?"}) == "CENTER OF THE WORLD?"
