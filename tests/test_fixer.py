import json

import agentlog
import config
import fixer
import pytest
import reviewer
import topicqueue


def chk(name, ok, severity="block", detail=""):
    return {"name": name, "ok": ok, "severity": severity, "detail": detail or name}


def result(verdict, *failing):
    return {"verdict": verdict, "checks": [chk(n, False, s, d) for n, s, d in failing] + [chk("duration", True)], "at": "x"}


LINES = [{"text": f"Narration line number {i} about the sanctuary of Delphi and its priestess."} for i in range(8)]


def video(tmp_path, name, **over):
    d = tmp_path / "output" / name
    d.mkdir(parents=True)
    meta = {"topic": "The Oracle of Delphi", "format": "doc", "title": "The Oracle of Delphi: Prophecy or Performance", "description": "d" * 100,
            "tags": ["oracle of delphi", "oracle delphi percy jackson", "history stories for sleep", "oracle of delphi explained", "legends and folklore"],
            "lines": [dict(l) for l in LINES], "grounded": True, "sources": ["Wikipedia: Delphi (CC BY-SA 4.0), retold"], "approved": True,
            "approved_by": "reviewer-agent", **over}
    (d / "meta.json").write_text(json.dumps(meta))
    return d


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path / "output")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "TOPICS_FILE", tmp_path / "topics.json")
    monkeypatch.setattr(agentlog, "FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(agentlog.subprocess, "run", lambda *a, **k: None)
    topicqueue._write([])
    (tmp_path / "data").mkdir(exist_ok=True)
    state = {"results": [], "reviews": 0, "rerenders": []}

    def fake_review(folder, *a, **k):
        state["reviews"] += 1
        r = state["results"].pop(0)
        meta = json.loads((folder / "meta.json").read_text())
        reviewer.apply_verdict(meta, r)
        (folder / "meta.json").write_text(json.dumps(meta))
        return r

    monkeypatch.setattr(reviewer, "review", fake_review)
    monkeypatch.setattr(reviewer, "source_text", lambda meta: "Delphi was called Pytho. Excavated by the French from 1893.")
    state["rerender"] = lambda slug: state["rerenders"].append(slug)
    return state


def test_duplicate_title_gets_a_distinct_title_and_tags_are_cleaned_then_review_runs_again(tmp_path, world):
    video(tmp_path, "short-1", format="short", title="The Oracle of Delphi: Prophecy or Performance?")
    d = video(tmp_path, "doc-1", seo={"titles": ["oracle of delphi: was the pythia truly divine?"]},
              review=result("fail", ("duplicate_title", "block", "too similar to: The Oracle of Delphi: Prophecy or Performance?")))
    world["results"] = [result("pass")]
    out = fixer.fix("doc-1", chat=lambda p: {}, rerender=world["rerender"])
    meta = json.loads((d / "meta.json").read_text())
    assert meta["title"] == "Oracle of Delphi: Was the Pythia Truly Divine?"
    assert "oracle delphi percy jackson" not in meta["tags"] and out["verdict"] == "pass" and meta["fix_attempts"] == 1
    assert world["rerenders"] == [] and any("new title" in f for f in out["fixed"])


def test_when_no_search_title_is_distinct_the_writer_is_asked(tmp_path, world):
    video(tmp_path, "short-1", format="short", title="The Oracle of Delphi: Prophecy or Performance?")
    d = video(tmp_path, "doc-1", seo={"titles": ["The Oracle of Delphi: Prophecy or Performance"]},
              review=result("fail", ("duplicate_title", "block", "dup")))
    world["results"] = [result("pass")]
    fixer.fix("doc-1", chat=lambda p: {"titles": ["Who Spoke for Apollo at Delphi?"]}, rerender=world["rerender"])
    assert json.loads((d / "meta.json").read_text())["title"] == "Who Spoke for Apollo at Delphi?"


def test_unsupported_claims_in_a_documentary_are_rewritten_from_the_source_and_it_is_rendered_again(tmp_path, world):
    d = video(tmp_path, "doc-1", review=result("needs_human", ("claims", "human", "2 specific claims: 1938; 1999")))
    edit = {"edits": [{"index": 2, "text": "Some accounts say the oracle later lost its influence as old beliefs faded across Greece."},
                      {"index": 3, "text": "French diggers uncovered the site in 1893 and revealed its treasuries."},
                      {"index": 4, "text": "The shrine was rebuilt in 1999 by a famous king of the region."}]}
    world["results"] = [result("pass")]
    out = fixer.fix("doc-1", chat=lambda p: edit, rerender=world["rerender"])
    lines = [l["text"] for l in json.loads((d / "meta.json").read_text())["lines"]]
    assert lines[2].startswith("Some accounts say") and "1893" in lines[3]  # a year the source has is allowed
    assert lines[4] == LINES[4]["text"]  # a year the source lacks is refused, the old line stays
    assert world["rerenders"] == ["doc-1"] and out["verdict"] == "pass" and any("rewrote 2" in f for f in out["fixed"])


def test_a_short_with_unsupported_claims_is_set_aside_and_its_topic_requeued(tmp_path, world):
    d = video(tmp_path, "short-1", format="short", grounded=False, sources=[], review=result("needs_human", ("claims", "human", "3 claims")))
    out = fixer.fix("short-1", chat=lambda p: {}, rerender=world["rerender"])
    assert out["archived"] and not d.exists() and (tmp_path / "output_old" / "short-1" / "meta.json").exists()
    assert topicqueue.items() == ["The Oracle of Delphi"] and world["reviews"] == 0


def test_a_documentary_without_a_source_is_set_aside_to_be_made_again(tmp_path, world):
    d = video(tmp_path, "doc-2", grounded=False, review=result("needs_human", ("grounded", "human", "script is not tied to a source")))
    assert fixer.fix("doc-2", chat=lambda p: {}, rerender=world["rerender"])["archived"] and not d.exists()


def test_after_two_tries_it_gives_up_tells_you_and_does_not_try_a_third_time(tmp_path, world):
    d = video(tmp_path, "doc-3", seo={"titles": []}, review=result("fail", ("title_matches", "block", "title may mislead")))
    world["results"] = [result("fail", ("title_matches", "block", "title may mislead")), result("fail", ("title_matches", "block", "title may mislead"))]
    chat = lambda p: {"titles": ["A Quite Different Name for It"]}
    fixer.fix("doc-3", chat=chat, rerender=world["rerender"])
    assert not json.loads((d / "meta.json").read_text()).get("fix_gave_up")
    # the first review stays failing; the second try is the last
    meta = json.loads((d / "meta.json").read_text())
    meta["review"] = result("fail", ("title_matches", "block", "title may mislead"))
    (d / "meta.json").write_text(json.dumps(meta))
    fixer.fix("doc-3", chat=chat, rerender=world["rerender"])
    final = json.loads((d / "meta.json").read_text())
    assert final["fix_gave_up"] is True and final["fix_attempts"] == 2
    assert fixer.fix("doc-3", chat=chat, rerender=world["rerender"]) == {"skipped": "already tried"}
    assert any("Needs your eyes" in e["title"] for e in agentlog.recent())
