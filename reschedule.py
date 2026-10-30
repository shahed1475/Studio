"""Put the schedule back on an approved video that is on YouTube, private, and past its publish time with no schedule left.

`safety.check` finds it ("still private after its publish time") and pauses Autopilot. The known causes: an edit in YouTube Studio
can clear the schedule, a block or an account limit are the others. The cause of a given case is not known from our side, so this module only repairs the
state: a new future `publishAt` on the next free slot, the video kept private, read back from YouTube, logged with before and after (`actionlog`). It never
makes anything public (a time in the past would publish at once, so the time is always ahead), never touches a public video, a video on hold, a duplicate
story, or one it already repaired once (a second loss goes to the owner)."""
import datetime as dt

import actionlog
import config
import records
import scheduler

TS = "%Y-%m-%dT%H:%M:%SZ"
KEEP = ("embeddable", "license", "publicStatsViewable")  # status fields YouTube returned: sent back so an update does not reset them


def lost(meta: dict) -> bool:
    """The record says: uploaded, approved, not on hold, not taken back on purpose, the health check found it private after its time, not repaired before."""
    if not meta.get("video_id") or not meta.get("approved") or meta.get("hold") or meta.get("taken_back") or meta.get("rescheduled"):
        return False
    return any("still private" in str(p) for p in (meta.get("health") or {}).get("problems", []))


def _live(yt, video_id: str) -> dict:
    items = yt.videos().list(part="status", id=video_id).execute().get("items", [])
    if not items:
        raise LookupError(f"{video_id} is not on YouTube")
    return items[0].get("status", {})


def apply(slug: str, cfg: dict, now: dt.datetime, yt=None) -> dict | None:
    """Returns None when the schedule is back, or {"skipped": why}."""
    import autopilot
    import policyclass

    if policyclass.hold_active():
        return {"skipped": "policy hold: a YouTube rule page changed and the owner has not released it"}
    folder = config.OUT / slug
    _, meta = autopilot._meta(slug)
    if not lost(meta):
        return {"skipped": "not lost"}
    twin = autopilot._twin(slug)
    if twin:
        autopilot.hold_duplicate(slug, twin, now)
        return {"skipped": "duplicate"}
    if yt is None:
        import upload

        yt = upload._service()
    video_id = meta["video_id"]
    live = _live(yt, video_id)
    if live.get("privacyStatus") != "private":
        return {"skipped": "already public"}  # nothing to repair, and nothing here may change a public video
    if live.get("publishAt") and dt.datetime.strptime(live["publishAt"][:19], TS[:-1]).replace(tzinfo=dt.timezone.utc) > now:
        records.merge(folder, {"publish_at": live["publishAt"][:19] + "Z"})
        return {"skipped": "still scheduled"}
    if live.get("uploadStatus") != "processed":
        return {"skipped": "not processed yet"}
    at = autopilot.free_slot(slug, meta.get("format", "short"), cfg, now)
    if at is None:
        return {"skipped": "no slot within the weekly pace limit"}
    when = scheduler.to_rfc3339(at)
    status = {k: live[k] for k in KEEP if k in live}
    status.update({"privacyStatus": "private", "publishAt": when, "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True})  # the same disclosure the upload made
    yt.videos().update(part="status", body={"id": video_id, "status": status}).execute()
    back = _live(yt, video_id)
    if str(back.get("publishAt", ""))[:19] != when[:19] or back.get("privacyStatus") != "private":
        return {"skipped": f"read back from YouTube: scheduled time is {back.get('publishAt')}, expected {when}; not recorded as done"}
    actionlog.record(video_id, {"privacyStatus": live.get("privacyStatus"), "publishAt": live.get("publishAt")}, {"privacyStatus": "private", "publishAt": when},
                     "autopilot", "the schedule of an approved video was gone after its publish time: set a new future time on the next free slot", now, kind="status")
    records.merge(folder, {"publish_at": when, "rescheduled": {"at": now.strftime(TS), "from": meta.get("publish_at"), "to": when, "verified": True}})
    return None
