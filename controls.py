"""The studio's control layer: a small set of safe, named calls to look at the studio and to hold a video, used by the MCP server (and usable from the command line).

`python -m controls` reads one JSON object from standard input, {"call": "videos", "args": {}}, runs that ONE named call and prints JSON. Nothing the caller
sends is ever run as code or used to build a path: the call name must be in CALLS, argument names must match the function, and a video name must be a plain slug
of an existing folder.

Never here, on purpose: making a video public, deleting anything, changing channel settings or money limits. Those stay with the owner (CLAUDE.md, section E)."""
import datetime as dt
import inspect
import json
import re
import sys

import config

SLUG = re.compile(r"[a-z0-9][a-z0-9_-]{0,120}")
TS = "%Y-%m-%dT%H:%M:%SZ"


def _slug(raw) -> str:
    if not isinstance(raw, str) or not SLUG.fullmatch(raw):
        raise ValueError("bad video name")
    if not (config.OUT / raw / "meta.json").is_file():
        raise ValueError(f"no such video: {raw}")
    return raw


def _read(slug: str) -> dict:
    return json.loads((config.OUT / _slug(slug) / "meta.json").read_text())


def _short(text, n: int = 300) -> str:
    return str(text or "")[:n]


def _failing(meta: dict) -> list[dict]:
    checks = (meta.get("review") or {}).get("checks", [])
    return [{"name": c["name"], "severity": c["severity"], "detail": _short(c.get("detail"))} for c in checks if not c["ok"]]


def videos(now: str | None = None) -> list[dict]:
    """Every video in the studio, one small record each (no script text)."""
    out = []
    for m in sorted(config.OUT.glob("*/meta.json")):
        try:
            d = json.loads(m.read_text())
        except ValueError:
            continue
        out.append({"slug": m.parent.name, "title": _short(d.get("title"), 120), "format": d.get("format") or "short",
                    "verdict": (d.get("review") or {}).get("verdict"), "approved": bool(d.get("approved")), "hold": bool(d.get("hold")),
                    "on_youtube": bool(d.get("video_id")), "video_id": d.get("video_id"), "publish_at": d.get("publish_at"), "uploaded_at": d.get("uploaded_at"),
                    "upload_ok": (d.get("upload_check") or {}).get("ok") if isinstance(d.get("upload_check"), dict) else None})
    return out


def video(slug: str) -> dict:
    """One video in detail: what is failing, where it stands, what it cost."""
    import llm

    d = _read(slug)
    return {"slug": slug, "title": _short(d.get("title"), 160), "format": d.get("format") or "short", "topic": _short(d.get("topic"), 160),
            "verdict": (d.get("review") or {}).get("verdict"), "failing": _failing(d), "approved": bool(d.get("approved")), "approved_by": d.get("approved_by"),
            "hold": bool(d.get("hold")), "taken_back": d.get("taken_back"), "video_id": d.get("video_id"), "publish_at": d.get("publish_at"),
            "uploaded_at": d.get("uploaded_at"), "playlists": d.get("playlists"), "recheck": d.get("recheck"), "title_test": d.get("title_test"),
            "footage": d.get("footage"), "cost_usd": round(llm.video_cost(slug), 3), "description_start": _short(d.get("description")),
            "sources": [_short(s, 160) for s in (d.get("sources") or [])[:6]]}


def events(n: int = 20) -> list[dict]:
    """The newest activity-feed entries (what Autopilot and the agents did)."""
    import agentlog

    return [{"at": e["at"], "kind": e["kind"], "title": _short(e["title"], 200), "detail": _short(e.get("detail"), 400)} for e in agentlog.recent(max(1, min(int(n), 200)))]


def next_slots(now: str | None = None) -> list[dict]:
    """The coming publish slots and what fills each (empty, repairing, ready, scheduled, uploaded)."""
    import autopilot
    import planner

    t = dt.datetime.strptime(now, TS).replace(tzinfo=dt.timezone.utc) if now else dt.datetime.now(dt.timezone.utc)
    cfg = autopilot.load_config()
    st = autopilot.build_state(t, cfg)
    return [{k: r[k] for k in ("format", "at", "status", "title", "slug", "starts_us")} for r in planner.rows(cfg, st["videos"], t, per_format=4)]


def status() -> dict:
    """Autopilot switches, money, the Risks card and counts: the one-screen picture."""
    import autopilot
    import llm
    import risk

    cfg, now = autopilot.load_config(), dt.datetime.now(dt.timezone.utc)
    key = llm.api_key()
    try:
        credit = risk.credit_left(key) if key else None
    except Exception:
        credit = None
    cap = llm.load_config()["daily_budget_usd"]
    spent = round(llm.spent_today(now), 2)
    try:
        rows = [{"id": r["id"], "name": r["name"], "level": r["level"], "evidence": _short(r["evidence"], 220)} for r in risk.assess(now, left=credit)]
    except Exception as e:  # a failing indicator must not hide the rest of the picture
        rows = [{"id": "error", "name": "Risks could not be read", "level": "watch", "evidence": type(e).__name__}]
    vs = videos()
    return {"autopilot": {k: cfg.get(k) for k in ("enabled", "auto_approve", "review_window_hours", "prepare_hours", "uploads_per_day", "shorts_per_day", "max_videos_per_week")},
            "money": {"spent_today": spent, "daily_cap": cap, "cap_left": round(cap - spent, 2), "credit": credit},
            "risks": rows, "counts": {"videos": len(vs), "on_youtube": sum(v["on_youtube"] for v in vs), "held": sum(v["hold"] for v in vs),
                                      "failing": sum(1 for v in vs if v["verdict"] in ("fail", "needs_human") and not v["on_youtube"])}}


def report() -> dict:
    """The daily report text, built now (nothing is written to the feed)."""
    import dailyreport
    import llm
    import risk

    key = llm.api_key()
    try:
        credit = risk.credit_left(key) if key else None
    except Exception:
        credit = None
    r = dailyreport.build(dt.datetime.now(dt.timezone.utc), credit)
    return {"text": r["text"], "problems": r["problems"]}


def hold(slug: str, yt=None, now: str | None = None) -> dict:
    """Keep a video from going out. A draft gets a hold flag. An upload scheduled on YouTube is also made private there (no publish time), so it cannot go
    public by itself; it is never made public again by this tool."""
    import recheck

    folder = config.OUT / _slug(slug)
    d = _read(slug)
    t = dt.datetime.strptime(now, TS).replace(tzinfo=dt.timezone.utc) if isinstance(now, str) else (now or dt.datetime.now(dt.timezone.utc))
    changes = {"hold": True}
    where = "not on YouTube: the hold stops Autopilot from approving, scheduling or uploading it"
    if d.get("video_id"):
        try:
            if yt is None:
                import titletest

                if not (titletest.mode() == "apply" and titletest.can_write()):
                    raise PermissionError("the YouTube login cannot edit videos")
                yt = titletest._service()
            recheck.take_back(yt, d["video_id"])
            changes["taken_back"] = t.strftime(TS)
            where = "made private on YouTube (no publish time); it cannot go public by itself"
        except Exception as e:
            where = f"the flag is set, but YouTube was NOT changed ({type(e).__name__}): make it private in YouTube Studio"
    recheck._merge(folder, changes)
    return {"slug": slug, "held": True, "youtube": where}


def release(slug: str) -> dict:
    """Take the hold off. A draft gets a fresh slot (like the dashboard does). An upload that was pulled back stays private on YouTube: publishing it is the owner's."""
    import recheck

    folder = config.OUT / _slug(slug)
    d = _read(slug)
    if d.get("video_id"):
        recheck._merge(folder, {"hold": False})
        return {"slug": slug, "held": False, "note": "released in the studio, but the video is still private on YouTube if it was pulled back: "
                                                       "publish or schedule it yourself in YouTube Studio"}
    fresh = json.loads((folder / "meta.json").read_text())
    fresh.pop("publish_at", None)  # a released draft gets a fresh slot instead of a stale or shared one
    fresh.update(hold=False, autopilot_fails=0)
    (folder / "meta.json").write_text(json.dumps(fresh, indent=2))
    return {"slug": slug, "held": False, "note": "released: Autopilot may work on it again"}


def run_pass() -> dict:
    """One Autopilot pass now (same as the 30-minute timer; it takes the same lock)."""
    import autopilot

    return autopilot.tick()


def make_backup() -> dict:
    import backup

    return backup.run()


READ = {"status": status, "videos": videos, "video": video, "events": events, "next_slots": next_slots, "report": report}
WRITE = {"hold": hold, "release": release, "run_pass": run_pass, "make_backup": make_backup}
CALLS = {**READ, **WRITE}


def dispatch(call, args: dict | None = None):
    """Run one named call with plain JSON arguments. Unknown names and unknown argument names are refused."""
    if not isinstance(call, str) or call not in CALLS:
        raise ValueError("unknown call")
    fn, args = CALLS[call], dict(args or {})
    allowed = set(inspect.signature(fn).parameters) - {"yt", "now"}  # a YouTube service or a clock is never passed in from outside
    if set(args) - allowed:
        raise ValueError("unknown argument")
    return fn(**args)


def main() -> int:
    try:
        req = json.loads(sys.stdin.read() or "{}")
        out = {"ok": True, "result": dispatch(req.get("call"), req.get("args"))}
    except Exception as e:
        out = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
    print(json.dumps(out, default=str))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
