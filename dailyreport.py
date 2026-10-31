"""One plain-English report a day in the activity feed: what was made and uploaded in the last 24 hours, what comes next, what it cost, what is wrong.

Written for the owner who does not read logs. It reads files only (no model call, no YouTube call), so it cannot fail because a service is down."""
import datetime as dt
import json

import agentlog
import autopilot
import config
import filelock

STATE = config.ROOT / "data" / "daily_report.json"
TS = "%Y-%m-%dT%H:%M:%SZ"


def _parse(ts: str) -> dt.datetime:
    return dt.datetime.strptime(ts, TS).replace(tzinfo=dt.timezone.utc)


def _event_is_open(title: str, records: list[dict]) -> bool:
    """An event is history, a report line is today's state. A 'found' or 'error' event about one video counts only while that video still shows the problem:
    the thumbnail set on a retry, a duplicate the owner released and a film re-uploaded under a new title were all listed a day after they were fixed. An event
    of any other kind of title is kept as it is. The title the event names is the record's title when it was written; a title nobody has any more means the
    video was retitled, archived or deleted, so the event no longer describes a video that exists."""
    def named(prefix):
        name = title[len(prefix):]
        return [r for r in records if r.get("title") == name]

    if title.startswith("Thumbnail was not set: "):
        return False  # the video's own state is read below (thumbnail_error without thumbnail_uploaded)
    if title.startswith("Held a duplicate: "):
        name = title[len("Held a duplicate: "):]  # the event cuts the title at 60 characters
        return any(r.get("hold") for r in records if (r.get("title") or "").startswith(name))
    if title.startswith("Pulled back for repair: "):
        return any(not r.get("video_id") and (r.get("review") or {}).get("verdict") != "pass" for r in named("Pulled back for repair: "))
    if title.startswith("Stopped spending on: "):
        return any(not r.get("video_id") and not r.get("approved") for r in named("Stopped spending on: "))
    if title.startswith("Narration check found missing words: "):
        return any(not r.get("video_id") for r in named("Narration check found missing words: "))
    return True


def build(now: dt.datetime, credit: float | None = None) -> dict:
    import llm

    since = now - dt.timedelta(hours=24)
    made, uploaded, coming, problems, held, records = [], [], [], [], [], []
    for m in sorted(config.OUT.glob("*/meta.json")):
        try:
            meta = json.loads(m.read_text())
        except ValueError:
            continue
        records.append(meta)
        title = meta.get("title", m.parent.name)
        mp4 = m.parent / "video.mp4"
        if mp4.exists() and dt.datetime.fromtimestamp(mp4.stat().st_mtime, dt.timezone.utc) >= since:
            made.append(title)
        if meta.get("uploaded_at") and _parse(meta["uploaded_at"]) >= since:
            uploaded.append(title)
        at = meta.get("publish_at")
        if at and now <= _parse(at) <= now + dt.timedelta(hours=48) and not meta.get("hold"):
            coming.append({"title": title, "at": at, "on_youtube": bool(meta.get("video_id"))})
        review = meta.get("review") or {}
        if not meta.get("video_id") and review.get("verdict") in ("fail", "needs_human"):
            names = [c["name"] for c in review.get("checks", []) if not c["ok"] and c["severity"] in ("block", "human")]
            problems.append(f"{title} failed its review ({', '.join(names) or review['verdict']}); Autopilot is repairing it or waiting for you")
        if meta.get("hold") and meta.get("video_id"):  # private on purpose and waiting for the owner: a decision, not a failure
            why = (meta.get("hold_reason") or "")[:80] or (f"pulled back {meta['taken_back'][:10]}" if meta.get("taken_back") else "held")
            held.append((title, why))
        if meta.get("video_id") and meta.get("thumbnail_error") and not meta.get("thumbnail_uploaded"):
            problems.append(f"{title} has no custom thumbnail (YouTube refused it): add it in YouTube Studio")
    coming.sort(key=lambda c: c["at"])
    day = (now - dt.timedelta(days=1)).strftime("%Y-%m-%d")
    spend = round(float(llm._usage().get(day, {}).get("usd", 0.0)), 2)
    for e in agentlog._all():
        if e["kind"] in ("found", "error") and _parse(e["at"]) >= since and _event_is_open(e["title"], records):
            problems.append(f"{e['title']}")
    if credit is not None and credit < autopilot.MIN_CREDIT_TO_MAKE:
        problems.append(f"OpenRouter credit is ${credit:.2f}: below ${autopilot.MIN_CREDIT_TO_MAKE:.2f} Autopilot makes no new video")
    snaps = []
    try:
        import growth

        snaps = growth.load_snapshots(1)
    except Exception:
        pass
    chan = f" Channel: {snaps[-1]['subscribers']} subscribers, {snaps[-1]['views']} views, {snaps[-1]['videos']} videos." if snaps else ""
    lines = [f"Made: {', '.join(made) or 'nothing'}.", f"Uploaded: {', '.join(uploaded) or 'nothing'}.",
             "Coming in 48 hours: " + ("; ".join(f"{c['title']} ({c['at'][5:16].replace('T', ' ')} UTC{'' if c['on_youtube'] else ', not uploaded yet'})" for c in coming) or "nothing scheduled") + ".",
             *([f"Held private on YouTube, waiting for your decision: {'; '.join(f'{t} ({w})' for t, w in held)}."] if held else []),
             f"Spent yesterday: ${spend:.2f}." + (f" Credit left: ${credit:.2f}." if credit is not None else "") + chan,
             "Problems: " + ("; ".join(dict.fromkeys(problems)) if problems else "none") + "."]
    return {"made": made, "uploaded": uploaded, "coming": coming, "spend": spend, "credit": credit, "held": [t for t, _ in held], "problems": list(dict.fromkeys(problems)), "text": "\n".join(lines)}


def run(now: dt.datetime | None = None, credit: float | None = None) -> dict:
    """Write today's report once (UTC day). Returns the report plus written=True/False."""
    now = now or dt.datetime.now(dt.timezone.utc)
    day = now.strftime("%Y-%m-%d")
    STATE.parent.mkdir(parents=True, exist_ok=True)
    with filelock.locked(STATE):
        try:
            last = json.loads(STATE.read_text()).get("day")
        except (OSError, ValueError):
            last = None
        if last == day:
            return {"written": False}
        report = build(now, credit)
        agentlog.event("info", f"Daily report {day}: {len(report['uploaded'])} uploaded, {len(report['made'])} made, {len(report['problems'])} problem(s)", report["text"], now=now)
        filelock.write_atomic(STATE, json.dumps({"day": day}))
    return {"written": True, **report}
