#!/usr/bin/env python3
"""YouTube Shorts automation.

  python run.py ideas [N]        add N topic ideas to the queue
  python run.py research [N]     daily: trends in N countries -> original topic ideas
  python run.py make [topic]     make one video (next queued topic if none given)
  python run.py doc [topic]      make a 16:9 documentary with archival images
  python run.py redo NAME        re-render a documentary from its saved script
  python run.py batch N          make N videos from the queue
  python run.py thumbs NAME [HOOK TEXT]   make 3 thumbnail options
  python run.py seo NAME         search-based title options, description and tags
  python run.py review NAME      reviewer agent checks a finished video
  python run.py autopilot tick|status   one automation pass / show state
  python run.py newswatch        weekly YouTube security/policy news digest
  python run.py newsvideo        make the next queued YouTube-news video
  python run.py subtitles NAME [--burn]   subtitles for a finished video (.srt, and burned in with --burn)
  python run.py trends           weekly niche trend research (YouTube API) + original topic ideas
  python run.py channels         study your reference channels (top videos, themes) + proposals
  python run.py branding "NAME" "TAGLINE"   profile picture, banner and description in branding/
  python run.py approve NAME     mark a reviewed video as ready to upload
  python run.py upload NAME [--public] [--at 2026-10-20T14:00:00Z]
  python run.py list             show videos and their status
"""
import json
import re
import shutil
import sys
from pathlib import Path

import archive_video
import config
import editprofile
import footage
import subtitles
import render
import scriptgen
import tts


def _queue() -> list[str]:
    return json.loads(config.TOPICS_FILE.read_text()) if config.TOPICS_FILE.exists() else []


def _save_queue(q: list[str]) -> None:
    config.TOPICS_FILE.write_text(json.dumps(q, indent=2))


STALE = {"approved", "approved_by", "review", "publish_at", "autopilot_fails"}


def reset_for_rerender(data: dict) -> dict:
    """A re-rendered video is a new video: drop approval, review and schedule from the old render."""
    return {k: v for k, v in data.items() if k not in STALE}


def unique_folder(base: Path) -> Path:
    """Never write into a folder that already holds a video (it could be one that was uploaded)."""
    if not base.exists():
        return base
    n = 2
    while (base.parent / f"{base.name}-{n}").exists():
        n += 1
    return base.parent / f"{base.name}-{n}"


def cmd_ideas(n: int = 10) -> None:
    q = _queue()
    new = [t for t in scriptgen.ideas(n) if t not in q]
    _save_queue(q + new)
    print("\n".join(f"+ {t}" for t in new) or "no new ideas")


def cmd_research(n: int = 3) -> None:
    import research

    q = _queue()
    new = [t for t in research.run(n) if t not in q]
    _save_queue(q + new)
    print("\n".join(f"+ {t}" for t in new) or "nothing new")


def cmd_make(topic: str | None = None) -> Path:
    q = _queue()
    if not topic:
        if not q:
            cmd_ideas(10)
            q = _queue()
        topic = q.pop(0)
        _save_queue(q)
    print(f"Topic: {topic}")
    data = None
    import wikipedia

    src = wikipedia.facts_for(topic, chars=3500)
    for attempt in range(3):
        try:
            data = scriptgen.script(topic, grounded=src[1] if src else None)
            if src:
                data["sources"] = [f"Wikipedia: {src[0]} (CC BY-SA 4.0), retold in our own words"]
            data["anchors"] = anchor_terms(topic, data.get("anchors", []), src[0] if src else "")
            break
        except Exception as e:  # bad JSON or too short: ask again
            print(f"  script attempt {attempt + 1} failed: {e}")
    if not data:
        raise SystemExit("could not generate a script")
    return _produce_short(data, topic)


def _produce_short(data: dict, topic: str, requeue: bool = True, pool_size: int = 6, min_unique: int = 4) -> Path:
    """Voice, footage, render and metadata for a finished Short script. requeue: put the topic back in the queue if footage is missing."""
    slug = re.sub(r"[^a-z0-9]+", "-", data["title"].lower()).strip("-")[:50]
    folder = unique_folder(config.OUT / slug)
    work = folder / "work"
    folder.mkdir(parents=True, exist_ok=True)
    print("Voice + captions...")
    prof = editprofile.load()
    narration, ass, durations = tts.narrate([l["text"] for l in data["lines"]], work, prof["sentence_pause_ms"] / 1000)
    print("Footage...")
    if config.PEXELS_KEY:
        clips = [footage.clip_for(l["visual"]) for l in data["lines"]]
        credits = footage.collect_credits(clips)
    else:  # archive pictures: only ones that name the subject
        clips, credits, stats = footage.scene_images(data["lines"], topic, data.get("anchors") or [], pool_size=pool_size, judge=_image_judge(topic))
        data["footage"] = stats
        if stats["missing"] or stats["unique"] < min_unique:
            clips = [None] * len(clips)
    if not footage.enough_footage(clips):
        if requeue:
            _save_queue([topic] + _queue())  # keep the topic for a later try
        shutil.rmtree(folder, ignore_errors=True)
        raise SystemExit("not enough footage found for this Short" + ("; topic put back in the queue" if requeue else ""))
    print("Rendering...")
    render.render(clips, durations, narration, ass, work, folder / "video.mp4", loudness=prof["target_lufs"])
    shutil.copy(work / "words.json", folder / "words.json")
    subtitles.write_files(folder, subtitles.load_words(work / "words.json"))
    shutil.rmtree(work)
    data["subtitles"] = "burned"
    data["credits"] = credits
    data["approved"] = False
    (folder / "meta.json").write_text(json.dumps(data, indent=2))
    print(f"\nDone: {folder / 'video.mp4'}\nTitle: {data['title']}\nWatch it, then: python run.py approve {folder.name}")
    return folder


def cmd_doc(topic: str | None = None) -> Path:
    import random

    q = _queue()
    if not topic:
        if not q:
            cmd_research(3)
            q = _queue()
        topic = q.pop(0)
        _save_queue(q)
    print(f"Documentary: {topic}")
    data = None
    import wikipedia

    src = wikipedia.facts_for(topic)
    print(f"  source article: {src[0] if src else 'none found (script will be flagged for a human check)'}")
    for attempt in range(4):
        try:
            data = scriptgen.doc_script(topic, grounded=src[1] if src else None)
            if src:
                data["sources"] = [f"Wikipedia: {src[0]} (CC BY-SA 4.0), retold in our own words", "https://en.wikipedia.org/wiki/" + src[0].replace(" ", "_")]
            data["anchors"] = anchor_terms(topic, data.get("anchors", []), src[0] if src else "")
            break
        except Exception as e:
            print(f"  script attempt {attempt + 1} failed: {e}")
    if not data:
        raise SystemExit("could not generate a documentary script")
    return _produce_doc(data)


_GENERIC_TERMS = {"the", "mystery", "mysteries", "legend", "real", "true", "story", "secret", "secrets", "truth", "unsolved"}


def anchor_terms(topic: str, anchors: list[str], article: str = "") -> list[str]:
    """Names an on-topic image will carry: the script's anchors plus the topic's and the source article's own names."""
    parts = re.split(r"\s+(?:of|and|in|at|for)\s+|[:,?]", f"{topic}|{article}".replace("|", ","))
    out: list[str] = []
    for a in [*anchors, *parts]:
        a = " ".join(w for w in a.strip().split() if w.lower() not in _GENERIC_TERMS)
        if len(a) >= 4 and a.lower() not in [o.lower() for o in out]:
            out.append(a)
    return out


def _image_judge(topic: str):
    def judge(titles: list[str]) -> list[str]:
        try:
            out = scriptgen._chat(
                f"A documentary about: {topic}. Below are archive image file names. Return the numbers of the ones that "
                "plausibly show that subject (its place, people, artwork, objects or maps). Reject anything about a "
                "different subject that merely shares a word (a space mission, an aircraft, a castle elsewhere, a flag).\n"
                + "\n".join(f"{i}: {t}" for i, t in enumerate(titles)) + '\n\nReturn JSON: {"keep": [numbers]}'
            )
            keep = {int(n) for n in out.get("keep", []) if str(n).isdigit()}
            return [t for i, t in enumerate(titles) if i in keep]
        except Exception:
            return titles
    return judge


def _produce_doc(data: dict, folder: Path | None = None) -> Path:
    import random

    slug = "doc-" + re.sub(r"[^a-z0-9]+", "-", data["title"].lower()).strip("-")[:45]
    folder = folder or unique_folder(config.OUT / slug)
    work = folder / "work"
    folder.mkdir(parents=True, exist_ok=True)
    print("Voice...")
    prof = editprofile.load()
    narration, _ass, durations = tts.narrate([l["text"] for l in data["lines"]], work, prof["sentence_pause_ms"] / 1000)
    print("Archival images (only pictures that name the subject)...")
    anchors = data.get("anchors") or []
    clips, credits, stats = footage.scene_images(data["lines"], data["topic"], anchors, judge=_image_judge(data["topic"]))
    if stats["missing"] or stats["unique"] < 6:
        shutil.rmtree(folder, ignore_errors=True)
        raise SystemExit(f"only {stats['unique']} on-topic images found ({stats['missing']} scenes without one); "
                         "not rendering a video of unrelated pictures")
    music = sorted(Path("music").glob("*.mp3")) if Path("music").exists() else []
    print(f"Rendering ({sum(c is not None for c in clips)}/{len(clips)} scenes have footage)...")
    words = subtitles.load_words(work / "words.json")
    doc_ass = None
    if config.DOC_SUBTITLES:
        doc_ass = work / "doc_captions.ass"
        doc_ass.write_text(subtitles.to_ass(subtitles.build_cues(words), (1920, 1080)))
    render.render(clips, durations, narration, doc_ass, work, folder / "video.mp4",
                  size=(1920, 1080), music=random.choice(music) if music else None, loudness=prof["target_lufs"])
    shutil.copy(work / "words.json", folder / "words.json")
    subtitles.write_files(folder, words)
    shutil.rmtree(work)
    starts, t = [], 0.0
    for n, ch in enumerate(data["chapters"], 1):
        t = sum(durations[: ch["start_line"]])
        starts.append(f"{int(t // 60)}:{int(t % 60):02d} {ch['title'] or f'Part {n}'}")
    intro = data["description"].split("\n\nChapters:")[0].split("\n\nSources:")[0]
    src = "".join(f"\n{x}" for x in data.get("sources", []))
    data["description"] = intro + (f"\n\nSources:{src}" if src else "") + "\n\nChapters:\n" + "\n".join(starts)
    data["footage"] = stats
    data["credits"] = credits
    data["subtitles"] = "burned" if config.DOC_SUBTITLES else "srt"
    data["approved"] = False
    (folder / "meta.json").write_text(json.dumps(data, indent=2))
    print(f"\nDone: {folder / 'video.mp4'}\nTitle: {data['title']}\nWatch it, then: python run.py approve {folder.name}")
    return folder



def cmd_redo(name: str) -> None:
    """Re-render an existing documentary from its saved script (keeps the text, redoes voice, images, video)."""
    data = reset_for_rerender(json.loads((config.OUT / name / "meta.json").read_text()))
    _produce_doc(data, config.OUT / name)


def cmd_thumbs(name: str, hook: str | None = None) -> None:
    import thumbnail

    folder = config.OUT / name
    meta = json.loads((folder / "meta.json").read_text())
    if hook:
        meta["thumb_hook"] = hook
        (folder / "meta.json").write_text(json.dumps(meta, indent=2))
    thumbnail.make(folder, hook)


def cmd_approve(name: str) -> None:
    p = config.OUT / name / "meta.json"
    meta = json.loads(p.read_text())
    meta["approved"] = True
    p.write_text(json.dumps(meta, indent=2))
    print(f"approved {name}")


def cmd_upload(name: str, args: list[str]) -> None:
    import upload

    at = args[args.index("--at") + 1] if "--at" in args else None
    vid = upload.upload(config.OUT / name, "public" if "--public" in args else "private", at)
    print(f"Uploaded: https://youtube.com/shorts/{vid}")


def cmd_list() -> None:
    for m in sorted(config.OUT.glob("*/meta.json")):
        d = json.loads(m.read_text())
        state = "uploaded" if d.get("video_id") else "approved" if d.get("approved") else "needs review"
        print(f"{state:13} {m.parent.name}")


def main() -> None:
    a = sys.argv[1:]
    if not a:
        print(__doc__)
    elif a[0] == "ideas":
        cmd_ideas(int(a[1]) if len(a) > 1 else 10)
    elif a[0] == "research":
        cmd_research(int(a[1]) if len(a) > 1 else 3)
    elif a[0] == "make":
        cmd_make(" ".join(a[1:]) or None)
    elif a[0] == "redo":
        cmd_redo(a[1])
    elif a[0] == "doc":
        cmd_doc(" ".join(a[1:]) or None)
    elif a[0] == "batch":
        for _ in range(int(a[1])):
            cmd_make()
    elif a[0] == "thumbs":
        cmd_thumbs(a[1], " ".join(a[2:]) or None)
    elif a[0] == "seo":
        import seo

        seo.make(config.OUT / a[1])
    elif a[0] == "branding":
        import branding

        out = branding.write_kit(config.ROOT / "branding", a[1], a[2] if len(a) > 2 else "Calm stories for quiet nights")
        print("\n".join(f"{k}: {v}" for k, v in out.items()))
    elif a[0] == "channels":
        import channelwatch

        d = json.loads(channelwatch.run().read_text())
        print(d.get("note") or f"{len(d['channels'])} channels studied, {len(d['ideas'])} topic ideas to review")
    elif a[0] == "agent":
        import agent

        r = agent.run(force="force" in a[1:])
        print(f"skipped: {r['skipped']}" if "skipped" in r else
              f"mode {r['mode']}: {r['studied']} channels studied, {r['new_channels']} new competitors, {r['strategies_added']} new ideas, "
              f"{r['applied']} applied, {len(r['errors'])} problems")
        for e in r.get("errors", []):
            print(" -", e)
    elif a[0] == "trends":
        import trendwatch

        d = json.loads(trendwatch.run().read_text())
        print(d.get("error") or f"{len(d['videos'])} videos read, median views {d['summary']['median_views']}, {len(d['ideas'])} topic ideas to review")
    elif a[0] == "subtitles":
        folder = config.OUT / a[1]
        if "--burn" in a:
            subtitles.burn_into_video(folder)
            print("subtitles burned in; captions.srt written")
        else:
            subtitles.write_files(folder, subtitles.ensure_words(folder))
            print("captions.srt written")
    elif a[0] == "newswatch":
        import newswatch

        path = newswatch.run()
        d = json.loads(path.read_text())
        print(f"{path.name}: {d['found']} relevant items, {len(d['items'])} summarized, {len(d['video_ideas'])} video ideas")
        for i in d["items"]:
            print(f"- {i['title']}\n    {i['what_changed']}")
    elif a[0] == "newsvideo":
        import newswatch

        print(newswatch.make_next_news_video(" ".join(a[1:]) or None))
    elif a[0] == "review":
        import reviewer

        r = reviewer.review(config.OUT / a[1])
        print(r["verdict"])
        for c in r["checks"]:
            print(("ok   " if c["ok"] else "FAIL ") + f"{c['severity']:5} {c['name']}: {c['detail']}")
    elif a[0] == "autopilot":
        import autopilot

        print(json.dumps(autopilot.tick() if a[1:] == ["tick"] else autopilot.status(), indent=2))
    elif a[0] == "approve":
        cmd_approve(a[1])
    elif a[0] == "upload":
        cmd_upload(a[1], a[2:])
    elif a[0] == "list":
        cmd_list()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
