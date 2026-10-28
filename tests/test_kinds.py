"""Kind skill cards (kinds.py, config/kinds.json): chosen by fixed rules, small, and only ever advice for packaging."""
import json

import clipper
import kinds
import packaging
import seo
import thumbnail


def meta(topic, title="", lines=(), anchors=(), chapters=()):
    return {"topic": topic, "title": title or topic, "lines": [{"text": t} for t in lines], "anchors": list(anchors), "chapters": [{"title": c} for c in chapters]}


def test_the_shipped_cards_are_complete_and_short():
    assert kinds.problems() == []
    assert set(kinds.names()) == {"legend", "mystery", "event", "person", "place"}


def test_real_topics_get_the_kind_a_viewer_would_name():
    assert kinds.classify(meta("Lost Army of Cambyses", "The Lost Army of Cambyses: 50,000 Soldiers Swallowed by Sand", anchors=["Siwa Oasis"])) == "mystery"
    assert kinds.classify(meta("La Llorona")) == "legend"
    assert kinds.classify(meta("Mami Wata", "Mami Wata: The Real Story Behind the Water Spirit")) == "legend"
    assert kinds.classify(meta("The Mystery of the Voynich Manuscript")) == "mystery"
    assert kinds.classify(meta("Collapse of Teotihuacan")) == "event"
    assert kinds.classify(meta("The Catacombs of Paris", chapters=["The old tunnels and tombs"])) == "place"


def test_one_stray_word_is_not_a_kind_and_junk_never_raises():
    assert kinds.classify(meta("The Tortoise and the Hare", chapters=["The fall of pride"])) == "story"
    for junk in ({}, {"topic": None, "lines": "x", "chapters": [1, None], "anchors": 5}, {"lines": [None]}):
        assert kinds.classify(junk) == "story"


def test_a_missing_or_bad_file_means_the_plain_default_card(tmp_path, monkeypatch):
    for text in (None, "{not json", json.dumps({"kinds": "no"})):
        if text is not None:
            (tmp_path / "k.json").write_text(text)
        monkeypatch.setattr(kinds, "FILE", tmp_path / "k.json")
        kinds._load.cache_clear()
        assert kinds.classify(meta("Lost Army of Cambyses")) == "story"
        assert kinds.card("mystery", "seo") == kinds.FALLBACK["seo"]
    kinds._load.cache_clear()


def test_a_card_line_is_cut_to_its_limit_and_unknown_kinds_get_the_default(monkeypatch):
    assert all(len(kinds.card(k, p)) <= kinds.MAX_CARD for k in kinds.names() for p in kinds.PARTS)
    assert kinds.card("nonsense", "hook") == kinds.card("story", "hook") != ""
    assert kinds.brief(meta("Lost Army of Cambyses"), "hook").startswith("Kind of video (mystery): ")


def test_the_card_reaches_the_seo_thumbnail_and_short_hook_prompts(tmp_path, monkeypatch):
    import scriptgen
    folder = tmp_path / "v"
    folder.mkdir()
    m = {**meta("Lost Army of Cambyses", lines=["An army vanished in the desert."]), "description": "Old.\n\nChapters:\n0:00 A", "tags": []}
    (folder / "meta.json").write_text(json.dumps(m))
    monkeypatch.setattr(seo, "core_phrase", lambda x: "lost army of cambyses")
    monkeypatch.setattr(seo, "suggest", lambda q: [])
    monkeypatch.setattr(seo, "competitors", lambda core: [])
    prompts = []
    monkeypatch.setattr(scriptgen, "_chat", lambda p, *a, **k: prompts.append(p) or {"titles": ["Lost Army of Cambyses: What Happened?"], "description_intro": "A lost army of Cambyses.", "tags": []})
    seo.make(folder)
    assert kinds.card("mystery", "seo") in prompts[0]
    seen = []
    thumbnail.hook_for(m, chat=lambda p: seen.append(p) or {"hooks": ["LOST ARMY"]})
    assert kinds.card("mystery", "thumb") in seen[0]
    seen.clear()
    clipper.hook(m, {"chapter": "The storm", "lines": [{"text": "A storm came."}]}, chat=lambda p: seen.append(p) or {"hook": "Where did 50,000 soldiers go?", "title": "T"})
    assert kinds.card("mystery", "hook") in seen[0]


def test_the_kind_nudges_the_title_ranking_only_a_little():
    plain, vanished = "Cambyses and the Army in the Desert", "Cambyses and the Army That Vanished"
    assert packaging.title_score(vanished, kind="mystery") > packaging.title_score(vanished)
    assert packaging.title_score(plain, kind="mystery") == packaging.title_score(plain)
    assert packaging.title_score(vanished, kind="mystery") - packaging.title_score(vanished) <= 0.4


def test_a_card_never_asks_for_a_lie():
    text = " ".join(kinds.card(k, p) for k in kinds.names() for p in kinds.PARTS).lower()
    for bad in ("you won't believe", "shocking", "invent", "make up", "fake"):
        assert bad not in text


def test_a_niche_tag_must_fit_the_kind_of_video():
    """28 Oct 2026: 'legends and folklore' sat on 18 of 25 videos, including a Persian army that vanished in 525 BC."""
    corpus = "lost army of cambyses persian army vanished western desert egypt 525 bc"
    tags = ["lost army of cambyses", "legends and folklore", "unsolved mysteries", "history stories for sleep", "folklore legends and myths", "persian army vanished"]
    mystery = seo.relevant_tags(tags, corpus, kind="mystery")
    assert "unsolved mysteries" in mystery and "history stories for sleep" in mystery and "persian army vanished" in mystery
    assert "legends and folklore" not in mystery and "folklore legends and myths" not in mystery
    legend = seo.relevant_tags(tags, corpus, kind="legend")
    assert "legends and folklore" in legend and "unsolved mysteries" not in legend
    assert "legends and folklore" in seo.relevant_tags(tags, corpus)  # no kind given: the old behaviour


def test_fixer_adds_only_the_niche_tags_that_fit(tmp_path):
    import fixer
    m = {**meta("Lost Army of Cambyses", lines=["An army vanished."]), "tags": [], "description": "d"}
    tags = fixer.clean_tags(m)
    assert "history stories for sleep" in tags and "legends and folklore" not in tags
