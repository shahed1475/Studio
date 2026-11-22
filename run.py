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
  python run.py autopilot make short|doc [--no-review]   one supervised make (+ review) by Autopilot's own steps: never approves, schedules or uploads
  python run.py newswatch        weekly YouTube security/policy news digest
  python run.py policywatch      daily: has YouTube changed its rule pages?
  python run.py titletest        daily: weak title? suggest (or change) one, then check it was better
  python run.py report           daily: one plain-English summary in the activity feed (made, uploaded, coming, cost, problems)
  python run.py state            print the server-only settings (secrets hidden) as Markdown
  python run.py backup           nightly: copy the records and settings (no secrets, no videos) to backups/, seven kept
  python run.py recheck          hourly: review one uploaded video again; repair its metadata, or take a failing scheduled one back to private
  python run.py remake <name> [--topic "..."]  set a video aside (never deleted) and make it again from the topic, first
  python run.py demand [topic] [--youtube]   search demand: autocomplete, Wikipedia pageviews, top YouTube results (all queued topics without a topic)
  python run.py comments [--force]   what viewers ask: questions from public comments (ours and the reference channels'), 30 days at most
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

Agents and checks:
  python run.py agents           every agent's health, playbook and last behaviour check
  python run.py agent-review     daily: behaviour checks (agenteval), trace triage, lessons prune
  python run.py doctor           every 6 h: stale or failing agents, safe fixes only, post-mortems
  python run.py guardian         hourly: hold, repair and reissue videos that are not public (never makes one public)
  python run.py unstick          move stuck drafts up the escalation ladder
  python run.py agent [force]    the growth agent's daily research
  python run.py script-review NAME [--llm]   check a script before voice and pictures
  python run.py judges NAME      who would judge this video's AI review now, and why (asks no model)
  python run.py listen NAME [--local]   compare the narration with the script (a warning only)
  python run.py inspect ...      measure and sample a video, save its sources (videoinspect.py)
  python run.py analyze-video NAME   one of OUR videos, shrunk, read by a vision model
  python run.py score-thumbnails NAME   score the thumbnail candidates (reads, changes nothing)
  python run.py recover [--thorough]   read-only: what a power cut left unfinished and the safe next step
Repairs and owner commands:
  python run.py repair NAME [--extra]   repair a broken draft (holds the Autopilot lock)
  python run.py remake-short NAME [--animate N]   make a Short again from its documentary
  python run.py reschedule NAME  owner only: a new future time for an approved video left private with no schedule
  python run.py edits [list|approve ID|reject ID]   changes to videos on YouTube; public ones wait for the owner
  python run.py rollback ID      put back what a logged change replaced
  python run.py rules [show|approve ID|reject ID]   the growth rules file; only the owner approves
  python run.py policy [release] YouTube rule-page changes and the scheduling hold
  python run.py seo-fix NAME     repair a video's search packaging
Growth and research:
  python run.py growthdata       our own numbers from the Analytics and Reporting APIs (read-only)
  python run.py diagnose         one main problem per video, owner tasks only
  python run.py learn            the weekly report from our own numbers
  python run.py audit-queue      rank and check the topic queue
  python run.py tidy-strategies  tidy the growth agent's strategy list
  python run.py channel-sync [--apply]   read the channel and write its real video ids into local records
  python run.py writer-bench     free models write Short scripts, scored by free rules (nothing trained)
  python run.py writer-bench-judge   a few cents: Claude judges one bench model's scripts (a report, never training data)
  python run.py trainset         build and check the private training set (no Claude output)
  python run.py specrun [tick|status|check DIR]   free videos from specs written by Claude
Setup and self-tests:
  python run.py depth-setup      fetch the depth model once (hash-checked) for camera motion
  python run.py sources-test [WORDS]   one live search in every picture and footage library
  python run.py pixabay-test [WORDS]   one live look-up with the saved Pixabay key
  python run.py tenant-quota     enforce user-studio storage limits
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


def freemodels_top(now, n: int) -> list[str]:
    import freemodels

    freemodels.refresh(now)
    return freemodels.choose("script", now, n=n)


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


def _real_footage(data: dict, clips: list, credits: list) -> tuple[list, list]:
    """Real moving footage (footage_real.py) on up to data["real_footage"] scenes when the film asks for it; the stats replace the number, so a redo asks again. Any failure leaves the
    scenes as they were: real footage is a bonus, never a reason to stop a film."""
    n = data.get("real_footage")
    n = n.get("asked") if isinstance(n, dict) else n
    if not isinstance(n, int) or isinstance(n, bool) or n <= 0:
        return clips, credits
    import footage_real
    import parallax

    try:
        flat = parallax.flat_scenes(data["lines"]) if len(data.get("lines", [])) == len(clips) else set()
        out, creds, stats = footage_real.for_film(data, clips, credits, n, flat=flat)
    except Exception as e:
        print(f"  real footage skipped ({type(e).__name__})")
        return clips, credits
    data["real_footage"] = stats
    print(f"  real footage: {stats['used']} clip(s) of {stats['asked']} asked, {stats['found']} fitting file(s) found in {stats['queries']} search(es)")
    return out, creds


def _real_media_on(data: dict) -> bool:
    """Real pictures from the approved free libraries (realmedia.py) before any drawn one, with their credits in the description. On for every video unless it says `real_media: false`, or
    it is drawn on purpose in one look (3d, photo, draw_all) or is a real case (no archive picture of a real victim or suspect)."""
    return data.get("real_media") is not False and data.get("art_style") not in ("photo", "3d") and not data.get("draw_all") and not _is_case(data)


def _real_finder(data: dict, kind: str):
    """The picture finder for this video (None when real media is off). The film may show up to 10 credit-needing items, a Short 4: each one is written into the description."""
    if not _real_media_on(data):
        return None
    import realmedia

    return realmedia.Finder(data["topic"], data.get("anchors") or [], judge=_image_judge(data["topic"]), credit_cap=10 if kind == "doc" else 4)


def _is_case(data: dict) -> bool:
    """A real case or unsolved crime: its pictures show no identifiable person (aiart.CASE_PICTURES) and its script follows scriptgen.CASE_RULES."""
    import kinds

    return (data.get("kind") or kinds.classify(data)) == "case"


def _weekly_kind(fmt: str) -> str | None:
    """The kind of video the weekly programme (weekplan.py) wants next, or None for the plain ranking: a film follows the rotation, the week's sixth Short the winner's kind (shortpick)."""
    import datetime as dt

    import autopilot
    import shortpick
    import weekplan

    cfg = autopilot.load_config()
    if not weekplan.enabled(cfg):
        return None
    metas = []
    for m in config.OUT.glob("*/meta.json"):
        try:
            metas.append({**json.loads(m.read_text()), "slug": m.parent.name})
        except (OSError, ValueError):
            continue
    if fmt == "doc":
        return weekplan.next_long_kind(weekplan.recent_doc_kinds(metas))
    if fmt == "short" and weekplan.winner_due(metas, cfg, dt.datetime.now(dt.timezone.utc)):
        w = shortpick.winner()
        return w["kind"] if w else None
    return None


def _draft_topic(fmt: str) -> str | None:
    """The topic of the saved documentary draft (scriptgen.DRAFT_FILE) while it still has fact-check uses left and its story is not already made, else None."""
    if fmt != "doc":
        return None
    try:
        d = json.loads(scriptgen.DRAFT_FILE.read_text())
    except (OSError, ValueError):
        return None
    if not d.get("topic") or not d.get("lines") or int(d.get("uses", 0)) >= scriptgen.MAX_DRAFT_USES:
        return None
    import duplicates

    return None if duplicates.topic_conflict(d["topic"], "doc") else d["topic"]


def _best_topic(fmt: str) -> str | None:
    """The queued topic the research and growth data like best that can be made well; the first in the queue if that ranking cannot run."""
    import topicrank

    pinned = topicqueue.pop_pinned(fmt)  # a video set aside to be made again comes first
    if pinned:
        return pinned
    waiting = _draft_topic(fmt)  # then a written documentary draft that waits for its fact-check: its topic left the queue when it was picked, so without
    if waiting:                  # this the draft was orphaned by a judge outage and only a hand-made pin brought it back (22 Nov 2026 audit)
        print(f"  a saved draft waits for its fact-check: {waiting}")
        return waiting
    try:
        return topicrank.pop_best(fmt, want_kind=_weekly_kind(fmt))
    except Exception as e:
        print(f"  topic ranking unavailable ({type(e).__name__}); taking the first topic that is not already made")
        import duplicates

        for _ in range(30):
            topic = topicqueue.pop_first()
            if topic is None or not duplicates.topic_conflict(topic, fmt):
                return topic
            print(f"  skipped '{topic[:60]}': the same story is already made")
        return None


SHORT_SOURCE_CHARS = 7000  # a Short is written from the whole article: with 3,500 the writer never saw the newest explanation of the Lost Army (the article is 5,700 characters)


def _make_options(args: list[str]) -> tuple[str | None, dict]:
    """`run.py make TOPIC [--draw-all] [--voice STYLE] [--lufs N] [--hold]`: the topic, and the settings of this one Short. --draw-all draws every scene in the 3D film look
    (the archive search only looked at file names and filled a Short with pictures that did not show its story); --voice an opt-in delivery from tts.VOICE_STYLES;
    --lufs a loudness target of its own inside editprofile.LIMITS; --hold keeps it away from Autopilot until the owner releases it."""
    words, extra, i = [], {}, 0
    while i < len(args):
        a = args[i]
        if a == "--draw-all":
            extra.update(art_style="3d", draw_all=True)
        elif a == "--hold":
            extra["hold"] = True
        elif a in ("--voice", "--lufs"):
            if i + 1 >= len(args):
                raise SystemExit(f"{a} needs a value")
            i += 1
            if a == "--voice":
                if args[i] not in tts.VOICE_STYLES:
                    raise SystemExit(f"unknown voice style {args[i]!r}: choose from {', '.join(tts.VOICE_STYLES)}")
                extra["voice_style"] = args[i]
            else:
                lo, hi = editprofile.LIMITS["target_lufs"]
                try:
                    value = float(args[i])
                except ValueError:
                    raise SystemExit(f"--lufs needs a number, got {args[i]!r}")
                if not lo <= value <= hi:
                    raise SystemExit(f"--lufs must be between {lo:g} and {hi:g}")
                extra["target_lufs"] = value
        else:
            words.append(a)
        i += 1
    return (" ".join(words) or None), extra


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


def cmd_make(topic: str | None = None, extra: dict | None = None) -> Path:
    return _charged(lambda t: _cmd_make(t, extra), topic)


_RUN_WORK: list[Path] = []  # the work folder of the film being made, so a stop is recorded in its checkpoint


def _records_stop(fn):
    """A film's progress is recorded in work/checkpoint.json (checkpoint.py). A run that ends, well or badly, records its end; one that a power cut or a kill stops
    does not, and the next make of the same film sees that it was interrupted, keeps every finished voice line, scene and picture, and does not count the cut
    against the film's three tries (_cmd_doc)."""
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        _RUN_WORK.clear()
        try:
            return fn(*args, **kwargs)
        except BaseException as e:
            if _RUN_WORK:
                import checkpoint

                checkpoint.end_run(_RUN_WORK[-1], f"stopped: {type(e).__name__}: {e}"[:300])
            raise
    return wrapper


PENDING_SHORT = config.ROOT / "data" / "pending_short.json"  # a Short whose script passed its gate but whose video is not finished (a cut, a crash)


def _pending_short() -> dict | None:
    import checkpoint

    saved = checkpoint.read_json(PENDING_SHORT)
    if not isinstance(saved.get("data"), dict) or not saved.get("topic") or saved.get("tries", 0) >= MAX_RESUMES:
        return None
    return saved


def _finished_pending(saved: dict, pending: Path) -> Path | None:
    """The saved video's own folder when that video was already finished: its record and video are there, so a cut came after the record was saved and
    before the saved script was cleared (21 Nov 2026 review: the resume then made the same video again in a new folder, a duplicate). The producer's last
    two steps are completed (its work folder removed, the saved script cleared) and nothing is made again."""
    old = config.OUT / saved["folder"] if saved.get("folder") else None
    if not old or not (old / "meta.json").is_file() or not (old / "video.mp4").is_file():
        return None
    try:
        meta = json.loads((old / "meta.json").read_text())
    except (OSError, ValueError):
        return None
    data = saved.get("data") or {}
    topic = data.get("topic") or saved.get("topic")
    if meta.get("title") != data.get("title") and not (topic and meta.get("topic") == topic):  # the title may have been polished since; the topic stays
        return None
    shutil.rmtree(old / "work", ignore_errors=True)
    pending.unlink(missing_ok=True)
    pending.with_name(pending.name + ".prev").unlink(missing_ok=True)
    print(f"The saved {'Short' if pending == PENDING_SHORT else 'film'} was already finished in {old.name} (a cut came just after its record was saved): nothing is made again")
    return old


def _cmd_make(topic: str | None = None, extra: dict | None = None) -> Path:
    saved = _pending_short() if not topic and not extra else None
    done = _finished_pending(saved, PENDING_SHORT) if saved else None
    if done:
        return done
    if saved:  # 20 Nov 2026 (load-shedding): an unfinished Short continues in its own folder; kept voice lines and checked scenes are not made again
        import checkpoint

        old = config.OUT / saved["folder"] if saved.get("folder") else None
        cut = bool(old and checkpoint.was_interrupted(old / "work"))
        if not cut:
            saved["tries"] = saved.get("tries", 0) + 1
        checkpoint.write_json(PENDING_SHORT, saved)
        print(f"Resuming the saved Short (try {saved['tries']}{', after an interruption' if cut else ''}): {saved['data'].get('title', '')}")
        return _produce_short(saved["data"], saved["topic"], folder=old if old and old.is_dir() and not (old / "meta.json").exists() else None, pending=True)
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

    src = wikipedia.facts_for(topic, chars=SHORT_SOURCE_CHARS)
    note = ""
    for attempt in range(3):
        try:
            data = scriptgen.script(topic, grounded=src[1] if src else None, note=note)
            data = _script_gate(data, src[1] if src else "", topic)
            if src:
                data["sources"] = [f"Wikipedia: {src[0]} (CC BY-SA 4.0), retold in our own words"]
            data["anchors"] = anchor_terms(topic, data.get("anchors", []), src[0] if src else "")
            break
        except Exception as e:  # bad JSON or too short: ask again, and say what was wrong
            print(f"  script attempt {attempt + 1} failed: {e}")
            lo, hi = scriptgen.short_word_range()
            note = f"YOUR LAST ATTEMPT WAS REJECTED: {str(e)[:200]}. Fix exactly that. Count the words of every line: the whole script must have between {lo + 6} and {hi} words (a longer script is better than a shorter one here), 11 lines."
    if not data:
        raise SystemExit("could not generate a script")
    data.update(extra or {})
    return _produce_short(data, topic, pending=not extra)


@_records_stop
def _produce_short(data: dict, topic: str, requeue: bool = True, pool_size: int = 6, min_unique: int = 4, folder: Path | None = None, pending: bool = False) -> Path:
    """Voice, footage, render and metadata for a finished Short script. requeue: put the topic back in the queue if footage is missing.
    folder: re-render inside this existing folder (it is never removed if the footage is missing)."""
    data = _apply_house_style(data, "short", folder)
    data.setdefault("format", "short")  # 20 Nov 2026: a new Short's record had no format key (records.format_of guessed right, but every reader should not have to guess)
    data["lines"], n = scriptgen.subscribe_invitation(data["lines"])  # every render path (new, redo, repair, clip): the voice and the captions say "subscribe", never "follow"
    if n:
        print("  closing invitation reworded: subscribe, not follow")
    slug = re.sub(r"[^a-z0-9]+", "-", data["title"].lower()).strip("-")[:50]
    in_place = folder is not None
    folder = folder or unique_folder(config.OUT / slug)
    work = folder / "work"
    folder.mkdir(parents=True, exist_ok=True)
    import checkpoint

    _RUN_WORK.append(work)
    began = checkpoint.start_run(work, "short")
    if began["interrupted"]:
        print(f"  this Short was interrupted (last run started {began['previous'].get('started', '?')}): resuming; kept voice lines and checked scenes are not made again")
    if pending:  # saved with its look applied, so a resume renders the same Short in the same folder
        old = checkpoint.read_json(PENDING_SHORT)
        same = old.get("data", {}).get("title") == data.get("title")
        checkpoint.write_json(PENDING_SHORT, {"data": data, "topic": topic, "folder": folder.name, "tries": old.get("tries", 0) if same else 0})
    if scriptgen.thin_script(data["lines"]):  # refuse before a voice and pictures are paid for
        if requeue:
            topicqueue.requeue_failed(topic)
        if not in_place:
            shutil.rmtree(folder, ignore_errors=True)
        if pending:
            PENDING_SHORT.unlink(missing_ok=True)
        raise SystemExit("the Short's script admits its sources say little; not made")
    import a2a

    a2a.handoff(data, "script", job=folder.name, work=work, min_lines=3)  # 21 Nov 2026: a Short's stages are checked and recorded like a film's (a2a.py)
    print("Voice + captions...")
    prof = editprofile.load()
    voice = {"style": data["voice_style"]} if data.get("voice_style") else {}  # only a video that asks for one gets a styled voice
    if data.get("voice_tail") is not None:
        voice["tail"] = data["voice_tail"]
    narration, ass, durations = tts.narrate([l["text"] for l in data["lines"]], work, editprofile.short_pause(prof), prof["motion"], prof["caption_pos"], **voice)
    data["voice_used"] = tts.voice_used(data.get("voice_style"))  # saved with the record at the end of this producer (a new video has no record yet)
    checkpoint.mark_stage(work, "voice", lines=len(durations), seconds=round(sum(durations), 2))
    a2a.handoff(data, "voice", job=folder.name, work=work, narration=narration, durations=durations)
    print("Footage...")
    if config.PEXELS_KEY:
        clips = [footage.clip_for(l["visual"]) for l in data["lines"]]
        credits = footage.collect_credits(clips)
    else:  # archive pictures: only ones that name the subject
        import aiart

        bl_got = _blender_scenes(data, durations, "short", (config.WIDTH, config.HEIGHT))  # a vertical globe at the story's place, a true-to-the-line 3D scene (blenderscenes.py)
        bl_still = {data["lines"][i]["text"]: (pic, credit) for i, (pic, credit) in bl_got.items() if pic.suffix.lower() == ".png"}
        art = lambda l: bl_still.get(l["text"]) or aiart.generate(l["text"], l.get("visual", ""), topic, vertical=True, style=data.get("art_style"), case=_is_case(data))
        finder = _real_finder(data, "short")
        clips, credits, stats = footage.scene_images(data["lines"], topic, data.get("anchors") or [], pool_size=pool_size, judge=_image_judge(topic),
                                                     art=art, art_limit=12 if data.get("art_style") == "3d" else aiart.MAX_PER_VIDEO["short"],
                                                     art_first=bool(data.get("art_first")), force_art=_forced_art(data), finder=finder, real_when_named=_real_photos_on(data))
        data["assets"] = finder.assets if finder else []
        data["footage"] = stats
        if stats["missing"] or stats["unique"] < min_unique:
            clips = [None] * len(clips)
        else:
            import blenderscenes

            clips, credits = blenderscenes.place(clips, credits, bl_got)
    if not footage.enough_footage(clips):
        if requeue:
            kept = topicqueue.requeue_failed(topic)  # to the back of the queue, so the next run tries another topic; dropped after two failures
        if not in_place:
            shutil.rmtree(folder, ignore_errors=True)
        if pending:
            PENDING_SHORT.unlink(missing_ok=True)  # the same script finds the same footage: a new topic next time
        raise SystemExit("not enough footage found for this Short" + (("; topic moved to the back of the queue" if kept else "; topic dropped after two failed tries") if requeue else ""))
    clips, credits, anim = _animate(data, clips, credits, durations, vertical=True)  # a 3D Short can have a few moving clips
    clips = _parallax(data, clips, durations, (config.WIDTH, config.HEIGHT))  # free 2.5D camera motion when the Short asks for it
    if anim:
        data["animation"] = anim
        print(f"  animation: {anim['animated']} new clip(s), {anim['cached']} from the cache, {anim['failed']} failed, ${anim['spent']:.2f} spent")
    checkpoint.mark_stage(work, "visuals", scenes=len(clips))
    a2a.handoff(data, "visuals", job=folder.name, work=work, clips=clips, min_share=0.6)  # a Short may show a plain colour on a few scenes (footage.enough_footage)
    print("Rendering...")
    import musicbed

    music_bed, music_used = musicbed.bed(sum(durations), work, str(data.get("topic") or data.get("title", "")))  # a quiet public-domain bed under the Short too (20 Nov 2026)
    data["music"] = musicbed.record(music_used)
    render.render(clips, durations, narration, ass, work, folder / "video.mp4", loudness=editprofile.lufs_for(data, prof), shots=prof["motion"] >= 1, music=music_bed,
                  crossfade=0.3 if prof["motion"] >= 2 and len(clips) <= 20 else 0.0, grain=prof["motion"] >= 2)
    checkpoint.mark_stage(work, "assembled", seconds=round(checkpoint.media_seconds(folder / "video.mp4"), 2))
    import subscribe

    subscribe.add_to(folder / "video.mp4", data, "short", durations, subtitles.load_words(work / "words.json"), (config.WIDTH, config.HEIGHT))  # the pop-up lands on the spoken 'subscribe'
    import sfx

    sfx.add_to(folder / "video.mp4", data, "short", durations)  # a riser into the first word and a hit on the second line (audio only, the picture is copied)
    shutil.copy(work / "words.json", folder / "words.json")
    subtitles.write_files(folder, subtitles.with_punctuation(subtitles.load_words(work / "words.json"), [l["text"] for l in data["lines"]]))
    data["subtitles"] = "burned"
    data["credits"] = credits
    data["approved"] = False
    a2a.handoff(data, "render", job=folder.name, work=work, video=folder / "video.mp4", durations=durations)  # the video exists, decodes, and is as long as its narration
    records.save(folder, data)  # the producer owns the record until it is finished: one atomic whole save
    shutil.rmtree(work)  # only after the record is saved (a cut in between keeps the checked scenes)
    if pending and checkpoint.read_json(PENDING_SHORT).get("folder") == folder.name:
        PENDING_SHORT.unlink(missing_ok=True)
        PENDING_SHORT.with_name(PENDING_SHORT.name + ".prev").unlink(missing_ok=True)
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


def _write_pending(saved: dict) -> None:
    """The saved script is written atomically, with the previous version kept (checkpoint.write_json): a power cut during this write once could have left half a file and
    lost a paid or hours-long script."""
    import checkpoint

    checkpoint.write_json(PENDING_DOC, saved)


def _pending_doc() -> dict | None:
    import checkpoint

    saved = checkpoint.read_json(PENDING_DOC)  # the previous version when the current one is unreadable
    if not saved:
        return None
    if not isinstance(saved.get("data"), dict) or saved.get("tries", 0) >= MAX_RESUMES:
        return None
    lines = saved["data"].get("lines")
    words = sum(len(str(l.get("text", "")).split()) for l in lines) if isinstance(lines, list) else 0
    need = round(scriptgen.min_doc_words() * 0.9)  # by words, not lines: a long film joins short lines (scriptgen.join_short_lines), so 70 lines can be 22 minutes
    if isinstance(lines, list) and lines and words < need:
        _set_aside_pending(saved, f"it has {words} words in {len(lines)} lines and the owner's documentary length ({scriptgen.DOC_MINUTES[0]:g} to {scriptgen.DOC_MINUTES[1]:g} "
                                  f"minutes) needs about {need}" + ("; it was also written without a source article" if saved["data"].get("grounded") is False else ""))
        return None
    return saved


def _set_aside_pending(saved: dict, why: str) -> None:
    """A saved script written for an older, shorter length rule is not rendered (20 Nov 2026: the 54-line Pyramids script, written without a source under the 8 to 10 minute
    rule, would have been Autopilot's next film after the owner chose 20 to 26 minutes). It is kept beside the original name, never deleted, and the owner is told once."""
    import datetime as dt

    import agentlog

    keep = PENDING_DOC.with_name(f"pending_doc.set-aside-{dt.datetime.now(dt.timezone.utc):%Y%m%d-%H%M%S}.json")
    try:
        PENDING_DOC.replace(keep)
    except OSError:
        return
    agentlog.event("info", f"Set aside a saved script: {str(saved['data'].get('title', ''))[:60]}",
                   f"Not rendered because {why}. It is kept as data/{keep.name}; the next film starts from a new topic.")
    print(f"  saved script set aside ({why}): {keep.name}")


def _cmd_doc(topic: str | None = None, photo: bool = False) -> Path:
    import random

    saved = _pending_doc() if not topic else None
    done = _finished_pending(saved, PENDING_DOC) if saved else None
    if done:
        return done
    if saved:
        import checkpoint

        old = config.OUT / saved["folder"] if saved.get("folder") else None
        cut = bool(old and checkpoint.was_interrupted(old / "work"))  # a power cut or a kill is not a failed try: the film continues where it stopped
        if not cut:
            saved["tries"] = saved.get("tries", 0) + 1
        _write_pending(saved)
        print(f"Resuming the saved script (try {saved['tries']}{', after an interruption' if cut else ''}): {saved['data']['title']}")
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

    chars_each, keep = scriptgen.source_budget()  # enough source text for the owner's length (7,000 x 2 at 8-10 minutes, about 18,000 x 3 at 20-26)
    arts = wikipedia.facts_multi(topic, n=keep + 1, chars_each=chars_each)  # the best articles: a script drawn from more than one source has fewer unsupported details
    if arts and not wikipedia.is_media_work(arts[0]["text"]):  # a folklore or history topic is not retold from a film's plot: keep the main article, drop adaptations
        arts = [arts[0]] + [a for a in arts[1:] if not wikipedia.is_media_work(a["text"])]
    arts = arts[:keep]
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
            words, need = sum(len(str(l.get("text", "")).split()) for l in data["lines"]), round(0.9 * scriptgen.min_doc_words())
            if words < need:  # the owner's length (rules.json long_min_minutes) is a gate before any voice is made, the same 90 % _pending_doc keeps on a resume
                raise ValueError(f"the script is {words} words; the owner's shortest documentary needs about {need}")  # (22 Nov 2026 audit: a 1,500-word script rendered)
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
            if "could not be fact-checked" in str(e):  # no free judge (busy, or the day's free requests are used up): asking again at once only burns the saved
                raise SystemExit("the written draft is saved (data/pending_draft.json) and waits for a free judge: the next make checks it, nothing is written again")  # draft
    else:  # no attempt reached `break`: whatever `data` holds was refused (22 Nov 2026 audit: a thin script refused in attempt 1 stayed in `data` when the
        raise SystemExit("could not generate a documentary script that passed its checks")  # later attempts failed, and was voiced and rendered ungated)
    if not data:
        raise SystemExit("could not generate a documentary script")
    if photo:  # realistic invented people (owner's request): the video is held and unapproved, nothing about it goes out until the owner says so
        data.update(art_style="photo", art_first=True, hold=True)
    PENDING_DOC.parent.mkdir(parents=True, exist_ok=True)
    _write_pending({"data": data, "folder": "", "tries": 0})
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


@_records_stop
def _produce_doc(data: dict, folder: Path | None = None) -> Path:
    import random

    data = _apply_house_style(data, "doc", folder)
    local = data.get("local_pictures") or []
    if local and (len(local) != len(data["lines"]) or [p for p in local if not Path(p).exists()]):
        raise SystemExit("pictures not ready: " + ", ".join(Path(p).name for p in local if not Path(p).exists()) if len(local) == len(data["lines"]) else "local_pictures needs one picture per line")
    if _real_media_on(data):
        data.setdefault("real_footage", 4)  # up to four real Commons clips where they truly fit (footage_real.py); none when none is found

    slug = "doc-" + re.sub(r"[^a-z0-9]+", "-", data["title"].lower()).strip("-")[:45]
    in_place = folder is not None  # a re-render inside an existing video's folder: that folder is never removed (28 Oct 2026: a re-render at the picture budget removed a whole video)
    folder = folder or unique_folder(config.OUT / slug)
    work = folder / "work"
    folder.mkdir(parents=True, exist_ok=True)
    import checkpoint

    _RUN_WORK.append(work)
    began = checkpoint.start_run(work, "doc")
    if began["interrupted"]:
        import agentlog

        kept = ", ".join(sorted(began["stages"])) or "nothing yet"
        print(f"  this film was interrupted (its last run started {began['previous'].get('started', '?')} and never finished): resuming; stages already done: {kept}")
        agentlog.event("info", f"Resuming an interrupted film: {str(data.get('title', ''))[:60]}",
                       f"The last run started {began['previous'].get('started', '?')} and stopped without finishing (a power cut, a restart or a kill). "
                       f"Finished voice lines, checked scenes and drawn pictures are kept; only the missing work is done again. Stages done before: {kept}.")
    pending_mine = False  # a pending doc for ANOTHER video must survive this production (19 Nov 2026: redoing one film deleted the next pending build)
    if PENDING_DOC.exists():
        try:
            saved = json.loads(PENDING_DOC.read_text())
            if saved.get("data", {}).get("title") == data.get("title"):
                saved["folder"] = folder.name
                _write_pending(saved)
                pending_mine = True
        except (OSError, ValueError):
            pass
    import a2a

    a2a.handoff(data, "script", job=folder.name, work=work)  # the orchestrator checks each stage's real output before the next starts (a2a.py): lines, chapters
    print("Voice...")
    prof = editprofile.load()
    tail = {"tail": data["voice_tail"]} if data.get("voice_tail") is not None else {}  # a video that asks keeps less of the voice service's silence after each line
    narration, _ass, durations = tts.narrate([l["text"] for l in data["lines"]], work, prof["sentence_pause_ms"] / 1000, **tail)
    data["voice_used"] = tts.voice_used(None)  # before the hand-over, so its row names the voice
    checkpoint.mark_stage(work, "voice", lines=len(durations), seconds=round(sum(durations), 2))
    a2a.handoff(data, "voice", job=folder.name, work=work, narration=narration, durations=durations)  # a narration file and one timing per line
    if local:  # pictures drawn elsewhere for free (ccdoc.py): no search, no paid drawing, no stock footage, no animation
        clips = [Path(p) for p in local]
        credits = list(data.get("local_credits") or [])
        finder = None  # no library search: the record lists no library assets (20 Nov 2026: this name was unset and the finished film crashed before its record was saved)
        stats = {"scenes": len(clips), "unique": len({str(c) for c in clips}), "missing": 0, "drawn": 0}
    else:
        print("Archival images (only pictures that name the subject)...")
        anchors = data.get("anchors") or []
        import aiart

        bl_got = _blender_scenes(data, durations, "doc", (1920, 1080))  # a globe at the story's place and true-to-the-line 3D scenes, rendered headless (blenderscenes.py)
        bl_still = {data["lines"][i]["text"]: (pic, credit) for i, (pic, credit) in bl_got.items() if pic.suffix.lower() == ".png"}
        forced, ran_out = _forced_art(data), []

        def art(l):  # a line Blender drew is not drawn again; style "3d": a 3D animated-film look
            got = bl_still.get(l["text"]) or aiart.generate(l["text"], l.get("visual", ""), data["topic"], style=data.get("art_style"), case=_is_case(data))
            if got is None and l["text"] in forced and _free_pictures_spent():
                ran_out.append(l["text"])  # a scene that must be drawn found today's free allowance spent
            return got

        finder = _real_finder(data, "doc")
        pics = dict(judge=_image_judge(data["topic"]), art=art, art_first=bool(data.get("art_first")), force_art=_forced_art(data), finder=finder, real_when_named=_real_photos_on(data))
        clips, credits, stats = footage.scene_images(data["lines"], data["topic"], anchors, art_limit=aiart.MAX_PER_VIDEO["doc"], **pics)
        if stats["unique"] < MIN_VARIETY * stats["scenes"] and aiart.enabled():  # the same few pictures again and again: draw illustrations for the scenes that would repeat
            print(f"  only {stats['unique']} different pictures for {stats['scenes']} scenes: drawing more")
            clips, credits, stats = footage.scene_images(data["lines"], data["topic"], anchors, art_limit=aiart.MAX_PER_VIDEO["doc"] + aiart.EXTRA_FOR_VARIETY, **pics)
        if ran_out:
            _wait_for_pictures(data, folder, len(set(ran_out)), len(data["lines"]))
        if stats["missing"] or stats["unique"] < 6:
            shutil.rmtree(work if in_place else folder, ignore_errors=True)
            raise SystemExit(f"only {stats['unique']} on-topic images found ({stats['missing']} scenes without one); "
                             "not rendering a video of unrelated pictures")
        clips, credits = _real_footage(data, clips, credits)  # real moving footage on the scenes that may carry it (before the animation step: a real clip is not animated)
        import blenderscenes

        clips, credits = blenderscenes.place(clips, credits, bl_got)  # the lines Blender was planned for show Blender's scene (its stills then get camera motion from their exact depth)
        clips, credits, anim = _animate(data, clips, credits, durations)  # some drawn scenes become short moving clips when the video asks for it
        if anim:
            data["animation"] = anim
            print(f"  animation: {anim['animated']} new clip(s), {anim['cached']} from the cache, {anim['failed']} failed, ${anim['spent']:.2f} spent")
    clips = _parallax(data, clips, durations, (1920, 1080))  # free 2.5D camera motion when the video asks for it
    import musicbed

    music_bed, music_used = musicbed.bed(sum(durations), work, str(data.get("topic") or data["title"]))  # different public-domain tracks under the whole film, never one looped (musicbed.py)
    data["music"] = musicbed.record(music_used)
    checkpoint.mark_stage(work, "visuals", scenes=len(clips))
    a2a.handoff(data, "visuals", job=folder.name, work=work, clips=clips)  # a real picture or clip file for every line
    print(f"Rendering ({sum(c is not None for c in clips)}/{len(clips)} scenes have footage)...")
    words = subtitles.with_punctuation(subtitles.load_words(work / "words.json"), [l["text"] for l in data["lines"]])
    doc_ass = None
    if config.DOC_SUBTITLES:
        doc_ass = work / "doc_captions.ass"
        doc_ass.write_text(subtitles.to_ass(subtitles.build_cues(words), (1920, 1080), prof["caption_pos"]))
        import motiongraphics

        if data.get("graphics"):  # 2D chapter title cards and date badges, from the chapter list and the years the script writes (and the hook question)
            events = motiongraphics.graphics_events(data, durations, (1920, 1080))
            motiongraphics.add_to_ass(doc_ass, events, (1920, 1080))
            data["graphics"] = {"events": len(events)}
            print(f"  2D graphics: {len(events)} animated event(s)")
        else:  # a film that asks for no other graphics still opens with its question on screen (switch hook_text false)
            events = motiongraphics.hook_events(data, (1920, 1080))
            if events:
                motiongraphics.add_to_ass(doc_ass, events, (1920, 1080))
                print("  hook question on screen")
    render.render(clips, durations, narration, doc_ass, work, folder / "video.mp4",
                  size=(1920, 1080), music=music_bed, loudness=editprofile.lufs_for(data, prof), shots=prof["motion"] >= 1)
    checkpoint.mark_stage(work, "assembled", seconds=round(checkpoint.media_seconds(folder / "video.mp4"), 2))
    import subscribe

    subscribe.add_to(folder / "video.mp4", data, "doc", durations, [], (1920, 1080))  # one or two branded pop-ups at high points: the film itself ends on the story
    import sfx

    sfx.add_to(folder / "video.mp4", data, "doc", durations, data.get("chapters"))  # riser, hit on the reveal, whoosh at chapter changes, swell on the payoff
    shutil.copy(work / "words.json", folder / "words.json")
    subtitles.write_files(folder, words)
    starts, t = [], 0.0
    for n, ch in enumerate(data["chapters"], 1):
        t = sum(durations[: ch["start_line"]])
        starts.append(f"{int(t // 60)}:{int(t % 60):02d} {ch['title'] or f'Part {n}'}")
    intro = data["description"].split("\n\nChapters:")[0].split("\n\nSources:")[0]
    import ccdoc

    src = "".join(f"\n{x}" for x in ccdoc.source_lines(data))  # sources are dicts of title+url: their repr()s once went into a description verbatim
    data["description"] = intro + (f"\n\nSources:{src}" if src else "") + "\n\nChapters:\n" + "\n".join(starts)
    data["footage"] = stats
    data["credits"] = credits
    data["assets"] = finder.assets if finder else []  # every library picture: address, licence, credit, date, hash
    data["subtitles"] = "burned" if config.DOC_SUBTITLES else "srt"
    data["approved"] = False
    a2a.handoff(data, "render", job=folder.name, work=work, video=folder / "video.mp4", durations=durations)  # the video exists, decodes, and is as long as its narration
    records.save(folder, data)
    shutil.rmtree(work)  # only after the record is saved: a cut before this point leaves the checked scenes for the next run, never a folder with neither
    if pending_mine:
        PENDING_DOC.unlink(missing_ok=True)  # this production was the pending script's own build: it is spent now
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


def _free_pictures_spent() -> bool:
    """True when free drawing is set up but today's allowance cannot pay for one more film picture (freeart.py)."""
    try:
        import freeart

        return freeart.have_keys() and freeart.quota_left() < freeart.neurons(1024, 576)
    except Exception:
        return False


def _wait_for_pictures(data: dict, folder: Path, short: int, total: int) -> None:
    """A film whose every scene is drawn stops when today's free pictures run out, instead of being rendered with the same few pictures again and again (20 Nov 2026:
    a 20 to 26 minute film needs 84 to 100 pictures, about 9,000 to 15,000 Neurons, against a 9,000 a day allowance). Every picture drawn so far is kept in the cache and
    costs nothing next time, the script stays in data/pending_doc.json, and this stop does not use up one of its three tries: the next make continues the same film
    after the allowance resets at 00:00 UTC."""
    import agentlog

    try:
        saved = json.loads(PENDING_DOC.read_text())
        if saved.get("data", {}).get("title") == data.get("title"):
            saved["tries"] = max(0, int(saved.get("tries", 0)) - 1)
            saved["folder"] = folder.name
            saved["waiting_for_pictures"] = {"short": short, "total": total}
            _write_pending(saved)
    except (OSError, ValueError):
        pass
    msg = (f"{short} of {total} scenes still need a drawn picture and today's free picture allowance is spent; the {total - short} drawn so far are kept. "
           "The same film continues after the allowance resets at 00:00 UTC (data/pending_doc.json).")
    agentlog.event("info", f"Waiting for tomorrow's free pictures: {str(data.get('title', ''))[:60]}", msg)
    raise SystemExit("waiting for pictures: " + msg)


def _blender_scenes(data: dict, durations: list, fmt: str, size: tuple[int, int]) -> dict:
    """Blender's scenes for this video (blenderscenes.py, 20 Nov 2026): {line: (file, credit)}. The plan and what was rendered go into data["blender"]. `blender` false in the
    record switches it off; any failure gives no Blender scenes and the video is made exactly as before."""
    if data.get("blender") is False:
        return {}
    try:
        import blenderscenes

        coords = blenderscenes.coordinates(blenderscenes.source_title(data))
        planned = blenderscenes.plan(data, fmt, coords)
        if not planned:
            data["blender"] = {"planned": 0, "why": "no line names a place Blender can show truthfully" + ("" if coords else " and the source article has no coordinates")}
            print("  Blender: nothing planned (" + data["blender"]["why"] + ")")
            return {}
        print(f"  Blender: {len(planned)} scene(s) planned: " + ", ".join(f"{p['scene']} on line {p['line'] + 1}" for p in planned))
        got, stats = blenderscenes.render(planned, durations, size)
        data["blender"] = {**stats, "planned": len(planned), "coordinates": list(coords) if coords else None}
        print(f"  Blender: {len(got)} rendered, {len(stats['failed'])} failed" + (f" ({stats['failed'][0]['reason'][:120]})" if stats["failed"] else ""))
        return got
    except Exception as e:
        data["blender"] = {"failed": True, "reason": f"{type(e).__name__}: {str(e)[:200]}"}
        print(f"  Blender skipped ({type(e).__name__}): the usual pictures are used")
        return {}


def _parallax(data: dict, clips: list, durations: list, size: tuple[int, int]) -> list:
    """2.5D camera motion on the drawn pictures when the video asks for it (data["parallax"]); the stats replace the switch. Any failure leaves the plain camera moves:
    a video is never stopped for this."""
    if not data.get("parallax"):
        return clips
    import parallax

    try:
        clips, stats = parallax.apply(clips, durations, size, flat=parallax.flat_scenes(data["lines"]) if len(data.get("lines", [])) == len(clips) else None)
    except Exception as e:
        data["parallax"] = {"failed": True, "reason": type(e).__name__}
        print(f"  camera motion skipped ({type(e).__name__}): the usual camera moves are used")
        return clips
    data["parallax"] = stats
    print(f"  camera motion: {stats['made']} new clip(s), {stats['cached']} from the cache, {stats['failed']} failed ({stats['model']} with a depth map, {stats['approximate']} approximate)")
    return clips


LOOKS = {  # what a new video asks for besides its pictures and clips. "photo" is the Lost Army film's look (the owner's choice, 30 Oct 2026): realistic AI scenes, free camera motion (flat gentle zoom where
    # people may show), 2D chapter cards and date badges on a documentary, the shorter voice tail. "3d" is the storybook look Autopilot used before.
    "photo": {"doc": {"parallax": True, "graphics": True, "voice_tail": 0.15, "real_footage": 4}, "short": {"parallax": True}},
    "3d": {"doc": {}, "short": {}},
}
DEFAULT_LOOK = "photo"


def _house_style(kind: str) -> dict:
    """What Autopilot adds to a NEW video of this kind (autopilot.json house_style, `look` photo or 3d): the look, a few moving clips and its motion. Only when it is switched on and
    the account can pay for it (credit known and at least min_credit: an animated documentary costs about $3 to $4, a stopped render wastes it). {} otherwise."""
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
    import freeart

    free = freeart.usable()  # pictures drawn on the owner's free Cloudflare account: only the script and the reviews cost money, and no paid clips
    if not (free and llm.free_only()) and (credit is None or credit < float(hs.get("min_credit_free", 0.6) if free else hs.get("min_credit", 8.0))):
        return {}  # a free-only studio (free models, free pictures, paid models off) spends nothing, so the balance does not matter (13 Nov 2026)
    look = hs.get("look") if hs.get("look") in LOOKS else DEFAULT_LOOK  # an unknown look is the default, never an error in the middle of a build
    return {"art_style": look, "animate": 0 if free else int(part.get("clips", 0)), "animate_budget": 0.0 if free else float(part.get("budget", 1.0)), "art_first": True, "house_style": True, **LOOKS[look].get(kind, {})}


def _apply_house_style(data: dict, kind: str, folder) -> dict:
    """Only a new video gets it: a folder means a re-render in place (redo, repair), and a video that chose its own look (a remake) keeps it."""
    if folder is None and "art_style" not in data:
        data.update(_house_style(kind))
    return data


def _real_photos_on(data: dict) -> bool:
    """A forced (drawn) scene still takes a real photo that is named for its subject (footage.named_photo). Not for a 3D video, a video that draws everything on purpose, one that
    switched it off (`real_photos` false) or a real case (no photograph of a real victim or suspect)."""
    return data.get("real_photos") is not False and data.get("art_style") != "3d" and not data.get("draw_all") and not _is_case(data)


def _forced_art(data: dict) -> set[str]:
    """Narration lines that are always drawn, whatever a picture search finds: the lines flagged for a redraw, and for a 3D video also the first four (the hook is the
    drawn, animated scene, never a museum photo: the first remake showed photos for the first 75 seconds)."""
    forced = set(data.get("redraw_lines") or [])
    if data.get("draw_all"):  # the owner asked for a Short whose every scene is drawn in one look
        forced |= {l["text"] for l in data["lines"]}
    if data.get("art_style") == "photo":  # every scene is drawn: no reused picture, no chart or faded sketch from the archive (the first two realistic videos showed both)
        forced |= {l["text"] for l in data["lines"]}
    if data.get("art_style") == "3d":
        forced |= {l["text"] for l in data["lines"][:4]}
    if _is_case(data):  # a real case: no archive photograph of a real victim or suspect, every scene is drawn under the no-identifiable-person rule (aiart.CASE_PICTURES)
        forced |= {l["text"] for l in data["lines"]}
    return forced


def _animate(data: dict, clips: list, credits: list, durations: list[float] | None = None, vertical: bool = False) -> tuple[list, list, dict | None]:
    """Animate some drawn scenes when the video asks for it (data["animate"] = how many clips, data["animate_budget"] = dollars, default 3). Returns
    (clips, credits with the AI-video credit added, stats) or the inputs and None when not asked. durations (seconds per scene) let the free-mode
    motion (animate.animate_scenes -> parallax) fit each clip to its line."""
    n = int(data.get("animate") or 0)
    if n <= 0:
        return clips, credits, None
    import animate
    import modelcfg

    pinned = {"scenes": data["animate_scenes"]} if data.get("animate_scenes") else {}  # a video that names its own scenes; otherwise they are spread across it
    new, stats = animate.animate_scenes(clips, data["lines"], n, float(data.get("animate_budget", 3.0)), animate.clip_generator(vertical=vertical),
                                        size=(720, 1280) if vertical else (1280, 720), **pinned, **({"durations": durations} if durations else {}))
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
        topic, extra = _make_options(a[1:])
        cmd_make(topic, extra)
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
    elif a[0] == "writer-bench":  # free open models write Short scripts from our sources; scored by free rules only, no Claude call, nothing trained
        import writerbench

        now = llm._now()
        cs = writerbench.cases(int(a[a.index("--cases") + 1]) if "--cases" in a else 4)
        models = a[a.index("--models") + 1].split(",") if "--models" in a else freemodels_top(now, int(a[a.index("--top") + 1]) if "--top" in a else 4)
        print(f"{len(models)} free model(s) x {len(cs)} source(s): " + ", ".join(c["topic"] for c in cs))
        if "--list" in a:
            print("\n".join(models))
            return
        res = writerbench.run(models, cs, now=now)
        for s in res["summary"]:
            print(f"  usable {s['usable']}/{s['tries']}  answered {s['answered']}  mean {s['mean_score']:.2f}  {s['seconds']}s  {s['model']}  often fails: {', '.join(s['often_fails']) or '-'}")
        print("Saved in data/writerbench/. Free rules only: facts beyond numbers and years are NOT checked.")
    elif a[0] == "writer-bench-judge":  # a few cents: Claude as the fact-check JUDGE of one bench model's scripts; a report, never training data
        import benchjudge

        f = sorted((config.ROOT / "data" / "writerbench").glob("2*.json"))[-1] if len(a) < 3 else config.ROOT / "data" / "writerbench" / a[2]
        srcs = {c["topic"]: c["source"] for c in __import__("writerbench").cases(12)}
        rep = benchjudge.check(f, a[1], srcs)
        (config.ROOT / "data" / "writerbench" / ("judge-" + f.name)).write_text(json.dumps(rep, indent=1))
        for s_ in rep["scripts"]:
            print(f"  {s_['topic'][:34]:35} {s_['lines']} lines  " + (s_["error"] if "error" in s_ else ("all lines supported" if s_["ok"] else f"{len(s_['unsupported'])} unsupported: " + "; ".join(f"{n}: {w[:60]}" for n, w in s_["unsupported"].items()))))
        print(f"{rep['model']}: {rep['judged']} scripts judged, {rep['lines_flagged']} lines flagged, {rep['lines_ok_pct']}% of lines supported. Report only: not a label, not training data.")
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
    elif a[0] == "recover":  # read-only: what a power cut left unfinished and the safe step that continues it (recovery.py)
        import recovery

        items = recovery.scan(thorough="--thorough" in a)
        print(json.dumps(items, indent=1) if "--json" in a else recovery.report(items))
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
    elif a[0] == "demand":  # search demand (searchdemand.py): `demand` refreshes every queued topic (YouTube part for the best 5), `demand <topic> [--youtube]` reads one
        import searchdemand

        def _show(r):
            p = r["parts"]
            ac, wp, yt = p.get("autocomplete"), p.get("wikipedia"), p.get("youtube")
            print(f"{(r['score'] if r['score'] is not None else '-')!s:>5}  {r['subject'][:44]:44}  autocomplete {ac['hits'] if ac else '-'}/10  "
                  f"wikipedia {wp['avg_30'] if wp else '-'}/day" + (f" (x{wp['trend']})" if wp and wp.get("trend") else "")
                  + (f"  youtube median {yt['median_views']:,} views, {yt['recent']} recent, {yt['small_channel_wins']} small-channel wins" if yt else ""))

        words = [x for x in a[1:] if not x.startswith("--")]
        if words:
            _show(searchdemand.demand(" ".join(words), with_youtube="--youtube" in a))
        else:
            d = searchdemand.refresh()
            print(f"{len(d['rows'])} queued topics read, {d['youtube_searches']} YouTube searches ({d['youtube_searches'] * 100} quota units)")
            for r in d["rows"][:20]:
                _show(r)
    elif a[0] == "comments":  # what viewers ask (commentinsights.py): questions from public comments, read only, nothing kept over 30 days; --force reads again today
        import commentinsights

        d = commentinsights.run(force="--force" in a)
        print(f"{len(d['own'])} questions on our videos, {len(d['niche'])} under the reference channels' top videos, {len(d['clusters'])} groups, "
              f"{len(d['ideas'])} topic ideas, {d['quota_units']} quota units" + (f"; problems: {'; '.join(d['errors'][:3])}" if d["errors"] else ""))
        for g in d["clusters"][:5]:
            print(f"  {g['count']:>3} x {g['label']}: {g['examples'][0][:100]}")
        for t in d["ideas"]:
            print(f"  idea: {t}")
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
    elif a[0] == "depth-setup":  # fetch the depth model once (27 MB, hash-checked) so this machine can make its own depth maps for camera motion
        import depth

        f = depth.ensure_model()
        rt = depth._runtime()
        print(f"model: {f} ({f.stat().st_size:,} bytes, SHA-256 checked)\nnumpy and onnxruntime: {'installed' if rt else 'NOT installed: pictures get approximate depth'}")
    elif a[0] == "sources-test":  # one live search in every picture and footage library (reads only; says which need a key)
        import openmedia

        print(openmedia.format_selftest(openmedia.selftest(" ".join(a[1:]) or "pyramids")))
    elif a[0] == "pixabay-test":  # one live look-up with the saved Pixabay key (reads only, nothing is downloaded or used in a video)
        import pixabay

        print(pixabay.selftest(" ".join(a[1:]) or "pyramids"))
    elif a[0] == "listen" and len(a) > 1:  # the studio listens to a finished video's narration and compares it with the script (a warning only; about a cent a film)
        import voicecheck

        res = voicecheck.listen(config.OUT / a[1], local=voicecheck.whisper_text if "--local" in a else None)  # --local: free, on this PC (faster-whisper), nothing sent anywhere
        if "error" in res:
            print("could not listen:", res["error"])
        else:
            records.merge(config.OUT / a[1], {"voice_check": voicecheck.summary(res)})
            print(f"{'OK' if res['ok'] else 'CHECK'}: {res['match'] * 100:.1f}% of {res['words']} words match the script, {len(res['gaps'])} gap(s), cost ${res['cost']:.4f} ({res['model']})")
            for g in res["gaps"]:
                print(f"  {g['kind']} {g['words']} words: script '{g['script']}' / heard '{g['heard']}'")
            if res["heard_as"]:
                print("  heard differently (leads, not proof):", "; ".join(f"{x} -> {y}" for x, y in res["heard_as"]))
            print(" ", res["coverage"])
    elif a[0] == "channel-sync":  # read the channel, write its real video ids into local records (after the VPS records were lost, 17 Nov 2026); --apply writes
        import channelsync
        import upload

        try:
            yt = upload._service()
            vids = channelsync.channel_videos(yt)
        except Exception as e:
            print(f"YouTube login expired or refused ({type(e).__name__}): re-run the login. Nothing was changed.")
            raise SystemExit(2)
        plan = channelsync.plan_adoptions(channelsync.local_records(config.OUT), vids)
        print(f"Channel: {len(vids)} videos. Local folders already holding an id: {plan['already']}.")
        for r in plan["adopt"]:
            print(f"  ON YOUTUBE, record missing: {r['slug']} -> {r['video_id']} (matched by {r['by']}, scheduled {r['publishAt']})")
        for c in plan["conflicts"]:
            print(f"  CONFLICT (owner decides, nothing written): {json.dumps(c)}")
        for s in plan["unmatched_local"]:
            print(f"  approved but NOT on the channel: {s}")
        for s in plan["unreadable"]:
            print(f"  UNREADABLE record (not checked, not changed; it cannot be uploaded either): {s}/meta.json")
        if "--apply" in a:
            print(f"Written: {channelsync.apply_adoptions(config.OUT, plan)} records.")
            for f in plan["failed"]:
                print(f"  NOT written, run again: {f['slug']} ({f['error']})")
        else:
            print("Preview only. Run again with --apply to write the ids.")
    elif a[0] == "reschedule" and len(a) > 1:  # the owner's command: a new future time for an approved video that is private past its publish time with no schedule (Autopilot never does this by itself)
        import datetime as dt

        import autopilot
        import reschedule

        now = dt.datetime.now(dt.timezone.utc)
        with autopilot.exclusive():
            print(json.dumps(reschedule.apply(a[1], autopilot.governed(autopilot.load_config(), now), now) or {"done": True}, indent=2, default=str))
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
    elif a[0] == "judges":  # who would judge this video's AI review now, and why each model is or is not eligible; asks no model (judges.py)
        import judges

        meta = json.loads((config.OUT / a[1] / "meta.json").read_text()) if len(a) > 1 else {}
        print(json.dumps(judges.plan(meta), indent=1, default=str))
    elif a[0] == "review":
        import reviewer

        r = reviewer.review(config.OUT / a[1])
        print(r["verdict"])
        for c in r["checks"]:
            print(("ok   " if c["ok"] else "FAIL ") + f"{c['severity']:5} {c['name']}: {c['detail']}")
    elif a[0] == "autopilot":
        import autopilot

        if a[1:2] == ["make"] and a[2:3] in (["short"], ["doc"]):  # one supervised make + review by Autopilot's own steps; never approves, schedules or uploads
            print(json.dumps(autopilot.make_one(a[2], review="--no-review" not in a), indent=2))
        else:
            print(json.dumps(autopilot.tick() if a[1:] == ["tick"] else autopilot.status(), indent=2))
    elif a[0] == "specrun":  # free videos from specs written by Claude (specrun.py): tick (default), status, check DIR
        import specrun

        if a[1:2] == ["status"]:
            print(json.dumps(specrun.status(), indent=1))
        elif a[1:2] == ["check"]:
            kind, _spec, errors, warns = specrun.check(Path(a[2]))
            print(f"{kind}: " + ("REFUSED:\n- " + "\n- ".join(errors) if errors else "spec ok") + "".join(f"\nwarning: {w}" for w in warns))
        else:
            print(json.dumps(specrun.tick(), indent=1))
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
