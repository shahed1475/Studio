"""Growth agent: one daily run that studies our channel and competitors, then proposes (hand-off) or applies safe changes (automatic)."""
import datetime as dt
import fcntl
import json

import agentlog
import channelwatch
import config
import discover
import growth
import strategy

CONFIG_FILE = config.ROOT / "agent.json"
LOCK_FILE = config.ROOT / "agent.lock"
REPORTS = config.ROOT / "data" / "agent" / "reports"
MODES = ("off", "handoff", "automatic")
DEFAULTS = {"mode": "handoff", "study_per_run": 4,
            "auto_channels": True, "auto_per_day": 3, "max_auto": 25,
            "auto_topics": True, "topics_per_day": 3}  # research ideas join the topic queue by themselves, this many a day  # the agent may add this many reference channels a day, up to max_auto in all


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        try:
            raw = json.loads(CONFIG_FILE.read_text())
            if raw.get("mode") in MODES:
                cfg["mode"] = raw["mode"]
            if isinstance(raw.get("study_per_run"), int) and 0 <= raw["study_per_run"] <= 20:
                cfg["study_per_run"] = raw["study_per_run"]
            for k in ("auto_channels", "auto_topics"):
                if isinstance(raw.get(k), bool):
                    cfg[k] = raw[k]
            for k, hi in (("auto_per_day", 10), ("max_auto", 35), ("topics_per_day", 10)):
                if isinstance(raw.get(k), int) and not isinstance(raw.get(k), bool) and 0 <= raw[k] <= hi:
                    cfg[k] = raw[k]
        except ValueError:
            pass
    return cfg


def save_config(cfg: dict) -> dict:
    if cfg.get("mode") not in MODES:
        raise ValueError("mode must be off, handoff or automatic")
    for k in ("auto_channels", "auto_topics"):
        if not isinstance(cfg.get(k, True), bool):
            raise ValueError(f"{k} must be on or off")
    for k, lo, hi in (("auto_per_day", 1, 10), ("max_auto", 0, 35), ("topics_per_day", 1, 10)):
        v = cfg.get(k, DEFAULTS[k])
        if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
            raise ValueError(f"{k} must be a whole number from {lo} to {hi}")
    out = {**DEFAULTS, **{k: cfg[k] for k in DEFAULTS if k in cfg}}
    CONFIG_FILE.write_text(json.dumps(out, indent=2))
    return out


MAX_QUEUE = 15  # the research agent stops adding ideas when this many topics already wait


def _similar(a: str, b: str, ratio: float = 0.75) -> bool:
    import difflib
    import re

    n = lambda t: re.sub(r"[^a-z0-9 ]", "", t.lower()).strip()
    return difflib.SequenceMatcher(None, n(a), n(b)).ratio() >= ratio


def known_topics() -> list[str]:
    """Everything already queued, made, set aside or given up on, so an idea is never queued twice."""
    import topicqueue

    out = list(topicqueue.items())
    for root in (config.OUT, config.ROOT / "output_old"):
        for m in root.glob("*/meta.json") if root.exists() else []:
            try:
                d = json.loads(m.read_text())
            except ValueError:
                continue
            out += [d.get("topic", ""), d.get("title", "")]
    try:
        out += list(json.loads((config.ROOT / "data" / "topic_fails.json").read_text()))
    except (OSError, ValueError):
        pass
    return [t for t in out if t]


def queue_ideas(cfg: dict, now: dt.datetime | None = None) -> list[str]:
    """Put the best new story ideas from the reference-channel study and the niche trends into the topic queue (a few a day, never duplicates)."""
    import topicqueue
    import trendwatch

    if not cfg.get("auto_topics"):
        return []
    room = min(cfg["topics_per_day"], MAX_QUEUE - len(topicqueue.items()))
    if room <= 0:
        return []
    ideas = [t for src in (channelwatch.latest(), trendwatch.latest()) for t in ((src or {}).get("ideas") or []) if isinstance(t, str) and 12 <= len(t) <= 160]
    known, added = known_topics(), []
    for t in ideas:
        if len(added) >= room:
            break
        t = topicqueue.subject_of(t)  # the queue takes subjects, not instructions
        if not t:
            continue
        if any(_similar(t, k) for k in known + added):
            continue
        added.append(t.strip())
    new = topicqueue.extend(added)
    if new:
        agentlog.event("applied", f"Added {len(new)} story idea{'s' if len(new) != 1 else ''} to the queue", "; ".join(new[:3]), now=now)
    return new


def briefing(now: dt.datetime, added_channels: list, removed_channels: list, added_topics: list) -> str:
    """One plain summary of where everything stands, written to the activity feed each morning."""
    import topicqueue

    states = {"waiting": 0, "approved": 0, "live": 0}
    upcoming = []
    for m in config.OUT.glob("*/meta.json") if config.OUT.exists() else []:
        try:
            d = json.loads(m.read_text())
        except ValueError:
            continue
        if d.get("video_id"):
            states["live"] += 1
        elif d.get("approved"):
            states["approved"] += 1
            if d.get("publish_at"):
                upcoming.append((d["publish_at"], d.get("title", "?")))
        else:
            states["waiting"] += 1
    day = now.strftime("%Y-%m-%d")
    today = [e for e in agentlog.recent(80) if e["at"].startswith(day)]
    fixes = [e["title"] for e in today if e["title"].startswith(("Fixed:", "Set aside"))]
    stuck = [e["title"] for e in today if e["title"].startswith("Needs your eyes")]
    parts = [f"{states['live']} videos live, {states['approved']} approved and waiting for their time, {states['waiting']} waiting for a decision"]
    if upcoming:
        when, title = sorted(upcoming)[0]
        parts.append(f"next to go public: {title} at {when[:16].replace('T', ' ')} UTC")
    parts.append(f"{len(topicqueue.items())} topics queued" + (f" ({len(added_topics)} added today)" if added_topics else ""))
    if added_channels or removed_channels:
        parts.append(f"reference channels: {len(added_channels)} added, {len(removed_channels)} removed")
    if fixes:
        parts.append(f"fixer: {len(fixes)} video{'s' if len(fixes) != 1 else ''} repaired or remade")
    if stuck:
        parts.append(f"needs you: {'; '.join(stuck[:3])}")
    text = ". ".join(parts) + "."
    agentlog.event("info", "Daily briefing", text, now=now)
    return text


def latest_report() -> dict | None:
    files = sorted(REPORTS.glob("*.json")) if REPORTS.exists() else []
    return json.loads(files[-1].read_text()) if files else None


def run(now: dt.datetime | None = None, yt=None, chat=None, force: bool = False) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    cfg = load_config()
    if cfg["mode"] == "off":
        return {"skipped": "off"}
    lock = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return {"skipped": "locked"}
    try:
        today = now.strftime("%Y-%m-%d")
        if not force and (REPORTS / f"{today}.json").exists():
            return {"skipped": "already ran today"}
        errors: list[str] = []

        def fail(step: str, e: Exception) -> None:
            errors.append(f"{step}: {type(e).__name__}: {e}")
            agentlog.event("error", f"Problem while I was working: {step}", f"{type(e).__name__}: {e}", notify=True, now=now)

        agentlog.event("info", "Daily research started", f"Mode: {cfg['mode']}", now=now)
        if yt is None:
            try:
                import trendwatch

                yt = trendwatch._service()
            except Exception as e:
                fail("connect to YouTube", e)
                return {"mode": cfg["mode"], "new_channels": 0, "studied": 0, "strategies_added": 0, "applied": 0, "errors": errors}

        own_id = ""
        try:
            own_id = growth.snapshot(yt, now)["channel_id"]
        except Exception as e:
            fail("read our channel", e)
        refs = channelwatch.load_refs()
        new = []
        try:
            new = discover.run(yt, own_id, refs, chat)
        except Exception as e:
            fail("find competitors", e)
        added_channels: list[dict] = []
        try:  # the best new finds, and the channels that keep showing up in the weekly search, join the reference list
            import trendwatch

            pool = new + [c for c in discover.load() if c["id"] not in {n["id"] for n in new}]
            if cfg["auto_channels"]:
                pool += discover.trend_candidates(trendwatch.latest(), chat, own_id)
            added_channels = discover.auto_add(yt, pool, cfg, now, own_id)
        except Exception as e:
            fail("add reference channels", e)
        refs = channelwatch.load_refs()
        study = []
        for ref in refs + [c["id"] for c in discover.load()[:cfg["study_per_run"]] if c["id"] not in refs]:
            try:
                b = channelwatch.breakdown(yt, ref, now=now)
                b["ref"] = ref
                study.append(b)
            except Exception as e:
                fail(f"study {ref}", e)
        removed_channels: list[str] = []
        try:
            removed_channels = discover.prune_inactive(study, now)
            discover.review_fit([b for b in study if b["ref"] in set(refs)], chat, now)
        except Exception as e:
            fail("check reference channels", e)
        snaps = growth.load_snapshots()
        analysis = growth.analyze(snaps, study)
        if snaps:
            import monetization

            analysis["monetization"] = monetization.progress(snaps[-1], now, monetization.ready_count())
        added = strategy.add(strategy.generate(analysis, study, chat))
        applied = []
        if cfg["mode"] == "automatic":
            for s in added:
                if s["auto_ok"]:
                    try:
                        strategy.apply(s["id"])
                        applied.append(s)
                        agentlog.event("applied", f"I applied: {s['text']}", s["why"], notify=True, now=now)
                    except Exception as e:
                        fail(f"apply {s['id']}", e)
        added_topics: list[str] = []
        try:
            added_topics = queue_ideas(cfg, now)
        except Exception as e:
            fail("queue story ideas", e)
        if added:
            agentlog.event("strategy", f"{len(added)} new growth idea{'s' if len(added) != 1 else ''}",
                           "; ".join(s["text"] for s in added[:3]), notify=True, now=now)
        agentlog.event("info", "Daily research finished",
                       f"Studied {len(study)} channels, found {len(new)} new, added {len(added_channels)} to your list, {len(added)} new ideas, {len(applied)} applied", now=now)
        brief = ""
        try:
            import risk

            import llm

            left = risk.credit_left(llm.api_key()) if llm.api_key() else None
            rows = risk.assess(now, left=left)
            risk.guard(left, now=now)
            summary = risk.summary(rows)
            if summary["act"] or summary["watch"]:
                agentlog.event("error" if summary["act"] else "info", f"Risks: {len(summary['act'])} need action, {len(summary['watch'])} to watch",
                               "; ".join(summary["act"] + summary["watch"])[:300], now=now)
        except Exception as e:
            fail("check the risks", e)
        try:
            brief = briefing(now, added_channels, removed_channels, added_topics)
        except Exception as e:
            fail("write the daily briefing", e)
        REPORTS.mkdir(parents=True, exist_ok=True)
        (REPORTS / f"{today}.json").write_text(json.dumps({
            "date": today, "at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "mode": cfg["mode"], "analysis": analysis, "briefing": brief, "topics_added": added_topics,
            "studied": [{"channel": c.get("channel"), "channel_id": c.get("channel_id"), "median_views": c.get("summary", {}).get("median_views", 0),
                         "top": c.get("top", [])[:3]} for c in study],
            "new_channels": [c["id"] for c in new], "channels_added": [c["id"] for c in added_channels], "channels_removed": removed_channels,
            "strategies_added": [s["id"] for s in added], "applied": [s["id"] for s in applied],
            "errors": errors}, indent=2))
        return {"mode": cfg["mode"], "new_channels": len(new), "channels_added": len(added_channels), "studied": len(study), "strategies_added": len(added),
                "applied": len(applied), "errors": errors}
    finally:
        lock.close()
