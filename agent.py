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
DEFAULTS = {"mode": "handoff", "study_per_run": 4}


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        try:
            raw = json.loads(CONFIG_FILE.read_text())
            if raw.get("mode") in MODES:
                cfg["mode"] = raw["mode"]
            if isinstance(raw.get("study_per_run"), int) and 0 <= raw["study_per_run"] <= 10:
                cfg["study_per_run"] = raw["study_per_run"]
        except ValueError:
            pass
    return cfg


def save_config(cfg: dict) -> dict:
    if cfg.get("mode") not in MODES:
        raise ValueError("mode must be off, handoff or automatic")
    out = {**DEFAULTS, **{k: cfg[k] for k in DEFAULTS if k in cfg}}
    CONFIG_FILE.write_text(json.dumps(out, indent=2))
    return out


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
        study = []
        for ref in refs + [c["id"] for c in discover.load()[:cfg["study_per_run"]] if c["id"] not in refs]:
            try:
                study.append(channelwatch.breakdown(yt, ref))
            except Exception as e:
                fail(f"study {ref}", e)
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
        if added:
            agentlog.event("strategy", f"{len(added)} new growth idea{'s' if len(added) != 1 else ''}",
                           "; ".join(s["text"] for s in added[:3]), notify=True, now=now)
        agentlog.event("info", "Daily research finished",
                       f"Studied {len(study)} channels, found {len(new)} new, {len(added)} new ideas, {len(applied)} applied", now=now)
        REPORTS.mkdir(parents=True, exist_ok=True)
        (REPORTS / f"{today}.json").write_text(json.dumps({
            "date": today, "at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "mode": cfg["mode"], "analysis": analysis,
            "studied": [{"channel": c.get("channel"), "channel_id": c.get("channel_id"), "median_views": c.get("summary", {}).get("median_views", 0),
                         "top": c.get("top", [])[:3]} for c in study],
            "new_channels": [c["id"] for c in new], "strategies_added": [s["id"] for s in added], "applied": [s["id"] for s in applied],
            "errors": errors}, indent=2))
        return {"mode": cfg["mode"], "new_channels": len(new), "studied": len(study), "strategies_added": len(added),
                "applied": len(applied), "errors": errors}
    finally:
        lock.close()
