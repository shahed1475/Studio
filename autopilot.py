"""Autopilot: decides what to do next (plan_actions) and does it (tick). Run every 30 minutes by a systemd timer."""
import datetime as dt
import fcntl
import json
import re
import os
from pathlib import Path

import agents
import config
import llm
import planner
import playbook
import prelaunch
import channelprofile
import records
import scheduler

CONFIG_FILE = config.ROOT / "autopilot.json"
STATE_FILE = config.ROOT / "autopilot_state.json"
LOCK_FILE = config.ROOT / "autopilot.lock"
MAX_VIDEO_COST = {"doc": 2.5, "short": 0.7}  # dollars one video may cost in all (script, pictures, reviews, repairs) before Autopilot stops repairing it and asks the owner
MIN_CREDIT_TO_MAKE = 1.5  # dollars on the OpenRouter account below which no new video is started: a documentary costs about $1 and a stopped render wastes it
NEWS_QUEUE = config.ROOT / "news_queue.json"
LOG = config.ROOT / "logs" / "autopilot.log"
JOB_FILE = config.ROOT / "job.pid"   # written by the dashboard while one of its jobs runs

DEFAULTS = {
    "enabled": False,            # master switch, off until the user turns it on
    "governor": {"enabled": True, "base": {}},  # weekly caps per format from YouTube's template-content rule (governor.py); base {} = 3 documentaries and 7 Shorts a week, tightened by repetition
    "pace_guard": True,          # read the Risks card's 'inauthentic content' level: at watch, no new Shorts; at act, nothing new is made or scheduled until it falls
    "max_videos_per_week": 0,    # 0 = no limit. Otherwise no new video is made for a slot that would be the Nth video out or scheduled in the 7 days before it
    "auto_approve": True,        # reviewer-agent "pass" counts as approval
    "uploads_per_day": 1,
    "review_window_hours": 24,   # time between a pass and the public slot, for the human veto
    "upload_lead_hours": 2,      # upload this long before the slot (private, publishAt set)
    "prepare_hours": 12,         # a video is started this many hours before its 24-hour review window opens (36 hours before the slot), never earlier
    "min_queue": 3,
    "max_waiting": 2,            # finished videos not yet uploaded
    "slots": scheduler.SLOTS_DEFAULT,
    "make_videos": True,         # off = repair, review and upload what exists, but start no new video (and no new research)
    "news_videos": True,         # build drafts from the weekly YouTube news digest (always need a human)
    "shorts": True,              # also make YouTube Shorts (vertical, under a minute)
    "shorts_per_day": 1,
    "max_waiting_shorts": 3,     # finished Shorts not yet uploaded
    "short_slots": scheduler.SHORT_SLOTS_DEFAULT,
    "second_sources": {          # two pages beyond Wikipedia and one original element per documentary (secondsources.py): OFF until the owner tops up; about two small model calls a video
        "enabled": False, "min_credit": 3.0,
    },
    "house_style": {             # 3D animated-film look plus a few moving clips for NEW videos, only while the OpenRouter credit is at least min_credit (about $3 for a documentary)
        "enabled": False, "min_credit": 8.0,
        "doc": {"clips": 4, "budget": 1.5},
        "short": {"clips": 1, "budget": 0.5},
    },
}
MAX_FAILS = 3
POLISH_MIN_LEAD = dt.timedelta(hours=30)  # a video this close to its slot is not edited: there is no time to make it again and check it


def auto_approves(cfg: dict) -> bool:
    """The reviewer's pass becomes an approval only when the studio allows it and its profile does not demand a person (profile.json)."""
    return bool(cfg["auto_approve"]) and not channelprofile.human_approval()


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        cfg.update({k: v for k, v in json.loads(CONFIG_FILE.read_text()).items() if k in DEFAULTS})
    return cfg


def governed(cfg: dict, now: dt.datetime) -> dict:
    """The config plus this week's caps per format (`_caps`), read from the same risk signals as the Risks card. A reading that fails, or governor.enabled
    false, gives the config unchanged: the studio works as before."""
    g = cfg.get("governor") or {}
    if not g.get("enabled", True):
        return cfg
    try:
        import governor
        import risk

        caps = governor.caps(risk.videos(config.OUT), now, g.get("base"))
        governor.record(caps, now)
        return {**cfg, "_caps": caps}
    except Exception:
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
FINISHING = ("review", "approve", "prelaunch", "schedule", "upload")
MAX_ROUNDS = 8  # videos looked at in one tick, when each repair is quick
DOC_COST_ESTIMATE = 1.3   # dollars: a documentary cost $1.04 to $1.10 to make; the margin covers one repair
SHORT_COST_ESTIMATE = 0.3  # a Short or a clip cost $0.01 to $0.14


def can_afford(kind: str, cap_left: float | None) -> bool:
    """Is there enough of the day's spending cap left to finish this kind of video? Starting one that cannot be finished wastes what it spent
    (its script is saved and resumed after midnight UTC, but its voice and pictures are not). An unknown cap never blocks."""
    return cap_left is None or cap_left >= (DOC_COST_ESTIMATE if kind == "doc" else SHORT_COST_ESTIMATE)


MAX_STUCK = 3  # stop making a kind of video while this many of it sit failed or waiting for a human


def failing_names(meta: dict) -> list[str]:
    return [c["name"] for c in (meta.get("review") or {}).get("checks", []) if not c["ok"] and c["severity"] in ("block", "human")]


def focus_rank(v: dict) -> tuple:
    """Which broken video to work on next: documentaries before Shorts, one already being repaired before an untouched one, then the one with
    the fewest open problems, then by name so the choice never flips between ticks."""
    return (0 if (v.get("format") or "doc") == "doc" else 1, 0 if v.get("fix_attempts", 0) > 0 else 1, v.get("blocking", 9), v["slug"])


NEW_WORK = ("make", "make_short", "make_clip", "make_news")


def pace_filter(acts: list[dict], state: dict, cfg: dict) -> list[dict]:
    """Autopilot reads YouTube's template-content risk (the Risks card row) before it makes or schedules anything new.
    Many videos in the 7-day window (watch or act): no new Short is made or scheduled; the documentary schedule goes on as it is (at one documentary and one
    Short a day the count sits near the line all the time, so holding documentaries too would stop the channel). Repetition signals (near-identical openings,
    one shared structure): nothing new at all until they clear. Videos already scheduled or uploaded, reviews, repairs, final checks and uploads are never held back."""
    level = state.get("platform_level")
    if not cfg.get("pace_guard", True) or level not in ("watch", "act"):
        return acts
    fmt = {v["slug"]: (v.get("format") or "doc") for v in state.get("videos", [])}
    keep, held = [], []
    for a in acts:
        shorts = a["do"] in ("make_short", "make_clip") or (a["do"] == "schedule" and fmt.get(a["slug"]) == "short")
        new = a["do"] in NEW_WORK or a["do"] == "schedule"
        (held if shorts or (state.get("platform_content_act") and new) else keep).append(a)
    if held:
        _note_pace(state, held)
    return keep


def _note_pace(state: dict, held: list[dict]) -> None:
    """One plain notice a day in the activity feed. Never raises."""
    try:
        import agentlog

        everything = bool(state.get("platform_content_act"))
        title = f"Autopilot is holding back new {'videos' if everything else 'Shorts'} ({dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d')})"
        if any(e.get("title") == title for e in agentlog.recent(60)):
            return
        agentlog.event("info", title, f"{state.get('platform_why', '')} Held: {', '.join(sorted({a['do'] for a in held}))}. "
                       + ("Repeated openings or one shared structure were found, so nothing new is made until that clears. " if everything else
                          "Documentaries go on as scheduled. ") + "Shorts continue by themselves when the count of videos in the 7-day window falls below 10; "
                       "switch this off with pace_guard in autopilot.json.")
    except Exception:
        pass


def plan_actions(state: dict, cfg: dict, now: dt.datetime, skip=()) -> list[dict]:
    """skip: videos already worked on in this tick."""
    if not cfg["enabled"] or state["busy"]:
        return []
    acts = []
    total = state["uploads_today"]
    by_fmt = dict(state.get("uploads_by_format") or {"doc": state["uploads_today"]})
    lead = dt.timedelta(hours=cfg["upload_lead_hours"])
    stuck = {"doc": 0, "short": 0}  # reviewed, repaired as far as the fixer can, and still not good enough: they wait for the owner
    polishable = []                 # passed videos with a facts warning, edited before they are approved: only the soonest is worked on per tick
    fixable = []                    # broken videos that still have repair tries left: one of them is worked on at a time, and nothing new is made meanwhile
    for v in state["videos"]:
        if v["video_id"] or v["hold"] or v["fails"] >= MAX_FAILS:
            continue
        fmt = v.get("format") or "doc"
        by_you = v["approved"] and v.get("approved_by") == "you"
        eligible = (v["verdict"] == "pass" and v["source"] != "news") or (v["verdict"] == "needs_human" and by_you)
        limit = (cfg.get("max_video_cost_usd") or MAX_VIDEO_COST).get(fmt, MAX_VIDEO_COST.get(fmt, 2.5))
        over = float(v.get("cost", 0.0)) >= limit
        if over and v["verdict"] in ("fail", "needs_human") and not eligible and not by_you and not v.get("cost_alerted"):
            acts.append({"do": "cost_stop", "slug": v["slug"]})
        repairable = v["verdict"] in ("fail", "needs_human") and not eligible and not by_you and v["source"] != "news" \
            and v.get("fix_attempts", 0) < v.get("fix_limit", 2) and not (v.get("gave_up") and v.get("fix_limit", 2) <= 2) and not over
        if v["verdict"] in ("fail", "needs_human") and not eligible and not by_you and not repairable:
            stuck[fmt] += 1
        if v["verdict"] is None:
            acts.append({"do": "review", "slug": v["slug"]})
        elif repairable:
            fixable.append(v)
        elif eligible:
            pub = _parse(v["publish_at"]) if v["publish_at"] else None
            if v.get("polish_wanted") and not over and state.get("spend_ok", True) and (pub is None or pub - now > POLISH_MIN_LEAD):
                polishable.append((pub or now + dt.timedelta(days=3650), v["slug"]))
                continue  # edited first: approving or scheduling it now would be undone by the edit
            if v.get("facts_open", v.get("polish_wanted")):
                continue  # the owner wants nothing with an open invented-facts warning approved, scheduled or uploaded: it waits for a polish, or for the owner
            if auto_approves(cfg) and not v["approved"] and v["verdict"] == "pass":
                acts.append({"do": "approve", "slug": v["slug"]})  # reviewed earlier (by hand or by the fixer): the reviewer's pass counts
            cap = cfg["shorts_per_day"] if fmt == "short" else cfg["uploads_per_day"]
            if pub is None or pub <= now + dt.timedelta(minutes=10):
                acts.append({"do": "schedule", "slug": v["slug"]})
            elif v["approved"] and not v.get("prelaunch_ok") and pub - now <= dt.timedelta(hours=cfg["review_window_hours"] + prelaunch.WINDOW_EXTRA_HOURS):
                acts.append({"do": "prelaunch", "slug": v["slug"]})  # the final check, when the review window opens; the upload waits for it
            elif (v["approved"] and state["connected"] and by_fmt.get(fmt, 0) < cap and v.get("prelaunch_ok")
                  and total < config.MAX_UPLOADS_PER_DAY and pub - lead <= now):
                acts.append({"do": "upload", "slug": v["slug"]})
                by_fmt[fmt] = by_fmt.get(fmt, 0) + 1
                total += 1
    if polishable:
        acts.append({"do": "polish", "slug": min(polishable)[1]})
    targets = planner.repair_targets(cfg, state["videos"], now)  # only drafts that take a slot which is due are worked on; the rest stay parked
    fixable = [v for v in fixable if v["slug"] in targets]
    todo = [v for v in fixable if v["slug"] not in skip]
    if todo and state.get("spend_ok", True):  # the fixer agent repairs what it can, then the reviewer decides again: one video at a time. Not when the day's cap is spent: a video's two tries are not used on weak free models
        acts.append({"do": "fix", "slug": min(todo, key=focus_rank)["slug"]})
    credit = state.get("credit_left")
    can_pay = (credit is None or credit >= MIN_CREDIT_TO_MAKE) and not state.get("storage_full")  # a balance that cannot be read does not block work; a known low one does
    if can_pay and not state["busy"] and cfg["make_videos"] and not fixable:
        need = planner.needs(cfg, state["videos"], now)  # only the slots no video covers need a new one
        if state["queue_len"] < cfg["min_queue"]:
            acts.append({"do": "ideas", "slug": None})
        cap_left = state.get("cap_left")
        if cfg["shorts"] and need["short"] > 0 and stuck["short"] < MAX_STUCK and can_afford("short", cap_left):
            if state.get("clippable", 0) > 0:  # cut from our own documentaries first: no script to write, cheapest
                acts.append({"do": "make_clip", "slug": None})
            elif state["queue_len"] > 0:
                acts.append({"do": "make_short", "slug": None})
        if need["doc"] > 0 and stuck["doc"] < MAX_STUCK and can_afford("doc", cap_left):
            if cfg["news_videos"] and state["news_pending"] > 0:
                acts.append({"do": "make_news", "slug": None})
            elif state["queue_len"] > 0:
                acts.append({"do": "make", "slug": None})
    return pace_filter(acts, state, cfg)


def _storage_full() -> bool:
    import tenantmode

    return tenantmode.is_tenant() and tenantmode.quota_state()["state"] == "full"


def _workable(d: dict, cfg: dict, slug: str) -> bool:
    """Can Autopilot still do something to this video (review it, repair it, polish it)? False once its tries or its money are used up."""
    import fixer

    checks = (d.get("review") or {}).get("checks", [])
    if d.get("hold") or d.get("video_id") or d.get("approved_by") == "you":
        return False
    review = d.get("review") or {}
    if not review.get("verdict") or any(c["name"] == "llm_review" and not c["ok"] for c in checks):
        return True  # not reviewed yet
    fmt = d.get("format", "short")
    if llm.video_cost(slug) >= (cfg.get("max_video_cost_usd") or MAX_VIDEO_COST).get(fmt, MAX_VIDEO_COST.get(fmt, 2.5)):
        return False
    if review.get("verdict") in ("fail", "needs_human"):
        return d.get("fix_attempts", 0) < fixer.attempt_limit(checks) and not (d.get("fix_gave_up") and fixer.attempt_limit(checks) <= 2)
    return fixer.polish_rounds(d) < fixer.POLISH_ROUNDS and bool(fixer.watch_problems(checks))


def build_state(now: dt.datetime, cfg: dict) -> dict:
    import fixer
    import llm
    import upload

    try:
        cap = cfg.get("daily_budget_usd", llm.load_config()["daily_budget_usd"])
        spend_ok = llm.spent_today(now) < cap
        cap_left = cap - llm.spent_today(now)
    except Exception:
        spend_ok, cap_left = True, None
    try:
        import risk

        credit_left = risk.credit_left(llm.api_key()) if llm.api_key() else None
    except Exception:
        credit_left = None

    videos = []
    for m in sorted(config.OUT.glob("*/meta.json")):
        d = json.loads(m.read_text())
        videos.append({
            "slug": m.parent.name, "format": d.get("format", "short"), "source": d.get("source"), "approved": bool(d.get("approved")),
            "verdict": None if any(c["name"] == "llm_review" and not c["ok"] for c in (d.get("review") or {}).get("checks", [])) else (d.get("review") or {}).get("verdict"),
            "hold": bool(d.get("hold")),
            "approved_by": d.get("approved_by"), "fix_attempts": d.get("fix_attempts", 0), "gave_up": bool(d.get("fix_gave_up")), "cost": llm.video_cost(m.parent.name), "cost_alerted": bool(d.get("cost_alerted")), "fix_limit": fixer.attempt_limit((d.get("review") or {}).get("checks", [])),
            "video_id": d.get("video_id"), "publish_at": d.get("publish_at") or ((d.get("upload_check") or {}).get("publishAt") if d.get("video_id") and not d.get("taken_back") and not d.get("hold") else None),
            "fails": d.get("autopilot_fails", 0),
            "prelaunch_ok": bool((d.get("prelaunch") or {}).get("ok")),
            "facts_open": d.get("approved_by") != "you" and bool(fixer.watch_problems((d.get("review") or {}).get("checks", []))),
            "polish_wanted": fixer.polish_rounds(d) < fixer.POLISH_ROUNDS and d.get("approved_by") != "you" and bool(fixer.watch_problems((d.get("review") or {}).get("checks", []))),
            "workable": _workable(d, cfg, m.parent.name),
            "blocking": len(failing_names(d)), "problems": failing_names(d), "title": d.get("title", ""),
        })
    by_fmt: dict = {}
    day = now.astimezone(dt.timezone.utc).strftime("%Y-%m-%d")
    for m in config.OUT.glob("*/meta.json"):
        d = json.loads(m.read_text())
        if str(d.get("uploaded_at", "")).startswith(day) and not d.get("hold"):  # a held upload will not go public: it does not use up the day's pace
            by_fmt[d.get("format", "short")] = by_fmt.get(d.get("format", "short"), 0) + 1
    queue = json.loads(config.TOPICS_FILE.read_text()) if config.TOPICS_FILE.exists() else []
    news = json.loads(NEWS_QUEUE.read_text()) if NEWS_QUEUE.exists() else []
    try:
        import risk

        platform = risk.pattern(risk.videos(config.OUT), now)  # the same reading the Risks card shows for YouTube's template-content rule
        platform_level, platform_why, platform_content = platform["level"], platform["evidence"], bool(platform.get("content_act"))
    except Exception:  # a risk that cannot be read does not stop the studio: it works as before
        platform_level, platform_why, platform_content = "ok", "", False
    return {
        "platform_level": platform_level, "platform_why": platform_why, "platform_content_act": platform_content,
        "queue_len": len(queue), "connected": upload.SECRET.exists() and upload.TOKEN.exists(), "busy": dashboard_busy(),
        "uploads_today": upload.uploads_today(config.OUT, now), "uploads_by_format": by_fmt,
        "news_pending": sum(1 for n in news if n.get("status") == "queued"), "videos": videos,
        "clippable": __import__("clipper").clippable(), "spend_ok": spend_ok, "cap_left": cap_left, "credit_left": credit_left, "storage_full": _storage_full(),
    }


# ---- executors: (slug, cfg, now) ----
def _meta(slug: str) -> tuple[Path, dict]:
    p = config.OUT / slug / "meta.json"
    return p, json.loads(p.read_text())


def read_pictures(slug: str) -> dict | None:
    """A vision model reads sampled frames and the reading is stored in meta (visual_check). bad = two or more WRONG pictures (another place, person or period
    than the narration names; atmospheric pictures do not count) or a garbled caption. None when the reading cannot run: that never blocks anything."""
    import videoinspect

    try:
        rows = videoinspect.visual_review(config.OUT / slug)
    except Exception:
        return None
    pics = next((r for r in rows if r["name"] == "pictures_fit_story"), None)
    caps = next((r for r in rows if r["name"] == "captions_readable"), None)
    n_pics = (pics["detail"].count(" s: ") if pics and not pics["ok"] else 0)
    garbled = bool(caps and not caps["ok"] and re.search(r"garbl|gibberish|stray|nonsens", caps["detail"], re.I))
    bad = n_pics >= WRONG_PICTURES or garbled
    records.merge(config.OUT / slug, {"visual_check": {"at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "ok": not bad, "rows": [r["name"] + ": " + r["detail"][:120] for r in rows if not r["ok"]],
                                                      "wrong_at": (pics or {}).get("times", []) if pics and not pics["ok"] else []}})
    return {"bad": bad, "rows": rows}


def visually_ok(slug: str) -> bool:
    """Before the reviewer's pass becomes an approval, the pictures are read (read_pictures). A clearly bad set sends the video to the fixer, then to the owner."""
    seen = read_pictures(slug)
    if seen is None or not seen["bad"]:
        return True
    def hold_for_human(meta):
        review = meta.setdefault("review", {"checks": []})
        review["checks"].append({"name": "visual_review", "ok": False, "severity": "human", "detail": " | ".join(r["detail"] for r in seen["rows"] if not r["ok"])[:400]})
        review["verdict"] = "needs_human"
        meta["approved"] = False

    records.update(config.OUT / slug, hold_for_human)
    return False


def _approve(slug: str) -> None:
    if visually_ok(slug):
        records.merge(config.OUT / slug, {"approved": True, "approved_by": "reviewer-agent"})


def do_review(slug, cfg, now):
    import reviewer

    result = reviewer.review(config.OUT / slug)
    if result["verdict"] == "pass" and auto_approves(cfg):
        _approve(slug)


def do_polish(slug, cfg, now):
    """Repair the invented-facts warning of a passed video once, then let the normal flow approve and schedule it. A failure is recorded on the video
    (so it is never tried again and never held up) and not raised."""
    import fixer

    try:
        out = fixer.polish(slug, now=now)
    except (Exception, SystemExit) as e:
        records.merge(config.OUT / slug, {"polish_done": {"at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "result": f"stopped by an error: {e}"[:300]}})
        return {"skipped": "error"}
    if isinstance(out, dict) and not out.get("skipped"):
        try:  # self-training from daily work: did the polish clear the facts warning?
            import lessons

            lessons.record("fixer", "invented facts warning after a passed review", "polish: rewrite the named lines from the source article",
                           out.get("verdict") == "pass" and not out.get("held"), now)
        except Exception:
            pass
    if out.get("verdict") == "pass" and auto_approves(cfg):
        _approve(slug)
    return out


def do_approve(slug, cfg, now):
    _approve(slug)


def learn_from_fix(slug: str, checks: list[str], out: dict, now) -> None:
    """Self-training from daily work: what the fixer did for each failing check, and whether the video then passed. Never stops the repair."""
    import lessons

    try:
        did = [re.sub(r"[:(].*$", "", str(f)).strip()[:60] for f in (out.get("fixed") or [])] or ["repair pass without a change"]
        worked = out.get("verdict") == "pass"
        for name in checks[:4]:
            for step in did[:3]:
                lessons.record("fixer", f"check {name} failed", step, worked, now)
    except Exception:  # a lesson that cannot be written is lost, not a failed repair
        pass


def do_fix(slug, cfg, now):
    import fixer

    try:
        checks = [c["name"] for c in (json.loads((config.OUT / slug / "meta.json").read_text()).get("review") or {}).get("checks", []) if not c["ok"] and c["severity"] in ("block", "human")]
    except (OSError, ValueError):
        checks = []
    out = fixer.fix(slug, now=now)
    if isinstance(out, dict) and not out.get("skipped"):
        learn_from_fix(slug, checks, out, now)
    if out.get("verdict") == "pass" and auto_approves(cfg):
        _approve(slug)
    return out


def do_prelaunch(slug, cfg, now):
    """The final check a day before the slot. A video the reviewer approved that fails is pulled back to a draft so the fixer can repair it while there is time."""
    import agentlog
    import prelaunch

    _, mine = _meta(slug)
    if mine.get("approved_by") == "you" and not (mine.get("visual_check") or {}).get("ok"):  # only reviewer-approved videos were ever picture-checked: read yours too, and tell you
        seen = read_pictures(slug)
        if seen and seen["bad"]:
            agentlog.event("error", f"Pictures may not fit: {mine.get('title', slug)}", "; ".join(r["detail"] for r in seen["rows"] if not r["ok"])[:300] + " You approved it, so it stays scheduled until you decide.", notify=True, now=now)
    res = prelaunch.check(slug, now)
    seen_by = {}

    def apply(meta):
        meta["prelaunch"] = {"at": res["at"], "ok": res["ok"], "problems": res["problems"]}
        seen_by["title"], seen_by["approved_by"] = meta.get("title", slug), meta.get("approved_by")
        if not res["ok"] and meta.get("approved_by") != "you":  # your approval is never withdrawn by the agent
            review = meta.setdefault("review", {"checks": []})
            review["checks"] = [c for c in review.get("checks", []) if c["name"] != "prelaunch"] + [
                {"name": "prelaunch", "ok": False, "severity": "block", "detail": "; ".join(res["problems"])[:400]}]
            review["verdict"] = "fail"
            meta["approved"] = False
            meta.pop("approved_by", None)
            meta.pop("publish_at", None)
            meta["fix_attempts"] = 0
            meta.pop("fix_gave_up", None)

    records.update(config.OUT / slug, apply)
    if not res["ok"]:
        title = seen_by["title"]
        if seen_by["approved_by"] == "you":
            agentlog.event("error", f"Final check found a problem: {title}", "; ".join(res["problems"][:2]) + " You approved it, so it stays scheduled until you decide.", notify=True, now=now)
        else:
            agentlog.event("error", f"Pulled back for repair: {title}", "The final check found: " + "; ".join(res["problems"][:2]) + ". Autopilot repairs it before its slot.", notify=True, now=now)


def _twin(slug: str) -> dict | None:
    """An earlier video of the same format that already tells this story, or None. A catalogue that cannot be read lets the video through."""
    try:
        import duplicates

        return duplicates.taken_by(slug)
    except Exception:
        return None


def hold_duplicate(slug: str, twin: dict, now) -> None:
    """The later of two videos on one story waits: on hold (visible, and reversible in the dashboard), the owner told once. Its slot is free for another story."""
    _, meta = _meta(slug)
    why = f"the same story as '{twin['title'][:70]}' ({twin['slug']}): a second video on one story is held back; release it in the dashboard if you want it anyway"
    try:
        records.merge(config.OUT / slug, {"hold": True, "hold_reason": why})
    except OSError:
        pass  # not saved (disk full): the owner is still told below, and the next pass finds the same duplicate and tries again
    try:
        import agentbus
        import agentlog

        agentbus.post("duplicate_subject", "autopilot", "owner", slug, reason=f"Held a duplicate: {meta.get('title', slug)[:70]}", evidence=why, now=now)
        agentlog.event("found", f"Held a duplicate: {meta.get('title', slug)[:60]}", f"It is {why}.", now=now)
    except Exception:
        pass


def do_schedule(slug, cfg, now):
    import policyclass

    if policyclass.hold_active():
        return {"skipped": "policy hold: a YouTube rule page changed and the owner has not released it"}
    p, meta = _meta(slug)
    review = meta.get("review") or {}
    if meta.get("hold") or not (review.get("verdict") == "pass" or meta.get("approved_by") == "you"):
        return {"skipped": "not eligible"}  # the approval step may have just sent it back (the pictures were read): a video that needs repair must not take a slot
    twin = _twin(slug)
    if twin:
        hold_duplicate(slug, twin, now)
        return {"skipped": "duplicate"}
    fmt = meta.get("format", "short")
    taken, metas = [], []
    for m in config.OUT.glob("*/meta.json"):  # only same-format videos block a slot; a Short may publish near a documentary
        d = json.loads(m.read_text())
        metas.append(d) if m.parent.name != slug else None
        if m.parent.name != slug and d.get("format", "short") == fmt and d.get("publish_at") and not d.get("hold"):
            taken.append(_parse(d["publish_at"]))
    slots = cfg["short_slots"] if fmt == "short" else cfg["slots"]
    import governor

    for _ in range(40):  # the next free slot that stays within the weekly cap (YouTube's template-content rule); none within three weeks: it waits
        try:
            at = scheduler.next_slot(now, slots, taken, cfg["review_window_hours"])
        except ValueError:
            return {"skipped": "no slot within the weekly pace limit"}
        if governor.allowed(metas, fmt, at, cfg.get("_caps")):
            records.merge(config.OUT / slug, {"publish_at": scheduler.to_rfc3339(at)})
            return None
        taken.append(at)
    return {"skipped": "no slot within the weekly pace limit"}


def do_upload(slug, cfg, now):
    import policyclass
    import upload

    if policyclass.hold_active():
        return {"skipped": "policy hold: a YouTube rule page changed and the owner has not released it"}

    _, meta = _meta(slug)
    twin = _twin(slug)
    if twin:
        hold_duplicate(slug, twin, now)  # caught at the last moment: never send a second video on one story
        return {"skipped": "duplicate"}
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
    seo.make(folder)  # research first (search phrase, rivals, autocomplete), then the title; the thumbnail text is written against the final title
    meta = json.loads(p.read_text())
    import fixer

    others = fixer.other_titles(folder)
    titles = [t for t in (meta.get("seo") or {}).get("titles", []) if not fixer._too_similar(t, others)] or (meta.get("seo") or {}).get("titles") or []
    if titles:
        import packaging

        meta["title"] = packaging.rank_titles(titles, (meta.get("seo") or {}).get("core", ""), others)[0]  # the best-scoring option, not just the first
    import seo

    tags = fixer.clean_tags(meta)
    core = (meta.get("seo") or {}).get("core", "")
    records.merge(folder, {"title": seo.ensure_title_front(meta["title"], core) if core else seo.polish_title(meta["title"]), "tags": tags})
    if meta.get("format") == "doc":  # Shorts use a frame YouTube picks; custom thumbnails are for long videos
        thumbnail.make(folder)


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


def do_cost_stop(slug, cfg, now):
    """A video that has used up its money limit is no longer repaired: say so once, with the real number."""
    import agentlog

    _, meta = _meta(slug)
    records.merge(config.OUT / slug, {"cost_alerted": True})
    agentlog.event("error", f"Stopped spending on: {meta.get('title', slug)}", f"It has cost ${llm.video_cost(slug):.2f} so far (limit for a "
                   f"{'documentary' if meta.get('format') == 'doc' else 'Short'}: ${(cfg.get('max_video_cost_usd') or MAX_VIDEO_COST).get(meta.get('format', 'short'), 2.5):.2f}). "
                   "It waits for you: approve it as it is, ask for one more try, or set it aside.", notify=True, now=now)


EXECUTORS = {"cost_stop": do_cost_stop, "prelaunch": do_prelaunch, "review": do_review, "approve": do_approve, "fix": do_fix, "polish": do_polish, "schedule": do_schedule, "upload": do_upload,
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
        cfg = governed(load_config(), now)
        actions, errors, seen, worked = [], [], set(), set()
        for _ in range(MAX_ROUNDS):  # a quick repair (a new title, a set-aside) lets the next video start in the same tick; a re-render ends the tick
            stop, progressed = False, False
            for a in plan_actions(build_state(now, cfg), cfg, now, skip=worked):
                key = (a["do"], a["slug"])
                if key in seen:
                    continue
                seen.add(key)
                progressed = True
                try:
                    with llm.cost_scope(a["slug"]), playbook.acting_as(agents.for_action(a["do"])):  # what a review, repair or picture check spends is charged to its video
                        res = EXECUTORS[a["do"]](a["slug"], cfg, now)
                    actions.append(a)
                    _log(f"ok {a['do']} {a['slug'] or ''}")
                    if a["do"] in ("fix", "polish"):
                        worked.add(a["slug"])
                        stop = stop or bool(isinstance(res, dict) and res.get("rerendered"))
                    elif a["do"] in ("make", "make_news", "make_short", "make_clip"):
                        stop = True
                except (Exception, SystemExit) as e:  # one failing step must not stop the rest
                    errors.append(f"{a['do']} {a['slug'] or ''}: {e}".strip())
                    _log(f"FAIL {errors[-1]}")
                    if a["do"] in ("fix", "polish"):
                        worked.add(a["slug"])
                    if a["slug"] and counts_as_failure(e):
                        records.update(config.OUT / a["slug"], lambda d: d.__setitem__("autopilot_fails", d.get("autopilot_fails", 0) + 1))
            if stop or not progressed:
                break
        for a in plan_actions(build_state(now, cfg), cfg, now, skip=worked):  # the finishing pass: whatever the repairs just approved is scheduled and uploaded now, not 30 minutes later
            key = (a["do"], a["slug"])
            if a["do"] not in FINISHING or key in seen:
                continue
            seen.add(key)
            try:
                with playbook.acting_as(agents.for_action(a["do"])):
                    EXECUTORS[a["do"]](a["slug"], cfg, now)
                actions.append(a)
                _log(f"ok {a['do']} {a['slug'] or ''}")
            except (Exception, SystemExit) as e:
                errors.append(f"{a['do']} {a['slug'] or ''}: {e}".strip())
                _log(f"FAIL {errors[-1]}")
        try:
            planner.sync_ready_folder(build_state(now, cfg)["videos"])  # ready/ lists what is going out, named by post time
        except OSError:
            pass
        result = {"at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "enabled": cfg["enabled"], "actions": actions, "errors": errors}
        STATE_FILE.write_text(json.dumps(result, indent=2))
        return result
    finally:
        lock.close()


class Busy(RuntimeError):
    """Autopilot (or another manual job) holds the lock."""


class exclusive:
    """Hold the Autopilot lock for a manual job (a repair run by hand), so the worker neither reviews nor re-renders the same folder meanwhile and the
    dashboard shows that a pass is running. Raises Busy at once when the lock is taken."""

    def __enter__(self):
        LOCK_FILE.touch(exist_ok=True)
        self.f = open(LOCK_FILE)
        try:
            fcntl.flock(self.f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.f.close()
            raise Busy("Autopilot is working right now: try again when its pass ends")
        return self

    def __exit__(self, *exc):
        self.f.close()


def is_running() -> bool:
    """True while a tick holds the lock (the dashboard waits for it before starting its own jobs)."""
    LOCK_FILE.touch(exist_ok=True)
    with open(LOCK_FILE) as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return False
        except BlockingIOError:
            return True


def focus_view(now: dt.datetime | None = None) -> dict | None:
    """The one broken video Autopilot is working on (or will take next): what it is and what is still wrong with it."""
    now = now or dt.datetime.now(dt.timezone.utc)
    try:
        cfg = load_config()
        state = build_state(now, cfg)
        slug = next((a["slug"] for a in plan_actions({**state, "busy": False}, {**cfg, "enabled": True}, now) if a["do"] == "fix"), None)
        v = next((x for x in state["videos"] if x["slug"] == slug), None)
        return {"slug": slug, "title": v["title"] or slug, "problems": v["problems"], "tries": v["fix_attempts"]} if v else None
    except Exception:
        return None


def plan_view(now: dt.datetime | None = None) -> dict:
    """The next videos with their post times, and how many Autopilot still has to prepare."""
    now = now or dt.datetime.now(dt.timezone.utc)
    try:
        cfg = governed(load_config(), now)
        videos = build_state(now, cfg)["videos"]
        return {"governor": cfg.get("_caps"), "rows": [r for r in planner.rows(cfg, videos, now) if r["at"] <= (now + dt.timedelta(days=9)).strftime("%Y-%m-%dT%H:%M:%SZ")],
                "needs": planner.needs(cfg, videos, now), "prepare_hours": cfg["prepare_hours"], "review_hours": cfg["review_window_hours"], "per_day": {"doc": cfg["uploads_per_day"], "short": cfg["shorts_per_day"]}}
    except Exception:
        return {"rows": [], "needs": {"doc": 0, "short": 0}, "prepare_hours": 0, "review_hours": 0, "per_day": {}}


def status() -> dict:
    last = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else None
    return {"config": load_config(), "last_tick": last, "running": is_running(), "focus": focus_view(), "plan": plan_view()}
