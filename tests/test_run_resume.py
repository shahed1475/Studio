import json

import run


def test_a_paid_script_is_resumed_not_regenerated(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "PENDING_DOC", tmp_path / "pending_doc.json")
    monkeypatch.setattr(run.config, "OUT", tmp_path / "out")
    got = []
    monkeypatch.setattr(run, "_produce_doc", lambda data, folder=None: got.append((data["title"], folder)) or tmp_path)
    monkeypatch.setattr(run.scriptgen, "doc_script", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not pay for a new script")))
    run.PENDING_DOC.write_text(json.dumps({"data": {"title": "Saved"}, "folder": "", "tries": 0}))
    run._cmd_doc()
    assert got == [("Saved", None)] and json.loads(run.PENDING_DOC.read_text())["tries"] == 1


def test_a_script_that_keeps_failing_is_dropped_after_three_tries(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "PENDING_DOC", tmp_path / "pending_doc.json")
    run.PENDING_DOC.write_text(json.dumps({"data": {"title": "Saved"}, "folder": "", "tries": run.MAX_RESUMES}))
    assert run._pending_doc() is None


def test_demand_rewards_subjects_people_search(monkeypatch):
    import seo
    monkeypatch.setattr(seo, "suggest", lambda q: ["pied piper of hamelin story", "pied piper real story", "pied piper song"] if "Piper" in q else [])
    assert seo.demand("The Pied Piper of Hamelin: a legend") == 0.3
    assert seo.demand("The 1817 Bell Farm accounts") == 0.0


def test_thumbnail_hook_prefers_one_that_names_the_subject():
    import thumbnail
    meta = {"title": "The Pied Piper of Hamelin Legend", "topic": "The Pied Piper of Hamelin", "lines": [{"text": "The Pied Piper led the children away from Hamelin. The real story is disputed."}],
            "chapters": [{"title": "The Pied Piper"}]}
    got = thumbnail.hook_for(meta, chat=lambda p: {"hooks": ["THE LOST WINDOW!", "PIED PIPER REAL STORY", "WHO WAS THE PIPER?"]})
    assert got == "WHO WAS THE PIPER?"  # it names the subject; the one with only the generic words REAL STORY comes after it (27 Oct audit: that template had spread to 3 of 6 thumbnails)
    assert got != "THE LOST WINDOW!"  # a hook that does not name the subject still loses


def test_new_videos_join_the_playlists_named_in_the_file(tmp_path):
    import upload
    f = tmp_path / "playlists.json"
    f.write_text(json.dumps({"doc": ["P1", "P2"], "short": ["P3"]}))
    calls = []

    class Items:
        def insert(self, part, body):
            calls.append(body["snippet"]["playlistId"])
            return type("R", (), {"execute": lambda self: {}})()

    class YT:
        def playlistItems(self):
            return Items()

    assert upload.join_playlists(YT(), "vid", "doc", f) == ["P1", "P2"] and upload.join_playlists(YT(), "vid", "short", f) == ["P3"]
    assert upload.join_playlists(YT(), "vid", "doc", tmp_path / "missing.json") == []


def test_a_saved_script_written_for_an_older_shorter_length_is_set_aside_not_rendered(tmp_path, monkeypatch):
    """20 Nov 2026: a 54-line, sourceless script saved under the 8 to 10 minute rule would have been Autopilot's next film after the owner chose 20 to 26 minutes."""
    import agentlog

    monkeypatch.setattr(run, "PENDING_DOC", tmp_path / "pending_doc.json")
    monkeypatch.setattr(run.scriptgen, "min_doc_words", lambda: 2556)
    short = {"data": {"title": "Old Pyramids", "grounded": False, "lines": [{"text": " ".join(["word"] * 21)} for i in range(54)]}, "folder": "", "tries": 0}
    run.PENDING_DOC.write_text(json.dumps(short))
    assert run._pending_doc() is None
    assert not run.PENDING_DOC.exists()
    kept = list(tmp_path.glob("pending_doc.set-aside-*.json"))
    assert len(kept) == 1 and json.loads(kept[0].read_text()) == short  # kept whole, never deleted
    ev = [json.loads(l) for l in agentlog.FILE.read_text().splitlines()]
    assert ev[-1]["title"].startswith("Set aside a saved script") and "1134 words in 54 lines" in ev[-1]["detail"] and "without a source" in ev[-1]["detail"]


def test_a_saved_script_of_the_current_length_is_still_resumed(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "PENDING_DOC", tmp_path / "pending_doc.json")
    monkeypatch.setattr(run.scriptgen, "min_doc_words", lambda: 2556)
    full = {"data": {"title": "New", "grounded": True, "lines": [{"text": " ".join(["word"] * 36)} for i in range(70)]}, "folder": "", "tries": 0}  # 70 joined lines, 2,520 words
    run.PENDING_DOC.write_text(json.dumps(full))
    assert run._pending_doc() == full and run.PENDING_DOC.exists()
