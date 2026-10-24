import packaging

CORE = "pied piper hamelin"


def test_a_title_with_the_phrase_up_front_beats_a_vague_question():
    good = packaging.title_score("Pied Piper of Hamelin: Real Story of the 130 Vanished Children", CORE)
    vague = packaging.title_score("What Do the 1817 Farm Accounts Actually Describe?", "bell witch")
    assert good > vague + 2


def test_ranking_puts_the_best_option_first_and_punishes_near_duplicates():
    opts = ["A Legend Told Slowly", "Pied Piper of Hamelin: Real Story Behind the Legend", "Hamelin Piper Tale"]
    assert packaging.rank_titles(opts, CORE)[0] == opts[1]
    other = ["Pied Piper of Hamelin: Real Story Behind the Legend"]
    assert packaging.rank_titles(opts, CORE, other)[0] != opts[1]


def test_shouting_titles_score_low():
    assert packaging.title_score("THE PIED PIPER OF HAMELIN SECRET REVEALED", CORE) < packaging.title_score("The Pied Piper of Hamelin Secret Revealed", CORE)


def test_audit_warns_about_a_buried_phrase_a_blank_description_start_and_a_repeating_thumbnail():
    meta = {"title": "A Calm Story About Something Old and Hidden in Hamelin Town", "description": "Welcome back to the channel everyone.",
            "seo": {"core": CORE}, "thumb_hook": "HAMELIN TOWN STORY"}
    by = {r["name"]: r for r in packaging.audit(meta)}
    assert not by["seo_title_front"]["ok"] and not by["seo_description_150"]["ok"]
    assert all(r["severity"] == "warn" for r in by.values())
    good = {"title": "Pied Piper of Hamelin: Real Story", "description": "The Pied Piper of Hamelin led 130 children away in 1284.", "seo": {"core": CORE}, "thumb_hook": "PIED PIPER TRUTH?"}
    assert all(r["ok"] for r in packaging.audit(good))
    assert not {r["name"]: r for r in packaging.audit({**good, "thumb_hook": "PIED PIPER REAL STORY"})}["seo_thumbnail_text"]["ok"]


def test_the_playlist_link_goes_before_the_credits_only_when_the_owner_set_one(tmp_path, monkeypatch):
    import json

    import compliance
    f = tmp_path / "playlists.json"
    assert compliance._cta(f) == ""
    f.write_text(json.dumps({"doc": ["P"], "cta": "More stories: https://www.youtube.com/playlist?list=P"}))
    assert compliance._cta(f) == "\n\nMore stories: https://www.youtube.com/playlist?list=P"
