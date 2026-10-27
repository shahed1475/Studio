import base64
import json

import pytest

import config
import llm
import modelcfg
import videoinspect


@pytest.fixture
def world(tmp_path, monkeypatch):
    out = tmp_path / "output"
    folder = out / "doc-x"
    folder.mkdir(parents=True)
    (folder / "video.mp4").write_bytes(b"original-video")
    (folder / "meta.json").write_text(json.dumps({"title": "Bell Witch Legend", "chapters": [{"title": "The Farm", "start_line": 0}],
                                                  "lines": [{"text": "In 1817 a farm in Tennessee reported knocking sounds."}, {"text": "A voice was reported by the family."}]}))
    monkeypatch.setattr(config, "OUT", out)
    monkeypatch.setattr(llm, "load_config", lambda: {"daily_budget_usd": 5.0, "models": {}, "enabled": True})
    monkeypatch.setattr(llm, "spent_today", lambda now=None: 0.0)
    monkeypatch.setattr(llm, "key_for", lambda model: "k")
    monkeypatch.setattr(llm, "_account", lambda *a, **k: None)
    monkeypatch.setattr(videoinspect, "model_modalities", lambda *a, **k: {modelcfg.get("video_analysis"): ["text", "image", "video"]})

    def shrink(src, dst, height):
        dst.write_bytes(b"small-video-" + str(height).encode())
        return dst

    monkeypatch.setattr(videoinspect, "_shrink_for_analysis", shrink)
    monkeypatch.setattr(videoinspect, "_video_seconds", lambda path: 348.0)
    return folder


def answer(obj):
    return {"choices": [{"message": {"content": json.dumps(obj)}}]}


def test_our_own_video_is_sent_shrunk_as_video_url_to_the_configured_gemini_model(world):
    sent = []

    def post(body, key):
        sent.append(body)
        return answer({"summary": "A calm retelling of the Bell Witch story.", "problems": [{"at_s": 75, "what": "The picture shows a different house than the narration", "severity": "medium"}]})

    got = videoinspect.gemini_analyze(world, post=post)
    assert got["summary"].startswith("A calm") and got["problems"] == [{"at_s": 75, "what": "The picture shows a different house than the narration", "severity": "medium"}]
    body = sent[0]
    assert body["model"] == modelcfg.get("video_analysis")
    parts = body["messages"][0]["content"]
    video = next(p for p in parts if p["type"] == "video_url")
    assert video["video_url"]["url"] == "data:video/mp4;base64," + base64.b64encode(b"small-video-360").decode()
    text = parts[0]["text"]
    assert "Bell Witch Legend" in text and "In 1817 a farm" in text and "untrusted" in text
    assert "not a frame-by-frame" in got["coverage"] and "360p" in got["coverage"]
    assert json.loads((world / "video_analysis.json").read_text())["summary"] == got["summary"]


def test_only_our_own_videos_are_analysed(world, tmp_path):
    elsewhere = tmp_path / "other"
    elsewhere.mkdir()
    (elsewhere / "video.mp4").write_bytes(b"x")
    got = videoinspect.gemini_analyze(elsewhere, post=lambda b, k: pytest.fail("must not be sent"))
    assert "own videos" in got["error"]


def test_a_video_still_too_big_after_shrinking_spends_nothing(world, monkeypatch):
    monkeypatch.setattr(videoinspect, "ANALYSIS_MAX_BYTES", 5)
    got = videoinspect.gemini_analyze(world, post=lambda b, k: pytest.fail("must not be sent"))
    assert "too large" in got["error"]


def test_no_analysis_without_a_video_capable_model_or_credit(world, monkeypatch):
    monkeypatch.setattr(videoinspect, "model_modalities", lambda *a, **k: {modelcfg.get("video_analysis"): ["text", "image"]})
    assert "video" in videoinspect.gemini_analyze(world, post=lambda b, k: pytest.fail("no"))["error"]
    monkeypatch.setattr(videoinspect, "model_modalities", lambda *a, **k: {modelcfg.get("video_analysis"): ["text", "image", "video"]})
    monkeypatch.setattr(llm, "spent_today", lambda now=None: 9.0)
    assert "cap" in videoinspect.gemini_analyze(world, post=lambda b, k: pytest.fail("no"))["error"]


def test_a_failed_or_nonsense_answer_is_an_error_not_a_pass_and_problems_are_cleaned(world):
    assert "error" in videoinspect.gemini_analyze(world, post=lambda b, k: 1 / 0)
    assert "error" in videoinspect.gemini_analyze(world, post=lambda b, k: {"choices": [{"message": {"content": "no json"}}]})
    got = videoinspect.gemini_analyze(world, post=lambda b, k: answer({"summary": "ok", "problems": [{"at_s": "x", "what": "bad time"}, {"at_s": 10, "what": "See evil.com now"},
                                                                                              {"at_s": 20, "what": "A real issue", "severity": "weird"}] + [{"at_s": i, "what": f"p{i}"} for i in range(30)]}))
    whats = [p["what"] for p in got["problems"]]
    assert "A real issue" in whats and not any("evil.com" in w for w in whats) and not any(w == "bad time" for w in whats) and len(whats) <= 12
    assert all(p["severity"] in ("low", "medium", "high") for p in got["problems"])


def test_the_analyze_video_command_prints_the_findings_and_what_was_covered(world, monkeypatch, capsys):
    import run

    monkeypatch.setattr(videoinspect, "gemini_analyze", lambda folder, post=None: {"model": "m", "summary": "A calm retelling.", "problems": [{"at_s": 75, "what": "Wrong house", "severity": "medium"}],
                                                                                    "coverage": "sent at 360p, not a frame-by-frame inspection", "cost": 0.12})
    monkeypatch.setattr("sys.argv", ["run.py", "analyze-video", "doc-x"])
    run.main()
    out = capsys.readouterr().out
    assert "A calm retelling." in out and "1:15" in out and "Wrong house" in out and "not a frame-by-frame" in out
    monkeypatch.setattr(videoinspect, "gemini_analyze", lambda folder, post=None: {"error": "the daily spending cap is used up"})
    with pytest.raises(SystemExit, match="cap is used up"):
        run.main()


def test_the_score_thumbnails_command_scores_the_saved_candidates_without_changing_the_record(world, monkeypatch, capsys):
    import run
    import thumbscore
    from PIL import Image

    meta = json.loads((world / "meta.json").read_text())
    (world / "thumbs").mkdir()
    for n in ("thumbs/art-a.jpg", "thumbs/thumb-1.jpg"):
        Image.new("RGB", (64, 36), (9, 9, 9)).save(world / n)
    (world / "meta.json").write_text(json.dumps({**meta, "thumb_hook": "BELL WITCH VOICE", "thumbnails": ["thumbs/art-a.jpg", "thumbs/thumb-1.jpg"], "thumbnail": "thumbs/art-a.jpg"}))
    before = (world / "meta.json").read_text()
    monkeypatch.setattr(thumbscore, "score", lambda paths, title, hook, post=None: [{"index": 1, "total": 8.2, "parts": {"focal_point": 8.0}}, {"index": 0, "total": 6.1, "parts": {"focal_point": 6.0}}])
    monkeypatch.setattr("sys.argv", ["run.py", "score-thumbnails", "doc-x"])
    run.main()
    out = capsys.readouterr().out
    assert out.index("thumb-1.jpg") < out.index("art-a.jpg") and "8.2" in out and "6.1" in out
    assert (world / "meta.json").read_text() == before


def test_the_request_leaves_room_for_the_models_thinking(world):
    """Real run, 27 Oct 2026: Gemini 3.1 Pro spent the whole 1,500-token limit thinking (finish_reason length) and returned 261 characters of cut-off JSON."""
    sent = []
    videoinspect.gemini_analyze(world, post=lambda b, k: sent.append(b) or answer({"summary": "ok", "problems": []}))
    assert sent[0]["max_tokens"] >= 4000 and sent[0]["reasoning"] == {"effort": "low"}


def test_a_reply_cut_off_by_the_output_limit_says_so_instead_of_no_json(world):
    cut = {"choices": [{"finish_reason": "length", "message": {"content": '```json\n{"summary": "The video'}}]}
    got = videoinspect.gemini_analyze(world, post=lambda b, k: cut)
    assert "ran out of output room" in got["error"]


def test_problems_at_a_time_after_the_end_of_the_video_are_dropped_and_counted(world):
    """Real runs, 27 Oct 2026: Gemini listed problems at 7:33, 8:20 and 9:00 in a 5:48 video. A time that cannot exist is a sign its other findings need checking."""
    got = videoinspect.gemini_analyze(world, post=lambda b, k: answer({"summary": "ok", "problems": [{"at_s": 75, "what": "Wrong house", "severity": "low"}, {"at_s": 453, "what": "Repeated image", "severity": "medium"},
                                                                                                  {"at_s": 540, "what": "Another repeat", "severity": "medium"}]}))
    assert [p["at_s"] for p in got["problems"]] == [75] and got["ignored_impossible_times"] == 2
