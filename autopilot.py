"""Autopilot: decides what to do next (plan_actions) and does it (tick). Run every 30 minutes by a systemd timer."""
import datetime as dt
import fcntl
import json
import re
import os
from pathlib import Path

import config
import scheduler

CONFIG_FILE = config.ROOT / "autopilot.json"
STATE_FILE = config.ROOT / "autopilot_state.json"
LOCK_FILE = config.ROOT / "autopilot.lock"
NEWS_QUEUE = config.ROOT / "news_queue.json"
LOG = config.ROOT / "logs" / "autopilot.log"
JOB_FILE = config.ROOT / "job.pid"   # written by the dashboard while one of its jobs runs

DEFAULTS = {
    "enabled": False,            # master switch, off until the user turns it on
    "auto_approve": True,        # reviewer-agent "pass" counts as approval
    "uploads_per_day": 1,
    "review_window_hours": 24,   # time between a pass and the public slot, for the human veto
    "upload_lead_hours": 2,      # upload this long before the slot (private, publishAt set)
    "min_queue": 3,
    "max_waiting": 2,            # finished videos not yet uploaded
    "slots": scheduler.SLOTS_DEFAULT,
    "make_videos": True,         # off = repair, review and upload what exists, but start no new video (and no new research)
    "news_videos": True,         # build drafts from the weekly YouTube news digest (always need a human)
    "shorts": True,              # also make YouTube Shorts (vertical, under a minute)
    "shorts_per_day": 1,
    "max_waiting_shorts": 3,     # finished Shorts not yet uploaded
    "short_slots": scheduler.SHORT_SLOTS_DEFAULT,
}
MAX_FAILS = 3


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        cfg.update({k: v for k, v in json.loads(CONFIG_FILE.read_text()).items() if k in DEFAULTS})
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG_FILE.write_text(json.dumps({k: cfg[k] for k in DEFAULTS}, indent=2))


def _parse(ts: str) -> dt.datetime:
    return dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))


def counts_as_failure(exc: BaseException) -> bool:
    """Only video-specific problems count toward the 3-strike limit. Network, auth, quota and guard errors are retried."""
    name = type(exc).__name__
    if isinstance(exc, (SystemExit, OSError)) or name in ("RefreshError", "TransportError", "DefaultCredentialsError"):
        return False
    if name == "HttpError":
        status = getattr(getattr(exc, "resp", None), "status", 0)
        return not (status in (401, 403, 429) or status >= 500)
    return True


def dashboard_busy(job_file: Path = JOB_FILE) -> bool:
    """True while a dashboard job (its own make or upload) is running, so a tick never races it."""
    try:
        pid = int(job_file.read_text().strip())
        os.kill(pid, 0)
        return True
    except (FileNotFoundError, ValueError, ProcessLookupError):
        return False
    except PermissionError:
        return True


WRONG_PICTURES = 2  # sampled frames showing the wrong place, person or period that hold a video back
MAX_STUCK = 3  # stop making a kind of video while this many of it sit failed or waiting for a human


def plan_actions(state: dict, cfg: dict, now: dt.datetime) -> list[dict]:
    if not cfg["enabled"] or state["busy"]:
        return []
    acts = []
    total = state["uploads_today"]
    by_fmt = dict(state.get("uploads_by_format") or {"doc": state["uploads_today"]})
    lead = dt.timedelta(hours=cfg["upload_lead_hours"])
    waiting = {"doc": 0, "short": 0}
    stuck = {"doc": 0, "short": 0}  # reviewed and not good enough: they wait for a fix or for the owner, and new ones must not pile on top
    for v in state["videos"]:
        if v["video_id"] or v["hold"] or v["fails"] >= MAX_FAILS:
            continue
        fmt = v.get("format") or "doc"
        by_you = v["approved"] and v.get("approved_by") == "you"
        eligible = (v["verdict"] == "pass" and v["source"] != "news") or (v["verdict"] == "needs_human" and by_you)
        if v["verdict"] in ("fail", "needs_human") and not eligible and not by_you:
            stuck[fmt] += 1
        if v["verdict"] in (None, "pass") or eligible:
            waiting[fmt] += 1
        if v["verdict"] is None:
            acts.append({"do": "review", "slug": v["slug"]})
        elif v["verdict"] in ("fail", "needs_human") and not eligible and not by_you and v["source"] != "news" \
                and v.get("fix_attempts", 0) < 2 and not v.get("gave_up"):
            acts.append({"do": "fix", "slug": v["slug"]})  # the fixer agent repairs what it can, then the reviewer decides again
        elif eligible:
            if cfg["auto_approve"] and not v["approved"] and v["verdict"] == "pass":
                acts.append({"do": "approve", "slug": v["slug"]})  # reviewed earlier (by hand or by the fixer): the reviewer's pass counts
            pub = _parse(v["publish_at"]) if v["publish_at"] else None
            cap = cfg["shorts_per_day"] if fmt == "short" else cfg["uploads_per_day"]
            if pub is None or pub <= now + dt.timedelta(minutes=10):
                acts.append({"do": "schedule", "slug": v["slug"]})
            elif (v["approved"] and state["connected"] and by_fmt.get(fmt, 0) < cap
                  and total < config.MAX_UPLOADS_PER_DAY and pub - lead <= now):
                acts.append({"do": "upload", "slug": v["slug"]})
                by_fmt[fmt] = by_fmt.get(fmt, 0) + 1
                total += 1
    if not state["busy"] and cfg["make_videos"]:
        if state["queue_len"] < cfg["min_queue"]:
            acts.append({"do": "ideas", "slug": None})
        if cfg["shorts"] and waiting["short"] < cfg["max_waiting_shorts"] and stuck["short"] < MAX_STUCK:
            if state.get("clippable", 0) > 0:  # cut from our own documentaries first: no script to write, cheapest
                acts.append({"do": "make_clip", "slug": None})
            elif state["queue_len"] > 0:
                acts.append({"do": "make_short", "slug": None})
        if waiting["doc"] < cfg["max_waiting"] and stuck["doc"] < MAX_STUCK:
            if cfg["news_videos"] and state["news_pending"] > 0:
                acts.append({"do": "make_news", "slug": None})
            elif state["queue_len"] > 0:
                acts.append({"do": "make", "slug": None})
    return acts


def build_state(now: dt.datetime, cfg: dict) -> dict:
    import upload

    videos = []
    for m in sorted(config.OUT.glob("*/meta.json")):
        d = json.loads(m.read_text())
        videos.append({
            "slug": m.parent.name, "format": d.get("format", "short"), "source": d.get("source"), "approved": bool(d.get("approved")),
            "verdict": (d.get("review") or {}).get("verdict"), "hold": bool(d.get("hold")),
            "approved_by": d.get("approved_by"), "fix_attempts": d.get("fix_attempts", 0), "gave_up": bool(d.get("fix_gave_up")),
            "video_id": d.get("video_id"), "publish_at": d.get("publish_at"), "fails": d.get("autopilot_fails", 0),
        })
    by_fmt: dict = {}
    day = now.astimezone(dt.timezone.utc).strftime("%Y-%m-%d")
    for m in config.OUT.glob("*/meta.json"):
        d = json.loads(m.read_text())
        if str(d.get("uploaded_at", "")).startswith(day):
            by_fmt[d.get("format", "short")] = by_fmt.get(d.get("format", "short"), 0) + 1
    queue = json.loads(config.TOPICS_FILE.read_text()) if config.TOPICS_FILE.exists() else []
    news = json.loads(NEWS_QUEUE.read_text()) if NEWS_QUEUE.exists() else []
    return {
        "queue_len": len(queue), "connected": upload.SECRET.exists() and upload.TOKEN.exists(), "busy": dashboard_busy(),
        "uploads_today": upload.uploads_today(config.OUT, now), "uploads_by_format": by_fmt,
        "news_pending": sum(1 for n in news if n.get("status") == "queued"), "videos": videos,
        "clippable": __import__("clipper").clippable(),
    }


# ---- executors: (slug, cfg, now) ----
def _meta(slug: str) -> tuple[Path, dict]:
    p = config.OUT / slug / "meta.json"
    return p, json.loads(p.read_text())


def visually_ok(slug: str) -> bool:
    """Before the reviewer's pass becomes an approval, a vision model reads sampled frames. A clearly bad picture set (two or more WRONG pictures: another place,
    person or period than the narration names; atmospheric pictures do not count) or a garbled caption sends the video to the fixer, then to the owner. A reading that cannot run never blocks: the rule checks already passed."""
    import videoinspect

    try:
        rows = videoinspect.visual_review(config.OUT / slug)
    except Exception:
        return True
    pics = next((r for r in rows if r["name"] == "pictures_fit_story"), None)
    p0, m0 = _meta(slug)
    m0["visual_check"] = {"at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "ok": True, "rows": [r["name"] + ": " + r["detail"][:120] for r in rows if not r["ok"]]}
    p0.write_text(json.dumps(m0, indent=2))
    caps = next((r for r in rows if r["name"] == "captions_readable"), None)
    n_pics = (pics["detail"].count(" s: ") if pics and not pics["ok"] else 0)
    garbled = bool(caps and not caps["ok"] and re.search(r"garbl|gibberish|stray|nonsens", caps["detail"], re.I))
    if n_pics >= WRONG_PICTURES or garbled:
        p, meta = _meta(slug)
        review = meta.setdefault("review", {"checks": []})
        review["checks"].append({"name": "visual_review", "ok": False, "severity": "human", "detail": " | ".join(r["detail"] for r in rows if not r["ok"])[:400]})
        review["verdict"] = "needs_human"
        meta["approved"] = False
        meta["visual_check"] = {**meta.get("visual_check", {}), "ok": False}
        p.write_text(json.dumps(meta, indent=2))
        return False
    return True


def _approve(slug: str) -> None:
    if visually_ok(slug):
        p, meta = _meta(slug)
        meta.update(approved=True, approved_by="reviewer-agent")
        p.write_text(json.dumps(meta, indent=2))


def do_review(slug, cfg, now):
    import reviewer

    result = reviewer.review(config.OUT / slug)
    if result["verdict"] == "pass" and cfg["auto_approve"]:
        _approve(slug)


def do_approve(slug, cfg, now):
    _approve(slug)


def do_fix(slug, cfg, now):
    import fixer

    out = fixer.fix(slug, now=now)
    if out.get("verdict") == "pass" and cfg["auto_approve"]:
        _approve(slug)


def do_schedule(slug, cfg, now):
    p, meta = _meta(slug)
    fmt = meta.get("format", "short")
    taken = []
    for m in config.OUT.glob("*/meta.json"):  # only same-format videos block a slot; a Short may publish near a documentary
        d = json.loads(m.read_text())
        if m.parent.name != slug and d.get("format", "short") == fmt and d.get("publish_at") and not d.get("hold"):
            taken.append(_parse(d["publish_at"]))
    slots = cfg["short_slots"] if fmt == "short" else cfg["slots"]
    meta["publish_at"] = scheduler.to_rfc3339(scheduler.next_slot(now, slots, taken, cfg["review_window_hours"]))
    p.write_text(json.dumps(meta, indent=2))


def do_upload(slug, cfg, now):
    import upload

    _, meta = _meta(slug)
    upload.upload(config.OUT / slug, "private", meta["publish_at"])


def do_ideas(slug, cfg, now):
    import run

    run.cmd_research(3)


def finish_video(folder: Path) -> None:
    """Thumbnails, then search-based metadata, then the best title option. The reviewer sees the finished package."""
    import seo
    import thumbnail

    p = folder / "meta.json"
    meta = json.loads(p.read_text())
    if meta.get("format") == "doc":  # Shorts use a frame YouTube picks; custom thumbnails are for long videos
        thumbnail.make(folder)
    seo.make(folder)
    meta = json.loads(p.read_text())
    import fixer

    others = fixer.other_titles(folder)
    titles = [t for t in (meta.get("seo") or {}).get("titles", []) if not fixer._too_similar(t, others)] or (meta.get("seo") or {}).get("titles") or []
    if titles:
        meta["title"] = titles[0]
    import seo

    meta["tags"] = fixer.clean_tags(meta)
    meta["title"] = seo.polish_title(meta["title"])
    p.write_text(json.dumps(meta, indent=2))


def do_make(slug, cfg, now):
    import run

    finish_video(run.cmd_doc())


def do_make_short(slug, cfg, now):
    import run

    finish_video(run.cmd_make())


def do_make_clip(slug, cfg, now):
    import clipper

    folder = clipper.make_next()
    if folder:
        finish_video(folder)


def do_make_news(slug, cfg, now):
    import newswatch

    newswatch.make_next_news_video()


EXECUTORS = {"review": do_review, "approve": do_approve, "fix": do_fix, "schedule": do_schedule, "upload": do_upload,
             "ideas": do_ideas, "make": do_make, "make_short": do_make_short, "make_clip": do_make_clip, "make_news": do_make_news}


def _log(msg: str) -> None:
    LOG.parent.mkdir(exist_ok=True)
    if LOG.exists() and LOG.stat().st_size > 2_000_000:  # one old copy is enough
        LOG.replace(LOG.with_name(LOG.name + ".1"))
    with LOG.open("a") as f:
        f.write(f"{dt.datetime.now().isoformat(timespec='seconds')} {msg}\n")


def tick(now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    lock = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return {"skipped": "locked"}
    try:
        cfg = load_config()
        actions, errors, heavy = [], [], False
        for a in plan_actions(build_state(now, cfg), cfg, now):
            if a["do"] in ("make", "make_news", "fix"):
                if heavy:
                    continue
                heavy = True
            try:
                EXECUTORS[a["do"]](a["slug"], cfg, now)
                actions.append(a)
                _log(f"ok {a['do']} {a['slug'] or ''}")
            except (Exception, SystemExit) as e:  # one failing step must not stop the rest
                errors.append(f"{a['do']} {a['slug'] or ''}: {e}".strip())
                _log(f"FAIL {errors[-1]}")
                if a["slug"] and counts_as_failure(e):
                    p, meta = _meta(a["slug"])
                    meta["autopilot_fails"] = meta.get("autopilot_fails", 0) + 1
                    p.write_text(json.dumps(meta, indent=2))
        result = {"at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "enabled": cfg["enabled"], "actions": actions, "errors": errors}
        STATE_FILE.write_text(json.dumps(result, indent=2))
        return result
    finally:
        lock.close()


def is_running() -> bool:
    """True while a tick holds the lock (the dashboard waits for it before starting its own jobs)."""
    LOCK_FILE.touch(exist_ok=True)
    with open(LOCK_FILE) as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return False
        except BlockingIOError:
            return True


def status() -> dict:
    last = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else None
    return {"config": load_config(), "last_tick": last, "running": is_running()}
