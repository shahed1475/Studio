"""Channel Guardian: watches the channel and YouTube's rules, holds what is risky, and sends repairs to Autopilot.

Hourly, after the recheck. No model is asked here (it reads saved records and the rule-page log), so it costs nothing. For every video:
- a PUBLIC video is only watched. A problem is reported once to the owner; its title may change only through the title test (owner's mode, before and after
  views, automatic revert). That is how views and likes stay as they were.
- a video that is NOT public yet (draft, or private and scheduled): a metadata problem (limits, search phrase) is repaired, a thumbnail text that only repeats
  the title is rewritten, both pushed to YouTube when the owner's edit switch is on. A scheduled video the recheck put on hold with a content problem is
  REISSUED: it goes back to being a draft, Autopilot repairs, re-checks and schedules it and uploads a new private copy. The old private copy is never
  deleted; the owner is told to remove it in Studio.
It never makes anything public, deletes anything, edits a public video's content, changes channel settings or flips an owner switch."""
import datetime as dt
import fcntl
import json
from pathlib import Path

import agentbus
import agentlog
import config
import lessons
import records

EDIT_LIMIT = 2      # metadata repairs by the guardian per video
MAX_ACTIONS = 5     # videos acted on in one run
TS = "%Y-%m-%dT%H:%M:%SZ"
UPLOAD_KEYS = ("video_id", "uploaded_at", "publish_at", "upload_started", "upload_check", "playlists", "thumbnail_uploaded", "thumbnail_error", "cover_uploaded", "cover_error",
               "taken_back", "prelaunch_ok", "prelaunch")


def problems(meta: dict) -> list[dict]:
    """Findings for one saved record, from rules only: kind 'metadata' (repairable here) or 'content' (needs a repair of the video)."""
    import compliance
    import packaging
    import recheck

    out = [{"name": "metadata_limits", "kind": "metadata", "detail": p} for p in compliance.metadata_problems(meta)]
    out += [{"name": r["name"], "kind": "thumbnail" if r["name"] == "seo_thumbnail_text" else "metadata", "detail": r["detail"]}
            for r in packaging.audit(meta) if not r["ok"] and r["name"].startswith("seo_")]
    bad = [n for n in recheck.failing(meta.get("review") or {}) if n not in recheck.META_ONLY]
    out += [{"name": n, "kind": "content", "detail": "the saved review failed this check"} for n in bad]
    return out


def _public(meta: dict, now: dt.datetime) -> bool:
    import recheck

    if meta.get("hold"):
        return False  # a held video was made private (or never went out): holding is the owner's or the recheck's decision and it stays held
    return bool(meta.get("video_id")) and (recheck._when_dt(meta) or now) <= now


def _set_thumbnail(yt, video_id: str, path: Path) -> None:
    from googleapiclient.http import MediaFileUpload

    yt.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(path), mimetype="image/jpeg")).execute()


def fix_metadata(folder: Path, meta: dict, yt, now: dt.datetime) -> list[str]:
    import compliance
    import recheck

    work = json.loads(json.dumps(meta))
    done = compliance.sanitize(work)  # includes the search phrase up front
    if not done:
        return []
    if meta.get("video_id") and yt is not None:
        try:
            recheck.push_metadata(yt, work)
        except IndexError:  # YouTube lists no such video: it was deleted in Studio. Nothing to push; the owner is told once and the record is left as it was.
            agentbus.post("video_missing", "guardian", "owner", folder.name, reason=f"The video {meta['video_id']} is no longer on YouTube",
                          evidence="The guardian could not find it to update its title or description. Deleted in YouTube Studio?", now=now)
            return []
    keep = {k: work[k] for k in ("title", "description", "tags") if work.get(k) != meta.get(k)}
    g = dict(meta.get("guardian") or {})
    g["edits"] = g.get("edits", 0) + 1
    records.merge(folder, {**keep, "guardian": g})
    return done


def fix_thumbnail(folder: Path, meta: dict, yt, now: dt.datetime) -> str | None:
    import thumbnail

    hook = thumbnail.hook_for(meta, avoid=[meta.get("thumb_hook", "")])
    if not hook or hook == meta.get("thumb_hook"):
        return None
    thumbnail.make(folder, hook)
    fresh = json.loads((folder / "meta.json").read_text())
    if fresh.get("video_id") and yt is not None and fresh.get("thumbnail"):
        _set_thumbnail(yt, fresh["video_id"], folder / fresh["thumbnail"])
    g = dict(fresh.get("guardian") or {})
    g["thumb_edits"] = g.get("thumb_edits", 0) + 1
    records.merge(folder, {"guardian": g})
    return hook


def reissue(folder: Path, meta: dict, now: dt.datetime) -> bool:
    """Back to a draft so Autopilot repairs and uploads a new private copy. Only for a held video; not for one the owner approved, a public one, or a second time."""
    g = dict(meta.get("guardian") or {})
    if not meta.get("hold") or meta.get("approved_by") == "you" or g.get("reissued", 0) >= 1 or not meta.get("video_id") or _public(meta, now):
        return False
    g["reissued"] = g.get("reissued", 0) + 1
    g["reissued_at"] = now.strftime(TS)

    def apply(d: dict) -> None:
        d["superseded"] = (d.get("superseded") or []) + [d["video_id"]]
        for k in UPLOAD_KEYS:
            d.pop(k, None)
        for k in ("hold", "approved", "approved_by", "fix_attempts", "fix_gave_up", "recheck", "polish_done"):
            d.pop(k, None)
        d["guardian"] = g
        d.pop("review", None)

    try:
        records.update(folder, apply)
    except OSError:
        return False  # not saved: nothing was changed, the held video stays held
    return True


def run(now: dt.datetime | None = None, yt=None, may_edit: bool | None = None, out: Path | None = None, lock_file: Path | None = None) -> dict:
    import autopilot
    import newswatch
    import titletest

    now = now or dt.datetime.now(dt.timezone.utc)
    try:
        lock = open(lock_file or autopilot.LOCK_FILE, "w")
    except OSError:
        return {"skipped": "cannot open the lock file"}  # nothing is edited without the lock
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)  # never edit a video Autopilot is working on
    except BlockingIOError:
        return {"skipped": "locked"}
    try:
        if may_edit is None:
            may_edit = titletest.mode() == "apply" and titletest.can_write()
        result = {"actions": [], "watching": 0, "rule_changes": 0}
        try:
            changes = newswatch.recent_policy_changes(now, days=2)
        except (OSError, ValueError, KeyError):
            changes = []  # an unreadable rule log is read again next hour
        for c in changes:
            result["rule_changes"] += 1
            agentbus.post("verify_rule", "guardian", "owner", c["page"], reason=f"YouTube changed its page '{c['page']}'",
                          evidence=(c["added"] or c["removed"] or [""])[0], now=now)
        client = [yt]

        def get_yt():
            if may_edit and client[0] is None:
                client[0] = titletest._service()
            return client[0] if may_edit else None

        try:
            metas = sorted((out or config.OUT).glob("*/meta.json"))
        except OSError:
            return {**result, "skipped": "cannot read the videos folder"}
        for m in metas:
            if len(result["actions"]) >= MAX_ACTIONS:
                break
            try:
                meta = json.loads(m.read_text())
            except ValueError:
                continue
            try:
                folder, slug = m.parent, m.parent.name
                if meta.get("superseded") and meta.get("video_id"):
                    agentbus.close_for(slug, "re-uploaded as a new private copy", kind="repair_video", now=now)
                found = problems(meta)
                if not found:
                    agentbus.close_for(slug, "no problem found now", now=now)
                    continue
                result["watching"] += 1
                title = meta.get("title", slug)[:50]
                if _public(meta, now):
                    agentbus.post("public_video_problem", "guardian", "owner", slug, reason=f"A public video has a problem: {title}",
                                  evidence="; ".join(f"{f['name']}: {f['detail']}" for f in found[:4]), now=now)
                    continue
                g = meta.get("guardian") or {}
                kinds = {f["kind"] for f in found}
                if "metadata" in kinds and g.get("edits", 0) < EDIT_LIMIT:
                    done = fix_metadata(folder, meta, get_yt() if meta.get("video_id") else None, now)
                    if done:
                        left = [p for p in problems(json.loads(m.read_text())) if p["kind"] == "metadata"]
                        for f in found:
                            if f["kind"] == "metadata":
                                lessons.record("guardian", f"{f['name']} on a video not public yet", "deterministic metadata repair", not left, now)
                        result["actions"].append({"slug": slug, "did": done})
                        agentlog.event("applied", f"Guardian repaired the metadata of {title}", "; ".join(done), now=now)
                if "thumbnail" in kinds and g.get("thumb_edits", 0) < 1 and len(result["actions"]) < MAX_ACTIONS:
                    try:
                        hook = fix_thumbnail(folder, json.loads(m.read_text()), get_yt() if meta.get("video_id") else None, now)
                    except Exception as e:  # a thumbnail that cannot be made today is tried again by nobody: the owner hears of it
                        hook = None
                        agentlog.event("found", f"Guardian could not change the thumbnail of {title}", type(e).__name__, now=now)
                    if hook:
                        lessons.record("guardian", "thumbnail text repeats the title", "new thumbnail text naming the subject", True, now)
                        result["actions"].append({"slug": slug, "did": [f"thumbnail text: {hook}"]})
                        agentlog.event("applied", f"Guardian rewrote the thumbnail text of {title}", hook, now=now)
                if "content" in kinds and meta.get("hold"):
                    if reissue(folder, meta, now):
                        lessons.record("guardian", "content problem on a held video", "reissue as a new private upload", True, now)
                        agentbus.post("repair_video", "guardian", "autopilot", slug, reason=f"Content problem: {', '.join(f['name'] for f in found if f['kind'] == 'content')}",
                                      evidence="held on YouTube; reissued as a draft", now=now)
                        old = (json.loads(m.read_text()).get("superseded") or ["?"])[-1]
                        agentlog.event("applied", f"Guardian sent {title} back to Autopilot for repair", f"It will be uploaded again as a new private copy. The old private copy "
                                       f"({old}) is still on your channel: delete it in YouTube Studio when you see the new one.", notify=True, now=now)
                        result["actions"].append({"slug": slug, "did": ["reissued"]})
                    else:
                        agentbus.post("content_problem_held", "guardian", "owner", slug, reason=f"Held video with a content problem: {title}",
                                      evidence="; ".join(f['name'] for f in found if f['kind'] == 'content'), now=now)
                elif "content" in kinds:
                    agentbus.post("content_problem", "guardian", "autopilot", slug, reason=f"Content problem on a video not public yet: {title}",
                                  evidence="; ".join(f['name'] for f in found if f['kind'] == 'content'), now=now)
            except Exception as e:  # one video (a YouTube refusal, a full disk) must not stop the others
                agentlog.event("found", f"Guardian could not finish checking {m.parent.name[:40]}", f"{type(e).__name__}: {str(e)[:120]}", now=now)
        return result
    finally:
        lock.close()
