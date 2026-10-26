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


def test_frames_are_cut_so_the_burned_in_captions_do_not_show_under_the_hook_text():
    assert thumbnail.frame_filter(None).startswith("scale=")
    bottom = thumbnail.frame_filter("bottom")  # captions sit at the bottom: keep the top part of the frame
    assert bottom.startswith("crop=iw:ih*0.78:0:0,") and bottom.endswith(f"crop={thumbnail.W}:{thumbnail.H}")
    assert thumbnail.frame_filter("top").startswith("crop=iw:ih*0.78:0:ih*0.22,")


def test_frames_that_do_not_show_the_story_are_left_for_last_and_a_reading_that_cannot_run_changes_nothing():
    ranked = ["a", "b", "c", "d", "e", "f"]
    assert thumbnail.prefer_fitting(ranked, [1, 4, 5]) == ["b", "e", "f"]
    assert thumbnail.prefer_fitting(ranked, [2]) == ["c", "a", "b"]  # too few fit: filled up in rank order
    assert thumbnail.prefer_fitting(ranked, None) == ["a", "b", "c"] and thumbnail.prefer_fitting(ranked, []) == ["a", "b", "c"]


def test_fit_frames_asks_one_vision_question_and_returns_the_numbers_that_fit(tmp_path, monkeypatch):
    import videoinspect
    from PIL import Image

    files = []
    for i in range(3):
        f = tmp_path / f"f{i}.jpg"
        Image.new("RGB", (64, 36), (i * 40, 0, 0)).save(f)
        files.append(f)
    monkeypatch.setattr(videoinspect, "model_modalities", lambda: {"vision/model": ["text", "image"]})
    monkeypatch.setattr(thumbnail.llm, "load_config", lambda: {"models": {"review": "vision/model"}})
    sent = []

    def post(payload, key):
        sent.append(payload)
        return {"choices": [{"message": {"content": '{"fit": [0, 2]}'}, "finish_reason": "stop"}], "usage": {}}
    assert thumbnail.fit_frames(files, "Delphi: the oracle's sanctuary", post=post) == [0, 2]
    assert len(sent) == 1 and sent[0]["model"] == "vision/model" and sum(p.get("type") == "image_url" for p in sent[0]["messages"][0]["content"]) == 3
    assert "Delphi: the oracle's sanctuary" in sent[0]["messages"][0]["content"][0]["text"]
    assert thumbnail.fit_frames(files, "x", post=lambda p, k: (_ for _ in ()).throw(RuntimeError("down"))) is None
    monkeypatch.setattr(videoinspect, "model_modalities", lambda: {})
    assert thumbnail.fit_frames(files, "x", post=post) is None  # no model that accepts images: never block


PIPER = {"title": "Pied Piper of Hamelin: Real Story of the 130 Vanished Children", "topic": "The Pied Piper of Hamelin", "chapters": [{"title": "The Window", "start_line": 0}],
         "lines": [{"text": "A stained glass window of about 1300 in the church is the earliest mention of the piper and the children."}]}


def test_the_prompt_gives_no_template_example_and_a_story_detail_beats_a_generic_word():
    asked = []
    chat = lambda p: asked.append(p) or {"hooks": ["PIED PIPER TRUTH", "PIED PIPER 1300 WINDOW"]}
    assert thumbnail.hook_for(PIPER, chat=chat) == "PIED PIPER 1300 WINDOW"  # TRUTH is not in the title, but it is a generic word: a real detail wins
    assert "BELL WITCH TRUTH" not in asked[0] and "like PIED PIPER REAL STORY" not in asked[0]  # the old examples taught the model one template for every video
    assert "REAL STORY" in thumbnail.GENERIC_HOOK_WORDS or {"real", "story"} <= thumbnail.GENERIC_HOOK_WORDS
