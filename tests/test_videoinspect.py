import json
import subprocess

import config
import llm
import pytest
import videoinspect as vi

MODALITIES = {"anthropic/claude-haiku-5.5": ["text", "image"], "nvidia/nemotron-3.5-super-vl:free": ["text", "image"], "deepseek/text-only": ["text"]}


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path / "output")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(vi, "ROOT", tmp_path / "research")
    monkeypatch.setattr(vi, "MODALITY_CACHE", tmp_path / "mod.json")
    monkeypatch.setattr(llm, "USAGE_FILE", tmp_path / "usage.json")
    monkeypatch.setattr(vi, "model_modalities", lambda get=None, now=None: MODALITIES)
    monkeypatch.setattr(llm, "load_config", lambda: {"models": {"script": "deepseek/text-only", "review": "", "cheap": ""}})
    return tmp_path


def make_video(folder, seconds=6):
    folder.mkdir(parents=True, exist_ok=True)
    f = folder / "video.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=duration={seconds}:size=320x240:rate=10", "-f", "lavfi", "-i", f"sine=frequency=300:duration={seconds}",
                    "-shortest", "-pix_fmt", "yuv420p", str(f)], check=True)
    return f


def reply(**over):
    return {"choices": [{"message": {"content": json.dumps({"hook": "opens on a test card", "structure": ["one scene"], "pacing": "steady", "editing_patterns": [], "visual_storytelling": "n/a",
                                                          "caption_issues": [], "picture_issues": [{"t": 2.0, "issue": "plain test pattern"}], "repeated_visuals": False,
                                                          "strengths": [], "problems": [], "cannot_tell": ["audio content"], **over})}}], "usage": {"prompt_tokens": 5, "completion_tokens": 5, "cost": 0.001}}


def test_youtube_links_ids_and_source_kinds(world):
    assert vi.parse_youtube_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10s") == "dQw4w9WgXcQ"
    assert vi.parse_youtube_id("https://youtu.be/dQw4w9WgXcQ?si=x") == "dQw4w9WgXcQ" and vi.parse_youtube_id("https://youtube.com/shorts/abc123XYZ_-") == "abc123XYZ_-"
    assert vi.parse_youtube_id("the oracle of delphi") is None
    make_video(world / "output" / "my-slug")
    assert vi.kind_of("my-slug") == "slug" and vi.kind_of("https://archive.org/download/x/y.mp4") == "openmedia"
    assert vi.kind_of("https://example.com/video.mp4") == "link" and vi.kind_of("a topic about delphi") == "topic"


def test_vision_model_is_checked_against_the_model_list_never_assumed():
    cfg = {"models": {"script": "deepseek/text-only", "review": "anthropic/claude-haiku-5.5", "cheap": ""}}
    assert vi.pick_vision_model(cfg, MODALITIES) == ("anthropic/claude-haiku-5.5", "the review model accepts images")
    cfg["models"]["review"] = "deepseek/text-only"  # a text-only model keeps its text jobs; a vision model is borrowed
    assert vi.pick_vision_model(cfg, MODALITIES)[0] == "anthropic/claude-haiku-5.5" and "fallback" in vi.pick_vision_model(cfg, MODALITIES)[1]
    assert vi.pick_vision_model(cfg, {})[0] is None and "could not be read" in vi.pick_vision_model(cfg, {})[1]


def test_frame_times_mix_even_spacing_and_scene_cuts_without_crowding():
    times = vi.pick_times(60.0, [5.0, 5.3, 20.0, 41.0, 55.0], 8)
    assert len(times) <= 8 and times == sorted(times) and all(b[0] - a[0] >= 0.8 for a, b in zip(times, times[1:]))
    assert {w for _, w in times} == {"even", "scene cut"} and all(0 <= t < 60 for t, _ in times)
    assert vi.pick_times(10.0, [], 4) and all(w == "even" for _, w in vi.pick_times(10.0, [], 4))


def test_a_studio_video_is_measured_sampled_read_by_the_vision_model_and_the_limits_are_stated(world):
    d = world / "output" / "v1"
    make_video(d)
    (d / "meta.json").write_text(json.dumps({"lines": [{"text": "A first line."}, {"text": "A second line."}], "title": "V1"}))
    seen = []
    report = vi.inspect_source("v1", "check pictures", 6, post=lambda payload, key: seen.append(payload) or reply())
    c, out = report["coverage"], world / "research"
    assert 1 <= c["frames_inspected"] <= 6 and c["whole_video_watched"] is False and c["speech_recognition"] is False and c["vision_model"] == "anthropic/claude-haiku-5.5"
    assert "not a full viewing" in c["statement"] and "scene cuts" in c["statement"] and "studio's own script" in c["transcript"]
    run_dir = next(out.iterdir())
    assert {p.name for p in run_dir.iterdir()} >= {"metadata.json", "frames.json", "analysis.json", "report.md", "errors.json", "transcript.txt", "frames"}
    images = [p for p in seen[0]["messages"][0]["content"] if p["type"] == "image_url"]
    assert len(images) == c["frames_inspected"] and "NOT watched the whole video" in seen[0]["messages"][0]["content"][0]["text"]
    assert report["analysis"]["picture_issues"][0]["t"] == 2.0 and "plain test pattern" in (run_dir / "report.md").read_text()


def test_without_a_vision_model_it_still_measures_and_says_the_analysis_could_not_run(world, monkeypatch):
    d = world / "output" / "v2"
    make_video(d)
    monkeypatch.setattr(vi, "model_modalities", lambda get=None, now=None: {})
    report = vi.inspect_source("v2", frames=4, post=lambda p, k: pytest.fail("no model, no call"))
    assert "analysis" not in report and report["coverage"]["vision_model"] is None and report["stats"]["scene_cuts"] >= 0
    assert any(e["step"] == "vision" for e in report["errors"]) and "no model that accepts images" in json.dumps(report["errors"])


class FakeYT:
    def videos(self):
        return type("V", (), {"list": lambda s, **k: type("E", (), {"execute": lambda s2: {"items": [{"snippet": {"title": "Big Mystery", "channelTitle": "Some Channel", "channelId": "UC1", "publishedAt": "2026-01-02T00:00:00Z",
                                                                                                             "description": "d", "thumbnails": {"high": {"url": "https://i.ytimg.com/vi/x/hq.jpg"}}},
                                                                                              "contentDetails": {"duration": "PT10M5S", "caption": "true"}, "statistics": {"viewCount": "1234"}, "status": {"license": "youtube"}}]}})()})()


def test_a_youtube_link_gets_metadata_and_the_thumbnail_but_the_video_is_never_downloaded(world, monkeypatch):
    monkeypatch.setattr(vi.requests, "get", lambda url, **k: type("R", (), {"content": b"\xff\xd8\xff fake jpeg", "raise_for_status": lambda s: None})())
    downloads = []
    monkeypatch.setattr(vi, "fetch_open_media", lambda *a, **k: downloads.append(a))
    import trendwatch
    monkeypatch.setattr(trendwatch, "iso_seconds", lambda s: 605)
    report = vi.inspect_source("https://www.youtube.com/watch?v=dQw4w9WgXcQ", yt=FakeYT(), post=lambda p, k: reply())
    c = report["coverage"]
    assert c["metadata"] and c["thumbnail"] and c["frames_inspected"] == 0 and c["whole_video_watched"] is False and downloads == []
    assert "thumbnail only" in c["statement"] and "not a viewing of the video" in c["statement"]
    assert "official API gives no transcript" in c["transcript"] and any("terms do not allow downloading" in e["error"] for e in report["errors"])
    assert json.loads((world / "research" / report["dir"].split("/")[-1] / "metadata.json").read_text())["title"] == "Big Mystery"


def test_a_missing_video_is_an_error_not_a_made_up_report(world):
    class Gone:
        def videos(self):
            return type("V", (), {"list": lambda s, **k: type("E", (), {"execute": lambda s2: {"items": []}})()})()
    report = vi.inspect_source("https://youtu.be/dQw4w9WgXcQ", yt=Gone(), post=lambda p, k: pytest.fail("nothing to read"))
    assert any("no video with this id" in e["error"] for e in report["errors"]) and "analysis" not in report


def test_only_open_collections_may_be_downloaded_and_other_links_are_refused(world):
    with pytest.raises(ValueError, match="open collections"):
        vi.fetch_open_media("https://example.com/a.mp4", world)
    report = vi.inspect_source("https://example.com/video.mp4", post=lambda p, k: pytest.fail("not accessed"))
    assert report["coverage"]["statement"] == "Nothing was accessed." and report["errors"]


def test_a_topic_is_researched_with_addresses_passages_and_revision_dates(world, monkeypatch):
    import wikipedia
    monkeypatch.setattr(wikipedia, "facts_multi", lambda topic, n=3, chars_each=0: [{"title": "Delphi", "url": "https://en.wikipedia.org/wiki/Delphi", "text": "Delphi was an oracle. " * 40, "revised": "2026-09-01T00:00:00Z"}])
    report = vi.inspect_source("the oracle of delphi", post=lambda p, k: pytest.fail("no images"))
    src = report["research"]["sources"][0]
    assert src["url"].endswith("/Delphi") and src["revised"].startswith("2026-09") and src["license"] == "CC BY-SA 4.0"
    assert "secondary" in src["type"] and "No primary sources" in report["coverage"]["statement"]


def test_visual_review_rows_are_warnings_and_carry_the_coverage_statement(world):
    d = world / "output" / "v3"
    make_video(d)
    rows = vi.visual_review(d, 4, post=lambda p, k: reply(repeated_visuals=True))
    assert {r["name"] for r in rows} == {"captions_readable", "pictures_fit_story", "no_repeated_pictures", "visual_coverage"}
    assert all(r["severity"] in ("warn", "info") for r in rows) and not next(r for r in rows if r["name"] == "no_repeated_pictures")["ok"]
    assert "not a full viewing" in next(r for r in rows if r["name"] == "visual_coverage")["detail"]


def test_a_reply_cut_off_at_the_token_limit_is_an_error_not_a_half_analysis(world):
    d = world / "output" / "v4"
    make_video(d)
    cut = reply()
    cut["choices"][0]["finish_reason"] = "length"
    report = vi.inspect_source("v4", frames=3, post=lambda p, k: cut)
    assert "analysis" not in report and any("cut off" in e["error"] for e in report["errors"])


def test_mood_pictures_are_noted_but_only_wrong_ones_fail_the_row(world):
    d = world / "output" / "v4"
    make_video(d)
    issues = [{"t": 3, "kind": "mood", "issue": "atmospheric fire"}, {"t": 9, "kind": "wrong", "issue": "map of India for Sumatra"}, {"t": 12, "issue": "no kind given"}]
    rows = vi.visual_review(d, 4, post=lambda p, k: reply(picture_issues=issues))
    fit = next(r for r in rows if r["name"] == "pictures_fit_story")
    assert not fit["ok"] and fit["detail"].count(" s: ") == 2 and "fire" not in fit["detail"]  # an issue with no kind counts as wrong
    assert "1 atmospheric" in next(r for r in rows if r["name"] == "pictures_mood")["detail"]
    only_mood = vi.visual_review(d, 4, post=lambda p, k: reply(picture_issues=issues[:1]))
    assert next(r for r in only_mood if r["name"] == "pictures_fit_story")["ok"]
