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
  python run.py policywatch      daily: has YouTube changed its rule pages?
  python run.py titletest        daily: weak title? suggest (or change) one, then check it was better
  python run.py report           daily: one plain-English summary in the activity feed (made, uploaded, coming, cost, problems)
  python run.py state            print the server-only settings (secrets hidden) as Markdown
  python run.py backup           nightly: copy the records and settings (no secrets, no videos) to backups/, seven kept
  python run.py recheck          hourly: review one uploaded video again; repair its metadata, or take a failing scheduled one back to private
  python run.py remake <name> [--topic "..."]  set a video aside (never deleted) and make it again from the topic, first
  python run.py youtube-login [production|testing]  show the YouTube login's age and mode, or set the mode
  python run.py health           are published videos public and free of claims? (pauses Autopilot if not)
  python run.py safety [--fix]   check that secret files and the login are protected
  python run.py newsvideo        make the next queued YouTube-news video
  python run.py subtitles NAME [--burn]   subtitles for a finished video (.srt, and burned in with --burn)
  python run.py trends           weekly niche trend research (YouTube API) + original topic ideas
  python run.py trend-import FILE.json   keep trending videos a person read in Studio's Trends tab (ranking signal for 14 days)
  python run.py channels         study your reference channels (top videos, themes) + proposals
  python run.py branding "NAME" "TAGLINE"   profile picture, banner and description in branding/
  python run.py approve NAME     mark a reviewed video as ready to upload
  python run.py upload NAME [--public] [--at 2026-10-20T14:00:00Z]
  python run.py list             show videos and their status
"""
import json
import os
import re
import shutil
import sys
from pathlib import Path

import archive_video
import config
import records
import editprofile
import footage
import llm
import subtitles
import packaging
import render
import scriptgen
import topicqueue
import tts

STALE = {"approved", "approved_by", "review", "publish_at", "autopilot_fails", "prelaunch", "visual_check",
         "video_id", "uploaded_at", "upload_started", "upload_check", "thumbnail_uploaded", "recheck", "healed", "playlists", "health", "title_test"}


def reset_for_rerender(data: dict) -> dict:
    """A re-rendered video is a new video: drop approval, review and schedule from the old render."""
    out = {k: v for k, v in data.items() if k not in STALE}
    if data.get("video_id"):
        out["replaces_video"] = data["video_id"]  # the old upload stays on YouTube until the owner approves deleting it
    return out


def unique_folder(base: Path) -> Path:
    """Never write into a folder that already holds a video (it could be one that was uploaded)."""
    if not base.exists():
        return base
    n = 2
    while (base.parent / f"{base.name}-{n}").exists():
        n += 1
    return base.parent / f"{base.name}-{n}"


def cmd_ideas(n: int = 10) -> None:
    new = topicqueue.extend(scriptgen.ideas(n))
    print("\n".join(f"+ {t}" for t in new) or "no new ideas")


def cmd_research(n: int = 3) -> None:
    import research

    new = topicqueue.extend(research.run(n))
    print("\n".join(f"+ {t}" for t in new) or "nothing new")


def _script_gate(data: dict, source: str, topic: str) -> dict:
    """The script reviewer's free check before a voice and pictures are paid for. Safe fixes are applied to `data`; a script still held raises, and the loop asks
    the writer again. Returns `data` (a loop that ends with no good script must not keep the held one: the caller sets data to None on a raise)."""
    import scriptreview

    try:
        scriptreview.gate(data, source, slug=re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:50])
    except ValueError:
        data.clear()  # the same dict object the caller holds: an empty script is never produced
        raise
    return data


def _best_topic(fmt: str) -> str | None:
    """The queued topic the research and growth data like best that can be made well; the first in the queue if that ranking cannot run."""
    import topicrank

    pinned = topicqueue.pop_pinned(fmt)  # a video set aside to be made again comes first
    if pinned:
        return pinned
    try:
        return topicrank.pop_best(fmt)
    except Exception as e:
        print(f"  topic ranking unavailable ({type(e).__name__}); taking the first topic that is not already made")
        import duplicates

        for _ in range(30):
            topic = topicqueue.pop_first()
            if topic is None or not duplicates.topic_conflict(topic, fmt):
                return topic
            print(f"  skipped '{topic[:60]}': the same story is already made")
        return None


def _charged(make, topic):
    """Run a make function, charging its spend to the new video: its folder does not exist while the script is written, so the cost is kept under a
    temporary name and moved to the folder's name when it is known."""
    import tenantmode

    if tenantmode.is_tenant() and tenantmode.quota_state()["state"] == "full":
        raise SystemExit("storage is full: delete videos you no longer need, then try again")
    key = f"pending:{os.getpid()}"
    with llm.cost_scope(key):
        folder = make(topic)
    llm.merge_cost(key, folder.name)
    return folder


def cmd_make(topic: str | None = None) -> Path:
    return _charged(_cmd_make, topic)


def _cmd_make(topic: str | None = None) -> Path:
    if not topic:
        topic = _best_topic("short")
        if not topic:
            cmd_ideas(10)
            topic = _best_topic("short")
        if not topic:
            raise SystemExit("no topics: could not make any ideas")
    print(f"Topic: {topic}")
    data = None
    import wikipedia

    src = wikipedia.facts_for(topic, chars=3500)
    for attempt in range(3):
        try:
            data = scriptgen.script(topic, grounded=src[1] if src else None)
            data = _script_gate(data, src[1] if src else "", topic)
            if src:
                data["sources"] = [f"Wikipedia: {src[0]} (CC BY-SA 4.0), retold in our own words"]
            data["anchors"] = anchor_terms(topic, data.get("anchors", []), src[0] if src else "")
            break
        except Exception as e:  # bad JSON or too short: ask again
            print(f"  script attempt {attempt + 1} failed: {e}")
    if not data:
        raise SystemExit("could not generate a script")
    return _produce_short(data, topic)


def _produce_short(data: dict, topic: str, requeue: bool = True, pool_size: int = 6, min_unique: int = 4, folder: Path | None = None) -> Path:
    """Voice, footage, render and metadata for a finished Short script. requeue: put the topic back in the queue if footage is missing.
    folder: re-render inside this existing folder (it is never removed if the footage is missing)."""
    data = _apply_house_style(data, "short", folder)
    slug = re.sub(r"[^a-z0-9]+", "-", data["title"].lower()).strip("-")[:50]
    in_place = folder is not None
    folder = folder or unique_folder(config.OUT / slug)
    work = folder / "work"
    folder.mkdir(parents=True, exist_ok=True)
    if scriptgen.thin_script(data["lines"]):  # refuse before a voice and pictures are paid for
        if requeue:
            topicqueue.requeue_failed(topic)
        if not in_place:
            shutil.rmtree(folder, ignore_errors=True)
        raise SystemExit("the Short's script admits its sources say little; not made")
    print("Voice + captions...")
    prof = editprofile.load()
    narration, ass, durations = tts.narrate([l["text"] for l in data["lines"]], work, editprofile.short_pause(prof), prof["motion"], prof["caption_pos"])
    print("Footage...")
    if config.PEXELS_KEY:
        clips = [footage.clip_for(l["visual"]) for l in data["lines"]]
        credits = footage.collect_credits(clips)
    else:  # archive pictures: only ones that name the subject
        import aiart

        art = lambda l: aiart.generate(l["text"], l.get("visual", ""), topic, vertical=True, style=data.get("art_style"))
        clips, credits, stats = footage.scene_images(data["lines"], topic, data.get("anchors") or [], pool_size=pool_size, judge=_image_judge(topic),
                                                     art=art, art_limit=12 if data.get("art_style") == "3d" else aiart.MAX_PER_VIDEO["short"],
                                                     art_first=bool(data.get("art_first")), force_art=_forced_art(data))
        data["footage"] = stats
        if stats["missing"] or stats["unique"] < min_unique:
            clips = [None] * len(clips)
    if not footage.enough_footage(clips):
        if requeue:
            kept = topicqueue.requeue_failed(topic)  # to the back of the queue, so the next run tries another topic; dropped after two failures
        if not in_place:
            shutil.rmtree(folder, ignore_errors=True)
        raise SystemExit("not enough footage found for this Short" + (("; topic moved to the back of the queue" if kept else "; topic dropped after two failed tries") if requeue else ""))
    clips, credits, anim = _animate(data, clips, credits, vertical=True)  # a 3D Short can have a few moving clips
    if anim:
        data["animation"] = anim
        print(f"  animation: {anim['animated']} new clip(s), {anim['cached']} from the cache, {anim['failed']} failed, ${anim['spent']:.2f} spent")
    print("Rendering...")
    render.render(clips, durations, narration, ass, work, folder / "video.mp4", loudness=prof["target_lufs"], shots=prof["motion"] >= 1,
                  crossfade=0.3 if prof["motion"] >= 2 and len(clips) <= 20 else 0.0, grain=prof["motion"] >= 2)
    shutil.copy(work / "words.json", folder / "words.json")
    subtitles.write_files(folder, subtitles.with_punctuation(subtitles.load_words(work / "words.json"), [l["text"] for l in data["lines"]]))
    shutil.rmtree(work)
    data["subtitles"] = "burned"
    data["credits"] = credits
    data["approved"] = False
    records.save(folder, data)  # the producer owns the record until it is finished: one atomic whole save
    print(f"\nDone: {folder / 'video.mp4'}\nTitle: {data['title']}\nWatch it, then: python run.py approve {folder.name}")
    return folder


def _second_sources(topic: str, arts: list[dict]) -> tuple[bool, dict | None]:
    """(attempted, what was found): two pages beyond Wikipedia and one original element, only when the owner switched `second_sources` on and the credit covers
    it (secondsources.py). Any failure means "not attempted": a video is never stopped for this."""
    try:
        import autopilot
        import risk
        import secondsources

        credit = risk.credit_left(llm.api_key()) if llm.api_key() else None
        if not secondsources.enabled(autopilot.load_config(), credit):
            return False, None
        extra = secondsources.gather(topic, [a["title"] for a in arts])
        print(f"  second sources: {len(extra['items']) if extra else 0} verified beyond Wikipedia" + (f", original element: {extra['element']['kind']}" if extra and extra.get("element") else ""))
        if not extra and secondsources.LAST_PROBLEM:
            print(f"  second sources: none found because {secondsources.LAST_PROBLEM}")
        return True, extra
    except Exception as e:
        print(f"  second sources skipped: {type(e).__name__}")
        return False, None


def cmd_doc(topic: str | None = None, photo: bool = False) -> Path:
    return _charged(lambda t: _cmd_doc(t, photo), topic)


MIN_VARIETY = 0.55  # share of a documentary's scenes that must show a different picture (Pied Piper showed 28%, Delphi 100%)
PENDING_DOC = config.ROOT / "data" / "pending_doc.json"  # a paid script whose video is not finished: the next pass renders it instead of paying for a new one
MAX_RESUMES = 3


def _pending_doc() -> dict | None:
    try:
        saved = json.loads(PENDING_DOC.read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(saved.get("data"), dict) or saved.get("tries", 0) >= MAX_RESUMES:
        return None
    return saved


def _cmd_doc(topic: str | None = None, photo: bool = False) -> Path:
    import random

    saved = _pending_doc() if not topic else None
    if saved:
        saved["tries"] = saved.get("tries", 0) + 1
        PENDING_DOC.write_text(json.dumps(saved))
        old = config.OUT / saved["folder"] if saved.get("folder") else None
        print(f"Resuming the saved script (try {saved['tries']}): {saved['data']['title']}")
        return _produce_doc(saved["data"], old if old and old.is_dir() and not (old / "meta.json").exists() else None)
    if not topic:
        topic = _best_topic("doc")
        if not topic:
            cmd_research(3)
            topic = _best_topic("doc")
        if not topic:
            raise SystemExit("no topics: could not make any ideas")
    print(f"Documentary: {topic}")
    data = None
    import wikipedia

    arts = wikipedia.facts_multi(topic, n=3, chars_each=7000)  # the best articles: a script drawn from more than one source has fewer unsupported details
    if arts and not wikipedia.is_media_work(arts[0]["text"]):  # a folklore or history topic is not retold from a film's plot: keep the main article, drop adaptations
        arts = [arts[0]] + [a for a in arts[1:] if not wikipedia.is_media_work(a["text"])]
    arts = arts[:2]
    src = (arts[0]["title"], "\n\n".join(f"[{a['title']}]\n{a['text']}" for a in arts)) if arts else None
    print(f"  source articles: {', '.join(a['title'] for a in arts) or 'none found (script will be flagged for a human check)'}")
    attempted, extra = _second_sources(topic, arts) if src else (False, None)
    gtext = (src[1] + ("\n\n" + extra["text"] if extra else "")) if src else None  # the article text, plus the verified passages when second sources are on
    for attempt in range(4):
        try:
            data = scriptgen.doc_script(topic, grounded=gtext)
            if scriptgen.thin_script(data["lines"]):
                raise ValueError("the script admits its sources say little")
            pairs = packaging.script_repeats([l["text"] for l in data["lines"]])  # a chapter that retells the opening: drop the retelling
            if pairs:
                data["lines"], data["chapters"] = scriptgen.remove_lines(data["lines"], data["chapters"], {j for _, j in pairs})
                print(f"  removed {len(pairs)} retold line(s)")
            data = _script_gate(data, gtext or "", topic)
            if src:
                data["sources"] = [f"Wikipedia: {a['title']} (CC BY-SA 4.0), retold in our own words" for a in arts] + [a["url"] for a in arts]
            if attempted:
                data["sources_extra"] = (extra or {}).get("items", [])
                data["sources"] = [*data.get("sources", []), *[i["url"] for i in data["sources_extra"]]]  # addresses only: a page's own title is never written into the public description
                if extra and extra.get("element"):
                    data["original_element"] = extra["element"]
            data["anchors"] = anchor_terms(topic, data.get("anchors", []), src[0] if src else "")
            break
        except Exception as e:
            print(f"  script attempt {attempt + 1} failed: {e}")
    if not data:
        raise SystemExit("could not generate a documentary script")
    if photo:  # realistic invented people (owner's request): the video is held and unapproved, nothing about it goes out until the owner says so
        data.update(art_style="photo", art_first=True, hold=True)
    PENDING_DOC.parent.mkdir(parents=True, exist_ok=True)
    PENDING_DOC.write_text(json.dumps({"data": data, "folder": "", "tries": 0}))
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
    def ask(titles: list[str]) -> list[str]:
        out = scriptgen._chat(
            f"A documentary about: {topic}. Below are archive image file names. Return the numbers of the ones that "
            "plausibly show that subject (its place, people, artwork, objects or maps). Reject anything about a "
            "different subject that merely shares a word (a space mission, an aircraft, a castle elsewhere, a flag). Also reject file names that describe a "
            "modern snapshot of ordinary people or soldiers, a brand, shop or advertisement, a street party, a Halloween or costume scene, or a medical or "
            "military operation, unless the documentary is about exactly that. Each line is a file name, then | and its Commons categories: reject a bare name whose categories show a "
            "ride, vehicle, aircraft, building or brand that only shares the word.\n"
            + "\n".join(f"{i}: {t}" for i, t in enumerate(titles)) + '\n\nReturn JSON: {"keep": [numbers]}'
        )
        keep = {int(n) for n in out.get("keep", []) if str(n).isdigit()}
        return [t for i, t in enumerate(titles) if i in keep]
    return footage.cached_judge(topic, ask)


def _produce_doc(data: dict, folder: Path | None = None) -> Path:
    import random

    data = _apply_house_style(data, "doc", folder)

    slug = "doc-" + re.sub(r"[^a-z0-9]+", "-", data["title"].lower()).strip("-")[:45]
    in_place = folder is not None  # a re-render inside an existing video's folder: that folder is never removed (28 Oct 2026: a re-render at the picture budget removed a whole video)
    folder = folder or unique_folder(config.OUT / slug)
    work = folder / "work"
    folder.mkdir(parents=True, exist_ok=True)
    if PENDING_DOC.exists():
        try:
            saved = json.loads(PENDING_DOC.read_text())
            if saved.get("data", {}).get("title") == data.get("title"):
                saved["folder"] = folder.name
                PENDING_DOC.write_text(json.dumps(saved))
        except (OSError, ValueError):
            pass
    print("Voice...")
    prof = editprofile.load()
    narration, _ass, durations = tts.narrate([l["text"] for l in data["lines"]], work, prof["sentence_pause_ms"] / 1000)
    print("Archival images (only pictures that name the subject)...")
    anchors = data.get("anchors") or []
    import aiart

    art = lambda l: aiart.generate(l["text"], l.get("visual", ""), data["topic"], style=data.get("art_style"))  # style "3d": a 3D animated-film look
    pics = dict(judge=_image_judge(data["topic"]), art=art, art_first=bool(data.get("art_first")), force_art=_forced_art(data))
    clips, credits, stats = footage.scene_images(data["lines"], data["topic"], anchors, art_limit=aiart.MAX_PER_VIDEO["doc"], **pics)
    if stats["unique"] < MIN_VARIETY * stats["scenes"] and aiart.enabled():  # the same few pictures again and again: draw illustrations for the scenes that would repeat
        print(f"  only {stats['unique']} different pictures for {stats['scenes']} scenes: drawing more")
        clips, credits, stats = footage.scene_images(data["lines"], data["topic"], anchors, art_limit=aiart.MAX_PER_VIDEO["doc"] + aiart.EXTRA_FOR_VARIETY, **pics)
    if stats["missing"] or stats["unique"] < 6:
        shutil.rmtree(work if in_place else folder, ignore_errors=True)
        raise SystemExit(f"only {stats['unique']} on-topic images found ({stats['missing']} scenes without one); "
                         "not rendering a video of unrelated pictures")
    clips, credits, anim = _animate(data, clips, credits)  # some drawn scenes become short moving clips when the video asks for it
    if anim:
        data["animation"] = anim
        print(f"  animation: {anim['animated']} new clip(s), {anim['cached']} from the cache, {anim['failed']} failed, ${anim['spent']:.2f} spent")
    music = sorted(Path("music").glob("*.mp3")) if Path("music").exists() else []
    print(f"Rendering ({sum(c is not None for c in clips)}/{len(clips)} scenes have footage)...")
    words = subtitles.with_punctuation(subtitles.load_words(work / "words.json"), [l["text"] for l in data["lines"]])
    doc_ass = None
    if config.DOC_SUBTITLES:
        doc_ass = work / "doc_captions.ass"
        doc_ass.write_text(subtitles.to_ass(subtitles.build_cues(words), (1920, 1080), prof["caption_pos"]))
    render.render(clips, durations, narration, doc_ass, work, folder / "video.mp4",
                  size=(1920, 1080), music=random.choice(music) if music else None, loudness=prof["target_lufs"], shots=prof["motion"] >= 1)
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
    records.save(folder, data)
    PENDING_DOC.unlink(missing_ok=True)
    print(f"\nDone: {folder / 'video.mp4'}\nTitle: {data['title']}\nWatch it, then: python run.py approve {folder.name}")
    return folder



def _refuse_if_uploaded(name: str) -> None:
    """A re-render in the same folder would leave the old upload scheduled on YouTube while a new one is made: an uploaded video is never redone in place."""
    if json.loads((config.OUT / name / "meta.json").read_text()).get("video_id"):
        raise SystemExit(f"{name} is on YouTube: its upload would stay scheduled. Make a new video of the topic and hold or delete the old one in YouTube Studio.")


def cmd_redo_short(name: str) -> None:
    """Re-render an existing Short in its own folder from its saved script (new voice, pictures and video)."""
    _refuse_if_uploaded(name)
    data = reset_for_rerender(json.loads((config.OUT / name / "meta.json").read_text()))
    _produce_short(data, data["topic"], requeue=False, folder=config.OUT / name)


def _house_style(kind: str) -> dict:
    """What Autopilot adds to a NEW video of this kind (autopilot.json house_style): the 3D animated-film look and a few moving clips. Only when it is switched on and
    the account can pay for it (credit known and at least min_credit: an animated documentary costs about $3, a stopped render wastes it). {} otherwise."""
    import autopilot
    import llm
    import risk

    hs = autopilot.load_config().get("house_style") or {}
    part = hs.get(kind) or {}
    if not hs.get("enabled") or not part:
        return {}
    try:
        credit = risk.credit_left(llm.api_key()) if llm.api_key() else None
    except Exception:
        credit = None
    if credit is None or credit < float(hs.get("min_credit", 8.0)):
        return {}
    return {"art_style": "3d", "animate": int(part.get("clips", 0)), "animate_budget": float(part.get("budget", 1.0)), "art_first": True, "house_style": True}


def _apply_house_style(data: dict, kind: str, folder) -> dict:
    """Only a new video gets it: a folder means a re-render in place (redo, repair), and a video that chose its own look (a remake) keeps it."""
    if folder is None and "art_style" not in data:
        data.update(_house_style(kind))
    return data


def _forced_art(data: dict) -> set[str]:
    """Narration lines that are always drawn, whatever a picture search finds: the lines flagged for a redraw, and for a 3D video also the first four (the hook is the
    drawn, animated scene, never a museum photo: the first remake showed photos for the first 75 seconds)."""
    forced = set(data.get("redraw_lines") or [])
    if data.get("art_style") == "photo":  # every scene is drawn: no reused picture, no chart or faded sketch from the archive (the first two realistic videos showed both)
        forced |= {l["text"] for l in data["lines"]}
    if data.get("art_style") == "3d":
        forced |= {l["text"] for l in data["lines"][:4]}
    return forced


def _animate(data: dict, clips: list, credits: list, vertical: bool = False) -> tuple[list, list, dict | None]:
    """Animate some drawn scenes when the video asks for it (data["animate"] = how many clips, data["animate_budget"] = dollars, default 3). Returns
    (clips, credits with the AI-video credit added, stats) or the inputs and None when not asked."""
    n = int(data.get("animate") or 0)
    if n <= 0:
        return clips, credits, None
    import animate
    import modelcfg

    new, stats = animate.animate_scenes(clips, data["lines"], n, float(data.get("animate_budget", 3.0)), animate.clip_generator(vertical=vertical),
                                        size=(720, 1280) if vertical else (1280, 720))
    if stats["animated"] or stats["cached"]:
        credits = [*credits, animate.credit(modelcfg.get("video_generation"))]
    return new, credits, stats


def cmd_remake(name: str, args: list[str]) -> None:
    """A NEW video of the same story from a saved documentary script, in its own folder (an uploaded video is never redone in place; its upload stays for the owner to
    delete). --style 3d draws the scenes in a 3D animated-film look; --animate N turns N drawn scenes into moving clips (about $0.24 each). The new video is held
    and not approved: nothing about it can go out until the owner says so."""
    src = json.loads((config.OUT / name / "meta.json").read_text())
    if src.get("format") != "doc":
        raise SystemExit(f"{name} is not a documentary: remake works on documentaries")
    style = args[args.index("--style") + 1] if "--style" in args else "3d"
    if style != "3d":
        raise SystemExit(f"unknown style {style!r}: the only style is 3d")
    data = reset_for_rerender(src)
    data.update(art_style=style, animate=int(args[args.index("--animate") + 1]) if "--animate" in args else 0, hold=True, remake_of=name,
                art_first=True)  # draw where no specific picture exists instead of reusing the generic reserve (which repeated the same museum photos)
    _produce_doc(data)


def cmd_redo(name: str) -> None:
    """Re-render an existing documentary from its saved script (keeps the text, redoes voice, images, video)."""
    _refuse_if_uploaded(name)
    data = reset_for_rerender(json.loads((config.OUT / name / "meta.json").read_text()))
    _produce_doc(data, config.OUT / name)


def cmd_thumbs(name: str, hook: str | None = None) -> None:
    import thumbnail

    folder = config.OUT / name
    if hook:
        records.merge(folder, {"thumb_hook": hook})
    thumbnail.make(folder, hook)


def cmd_approve(name: str) -> None:
    records.merge(config.OUT / name, {"approved": True})
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
    if a:
        import agents
        import playbook

        playbook.set_agent(agents.for_command(a[0]))  # model calls of this command carry its agent's role and limits
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
        cmd_doc(" ".join(w for w in a[1:] if w != "--photo") or None, photo="--photo" in a)
    elif a[0] == "remake-short":
        import clipper

        n = int(a[a.index("--animate") + 1]) if "--animate" in a else 2
        folder = clipper.make_from(a[1], {"art_style": "3d", "animate": n, "animate_budget": 1.0, "art_first": True, "hold": True})
        if folder is None:
            raise SystemExit(f"no Short could be cut from {a[1]}: no usable chapter left, or the pictures could not be made")
        print(f"3D Short ready (held, not approved): {folder}")
    elif a[0] == "remake":
        cmd_remake(a[1], a[2:])
    elif a[0] == "batch":
        for _ in range(int(a[1])):
            cmd_make()
    elif a[0] == "thumbs":
        cmd_thumbs(a[1], " ".join(a[2:]) or None)
    elif a[0] == "seo":
        import seo

        seo.make(config.OUT / a[1])
    elif a[0] == "guardian":
        import guardian

        res = guardian.run()
        print(res.get("skipped") and f"guardian skipped: {res['skipped']}" or f"guardian: {res['watching']} videos with findings, {len(res['actions'])} actions, {res['rule_changes']} rule page changes")
    elif a[0] == "unstick":
        import unstick

        res = unstick.run()
        print(json.dumps({k: v for k, v in res.items() if k != "tried"}, default=str) if res.get("skipped") else f"unstick: {res['slug']} solved={res['solved']} fix={res['fix']} owner={res['owner']}")
    elif a[0] == "agent-review":
        import agenteval
        import agentlog
        import lessons
        import tracetriage

        ev, tr, dropped = agenteval.run(), tracetriage.triage(), lessons.prune()
        new = [f for f in tr["families"] if f["state"] != "known"]
        print(f"agent evaluation: {ev['passed']} passed, {ev['failed']} failed; triage: {len(tr['families'])} families ({len(new)} not solved before), {tr['stuck_drafts']} stuck drafts; lessons pruned: {dropped}")
        if ev["failed"]:
            agentlog.event("error", "Agent evaluation failed", "; ".join(f"{c['case']}: {c['detail'][:80]}" for c in ev["cases"] if not c["ok"]), notify=True)
    elif a[0] == "analyze-video":
        import videoinspect

        res = videoinspect.gemini_analyze(config.OUT / a[1])
        if "error" in res:
            raise SystemExit(f"analysis not done: {res['error']}")
        print(f"analysis of {a[1]} by {res['model']}: {res['summary']}")
        for p in res["problems"]:
            print(f"  {p['at_s'] // 60}:{p['at_s'] % 60:02d} [{p['severity']}] {p['what']}")
        if res.get("ignored_impossible_times"):
            print(f"({res['ignored_impossible_times']} finding(s) ignored: their time is after the end of the video, so treat this report as leads to check, not facts)")
        print(f"{len(res['problems'])} problem(s). {res['coverage']}" + (f" Cost ${res['cost']:.3f}." if isinstance(res.get('cost'), (int, float)) else ""))
    elif a[0] == "score-thumbnails":
        import thumbscore

        meta = json.loads((config.OUT / a[1] / "meta.json").read_text())
        names = [n for n in meta.get("thumbnails", []) if (config.OUT / a[1] / n).is_file()]
        got = thumbscore.score([config.OUT / a[1] / n for n in names], meta.get("title", ""), meta.get("thumb_hook", ""))
        if not got:
            raise SystemExit("no score: no model could read the thumbnails, or the daily cap is used up")
        for g in sorted(got, key=lambda g: -g["total"]):
            print(f"  {g['total']:>4}  {names[g['index']]}  " + " ".join(f"{k}={v:g}" for k, v in g["parts"].items()))
        print(f"best: {names[max(got, key=lambda g: g['total'])['index']]} (the record was not changed)")
    elif a[0] == "trainset":
        import trainset

        rep = trainset.build(allow=tuple(x for x in a[1:] if "/" in x))  # model names the owner allows, e.g. a Llama or Qwen id; Claude output is excluded otherwise
        print(json.dumps({k: rep[k] for k in ("videos_seen", "examples_kept", "train", "valid", "rejected", "rejected_reasons", "ready_to_train", "needed", "dir")}, indent=1))
        for slug, why in list(rep["videos_skipped"].items())[:8]:
            print(f"  left out {slug}: {why}")
        print("Nothing was pushed or trained. Files are in the folder above.")
    elif a[0] == "script-review":
        import reviewer
        import scriptreview

        folder = config.OUT / a[1]
        meta = json.loads((folder / "meta.json").read_text())
        res = scriptreview.review(meta, reviewer.source_text(meta), use_llm="--llm" in a, may_spend=scriptreview.can_spend())
        scriptreview.record(a[1], res)
        for c in res["checks"]:
            print(f"  {'ok  ' if c['ok'] else c['severity'].upper():5} {c['name']}: {c['detail']}")
        print(f"script review of {a[1]}: {res['verdict']} (model read: {res['model']}); lines to look at: {res['bad_lines'][:20] or 'none'}")
    elif a[0] == "doctor":
        import doctor

        res = doctor.run()
        bad = [f"{r['agent']} {r['status']}" for r in res["agents"] if r["status"] in ("stale", "failing")]
        print(f"doctor: {len(res['agents'])} agents checked, unhealthy: {', '.join(bad) or 'none'}; fixed: {len(res['solved'])}; for the owner: {len(res['owner'])}; "
              f"setup items missing: {', '.join(res['needs']) or 'none'}; skill drafts: {len(res['drafts'])}")
    elif a[0] == "agents":
        import agenteval
        import agentbus
        import playbook

        try:
            ev = json.loads(agenteval.RESULT.read_text())
            print(f"last evaluation {ev['at']}: {ev['passed']} passed, {ev['failed']} failed")
        except (OSError, ValueError):
            print("no evaluation has run yet (python run.py agent-review)")
        print("playbooks: " + ", ".join(playbook.agents()))
        import doctor

        try:
            d = json.loads(doctor.REPORT.read_text())
            print(f"doctor {d['at']}: " + (", ".join(f"{x['agent']} {x['status']}" for x in d["agents"] if x["status"] in ("stale", "failing")) or "all agents with a job are healthy") + f"; setup missing: {', '.join(d['needs']) or 'none'}")
        except (OSError, ValueError, KeyError):
            print("the doctor has not run yet (python run.py doctor)")
        print("inbox: " + json.dumps(agentbus.summary()))
    elif a[0] == "seo-fix":
        import seo

        try:
            print("changed: " + (", ".join(seo.repair(config.OUT / a[1])) or "nothing"))
        except RuntimeError as e:
            print(f"seo-fix stopped: {e}")
    elif a[0] == "branding":
        import branding

        out = branding.write_kit(config.ROOT / "branding", a[1], a[2] if len(a) > 2 else "Calm stories for quiet nights")
        print("\n".join(f"{k}: {v}" for k, v in out.items()))
    elif a[0] == "channels":
        import channelwatch

        d = json.loads(channelwatch.run().read_text())
        print(d.get("note") or f"{len(d['channels'])} channels studied, {len(d['ideas'])} topic ideas to review")
    elif a[0] == "inspect":
        import videoinspect

        raise SystemExit(videoinspect.main(a[1:]))
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
    elif a[0] == "trend-import":  # trends read from the owner's own Studio Trends tab by a person: a JSON file of rows (title, channel, views, age_days, seconds, url)
        import trendinbox

        done, problems = trendinbox.import_items(json.loads(Path(a[1]).read_text()), source="studio_trends")
        print(f"{len(done)} trending videos kept for ranking, {len(problems)} skipped")
        for p in problems:
            print(" -", p)
    elif a[0] == "subtitles":
        folder = config.OUT / a[1]
        if "--burn" in a:
            subtitles.burn_into_video(folder)
            print("subtitles burned in; captions.srt written")
        else:
            subtitles.write_files(folder, subtitles.with_punctuation(subtitles.ensure_words(folder), [l["text"] for l in json.loads((folder / "meta.json").read_text())["lines"]]))
            print("captions.srt written")
    elif a[0] == "newswatch":
        import newswatch

        path = newswatch.run()
        d = json.loads(path.read_text())
        print(f"{path.name}: {d['found']} relevant items, {len(d['items'])} summarized, {len(d['video_ideas'])} video ideas")
        for i in d["items"]:
            print(f"- {i['title']}\n    {i['what_changed']}")
    elif a[0] == "policywatch":
        import newswatch

        ch = newswatch.policy_watch()
        print(f"{len(ch)} rule pages changed" if ch else "no rule page changed (first run only saves a copy)")
        for c in ch:
            print(f"- {c['page']}: {(c['added'] or c['removed'])[0]}")
    elif a[0] == "repair" and len(a) > 1:
        import fixer

        print(json.dumps(fixer.repair(a[1], extra="--extra" in a), indent=2, default=str))
    elif a[0] == "growthdata":  # our own per-video numbers from the Analytics and Reporting APIs (read-only)
        import growthdata

        print(json.dumps(growthdata.collect(), indent=2))
    elif a[0] == "diagnose":  # one primary problem per video from our own numbers; owner tasks only, nothing is written to YouTube
        import diagnose

        print(json.dumps(diagnose.run(), indent=2))
        print(diagnose.report())
        import datetime as dt

        import drift
        import newswatch

        d = drift.run(policy_changes=newswatch.recent_policy_changes(dt.datetime.now(dt.timezone.utc), 40))
        print(f"drift: {d['status']} ({d['have_days']} of {d['need_days']} days of history), {len(d['events'])} finding(s)")
    elif a[0] == "learn":  # the weekly report: what worked, what did not, from our own numbers (reads and writes its own files; never touches YouTube)
        import datetime as dt

        import learner

        out = learner.run()
        print(json.dumps(out, indent=2))
        print(learner.latest_summary(dt.datetime.now(dt.timezone.utc), lines=40))
    elif a[0] == "policy":  # YouTube rule-page changes and the hold on scheduling and uploads (the owner releases it)
        import policyclass

        if len(a) > 1 and a[1] == "release":
            print(policyclass.release_hold(" ".join(a[2:])))
        else:
            h = policyclass.hold_active()
            print(f"HOLD ACTIVE since {h['since']} for: {', '.join(h['pages'])}. Read the changes below, then `python run.py policy release`." if h else "no policy hold")
            for r in policyclass.recent(8):
                print(f"{r['at'][:10]} {r['severity']:4} {r['affects']:12} {r['page']}: {r['summary'][:110]}" + (f" | rules proposal {r['proposal']}" if r.get("proposal") else ""))
    elif a[0] == "edits":  # changes to videos on YouTube: proposals for public videos (owner approves) and the log of what was changed
        import actionlog

        sub = a[1] if len(a) > 1 else "list"
        if sub in ("approve", "reject") and len(a) > 2:
            yt = None
            if sub == "approve":
                import trendwatch

                yt = trendwatch._service()
            print(actionlog.resolve(a[2], sub == "approve", yt))
        else:
            for r in actionlog.pending():
                print(f"pending {r['id']} {r['slug']}: {r['source']} wants to change {', '.join(k for k in r['after'] if r['before'].get(k) != r['after'][k])} | {r['why'][:100]}")
            for r in actionlog.actions(10):
                print(f"{r['id']} {r['at']} {r['video_id']} {r['kind']} by {r['source']}{' (rolled back)' if r.get('rolled_back') else ''}: {r['why'][:80]}")
    elif a[0] == "rollback" and len(a) > 1:  # put back what a logged change replaced (owner command)
        import actionlog
        import trendwatch

        print(actionlog.rollback(a[1], trendwatch._service()))
    elif a[0] == "rules":  # the growth rules file: only the owner approves a proposed change
        import rulesfile

        sub = a[1] if len(a) > 1 else "show"
        if sub in ("approve", "reject") and len(a) > 2:
            print(rulesfile.resolve(a[2], approve=sub == "approve"))
        elif sub == "verify":
            print(rulesfile.mark_verified())
        else:
            r = rulesfile.load()
            print(f"rules {r['rules_version']}, last verified {r['last_verified']}" + (f", NOT verified for {rulesfile.stale_days(r)} days" if rulesfile.stale_days(r) else ""))
            for p in r["pending_changes"]:
                print(f"pending {p['id']}: {json.dumps(p['patch'])} | why: {p.get('why', '')} | source: {p.get('source', '')}")
            print("\n".join(f"problem: {x}" for x in r["_problems"]) or "no problems")
    elif a[0] == "tidy-strategies":
        import strategy

        print(strategy.tidy())
    elif a[0] == "audit-queue":
        import topicrank

        for r in topicrank.audit_queue():
            print(f"removed: {r['topic']} -- {r['why']}")
        print(f"{len(topicqueue.items())} topics left in the queue")
    elif a[0] == "remake" and len(a) > 1:
        import fixer

        r = fixer.remake(a[1], a[a.index("--topic") + 1] if "--topic" in a else None)
        print(f"set aside in {r['archived']}; the next {r['format']} will be made from: {r['topic']}")
    elif a[0] == "youtube-login":
        import datetime as dt

        import ytlogin

        now = dt.datetime.now(dt.timezone.utc)
        if len(a) > 1 and a[1] in ("production", "testing"):
            ytlogin.stamp(dt.datetime.strptime(ytlogin.status(now)["consented_at"], ytlogin.TS).replace(tzinfo=dt.timezone.utc) if ytlogin.status(now)["consented_at"] else now, mode=a[1])
        s = ytlogin.status(now)
        print(f"mode: {s['mode']}; {s['detail']}; last check: {s['last_check']}")
    elif a[0] == "health":
        import safety
        import ytlogin

        import datetime as dt

        import risk

        m = risk.money_watch()
        print("Money: " + ("balance not readable" if m["left"] is None else f"${m['left']:.2f} left") + ("; " + "; ".join(m["changed"]) if m["changed"] else ""))
        lg = ytlogin.check(dt.datetime.now(dt.timezone.utc))
        print("YouTube login: " + ("works" if lg["ok"] else f"NOT working ({lg['error']})"))
        r = safety.check()
        print(r.get("error") or f"{r['checked']} published videos checked, {len(r['problems'])} problems" + (", Autopilot paused" if r["paused"] else ""))
        for p in r["problems"]:
            print(" -", p)
    elif a[0] == "tenant-quota":
        import tenantmode

        print(json.dumps(tenantmode.enforce_quota()))
    elif a[0] == "titletest":
        import titletest

        r = titletest.run(quality=titletest.watch_quality())
        print(f"{r['checked']} public videos looked at (mode {titletest.mode()}): {len(r['changed'])} changed, {len(r['weak'])} suggested, "
              f"{len(r['reverted'])} put back or judged worse, {len(r['kept'])} kept, {r['learning']} too early to judge")
    elif a[0] == "report":
        import dailyreport
        import risk

        key = llm.api_key()
        out = dailyreport.run(credit=risk.credit_left(key) if key else None)
        print(out.get("text") if out.get("written") else "today's report was already written")
    elif a[0] == "state":
        import serverstate

        print(serverstate.markdown(serverstate.snapshot()))
    elif a[0] == "backup":
        import backup

        print(json.dumps(backup.run(), indent=2))
    elif a[0] == "recheck":
        import recheck

        print(json.dumps(recheck.run(), indent=2, default=str))
    elif a[0] == "safety":
        import safety

        if "--fix" in a:
            print("made private:", ", ".join(safety.fix_permissions()) or "nothing to change")
        for c in safety.local_audit():
            print(("ok   " if c["ok"] else "FAIL ") + f"{c['name']}: {c['detail']}")
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


def guarded_main(entry=None, argv: list[str] | None = None) -> int:
    """Run a command. A crash inside it (a full disk, a broken record, YouTube refusing) ends with one plain line, one entry in the activity feed and a non-zero
    exit code, which the worker log and the doctor read as a failed run. SystemExit (the commands' own refusals) and Ctrl+C pass through untouched."""
    entry = entry or main
    cmd = (sys.argv[1:] if argv is None else argv)[:1]
    try:
        entry()
        return 0
    except (SystemExit, KeyboardInterrupt):
        raise
    except Exception as e:
        print(f"run.py {' '.join(cmd)} failed: {type(e).__name__}: {str(e)[:200]}")
        try:
            import agentlog

            agentlog.event("error", f"A command failed: run.py {' '.join(cmd)}", f"{type(e).__name__}: {str(e)[:200]}")
        except Exception:
            pass  # the feed is a courtesy here: the message above and the exit code already say it
        return 1


if __name__ == "__main__":
    sys.exit(guarded_main())
