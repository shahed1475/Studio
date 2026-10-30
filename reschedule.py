"""Put the schedule back on an approved video that is on YouTube, private, and past its publish time with no schedule left. Run by the OWNER: `python run.py reschedule <slug>`.

`safety.check` finds it ("still private after its publish time") and pauses Autopilot. Its own message says the most common cause is a person's edit in YouTube Studio, and a person may
have pulled the video on purpose, so Autopilot never does this by itself: it reports, and putting the video back on course to go public is the owner's decision (30 Oct 2026, after a security
review of the first version, which let Autopilot do it). The command only repairs the state: a new future `publishAt` on the next free slot, the video kept private, read back from YouTube,
logged with before and after (`actionlog`, source "owner command"). It never makes anything public (a time in the past would publish at once, so the time is always ahead), never touches a public
video, a video on hold, a duplicate story, one with an open invented-facts warning the owner has not approved, one YouTube rejected or blocked in countries, one it already repaired once (a second
loss is the owner's to look at in Studio), a user studio, or a machine whose YouTube login cannot change videos."""
import datetime as dt
import time

import actionlog
import config
import records
import scheduler

TS = "%Y-%m-%dT%H:%M:%SZ"
KEEP = ("embeddable", "license", "publicStatsViewable")  # status fields YouTube returned: sent back so an update does not reset them
READBACK_TRIES, READBACK_WAIT = 4, 3  # 30 Oct 2026, real YouTube: the update took, but the read right after it still showed the old status


def lost(meta: dict) -> bool:
    """The record says: uploaded, approved, not on hold, not taken back on purpose, the health check found it private after its time, not repaired before."""
    if not meta.get("video_id") or not meta.get("approved") or meta.get("hold") or meta.get("taken_back") or meta.get("rescheduled"):
        return False
    return any("still private" in str(p) for p in (meta.get("health") or {}).get("problems", []))


def _read(yt, video_id: str) -> dict:
    items = yt.videos().list(part="status,contentDetails", id=video_id).execute().get("items", [])
    if not items:
        raise LookupError(f"{video_id} is not on YouTube")
    return items[0]


def _live(yt, video_id: str) -> dict:
    return _read(yt, video_id).get("status", {})


def _confirmed(yt, video_id: str, when: str) -> tuple[bool, dict]:
    """Read the video back until YouTube shows the new time (it can lag a few seconds behind its own write)."""
    back: dict = {}
    for i in range(READBACK_TRIES):
        back = _live(yt, video_id)
        if str(back.get("publishAt", ""))[:19] == when[:19] and back.get("privacyStatus") == "private":
            return True, back
        if i < READBACK_TRIES - 1:
            time.sleep(READBACK_WAIT)
    return False, back


def apply(slug: str, cfg: dict, now: dt.datetime, yt=None) -> dict | None:
    """Returns None when the schedule is back, or {"skipped": why}."""
    import autopilot
    import fixer
    import policyclass
    import tenantmode

    if tenantmode.is_tenant():
        return {"skipped": "not available in a user studio"}
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
    if meta.get("approved_by") != "you" and fixer.watch_problems((meta.get("review") or {}).get("checks", [])):
        return {"skipped": "an invented-facts warning is open on this video: approve it yourself first (the same rule as scheduling)"}
    if yt is None:
        import titletest
        import upload

        if not titletest.can_write():
            return {"skipped": "this machine's YouTube login has no permission to change videos"}
        yt = upload._service()
    video_id = meta["video_id"]
    item = _read(yt, video_id)
    live = item.get("status", {})
    if live.get("privacyStatus") != "private":
        return {"skipped": "already public"}  # nothing to repair, and nothing here may change a public video
    if live.get("uploadStatus") in ("rejected", "failed", "deleted"):
        return {"skipped": f"YouTube {live['uploadStatus']} the upload ({live.get('rejectionReason') or live.get('failureReason') or 'no reason given'}): not touched"}
    blocked = ((item.get("contentDetails") or {}).get("regionRestriction") or {}).get("blocked")
    if blocked:
        return {"skipped": f"blocked in {len(blocked)} countr{'y' if len(blocked) == 1 else 'ies'} (often a claim): not touched"}
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
    before, after = {"privacyStatus": live.get("privacyStatus"), "publishAt": live.get("publishAt")}, {"privacyStatus": "private", "publishAt": when}
    ok, back = _confirmed(yt, video_id, when)
    if not ok:  # a change may have happened: it is on record, as unverified, and the owner checks it in Studio
        actionlog.record(video_id, before, after, "owner command", f"sent, but YouTube's read-back did not show it after {READBACK_TRIES} reads (it showed {back.get('publishAt')}): unverified, check it in Studio", now, kind="status")
        return {"skipped": f"read back from YouTube: scheduled time is {back.get('publishAt')}, expected {when}; not recorded as done (the attempt is in the action log as unverified)"}
    actionlog.record(video_id, before, after, "owner command", "the schedule of an approved video was gone after its publish time: the owner asked for a new future time on the next free slot", now, kind="status")
    records.merge(folder, {"publish_at": when, "rescheduled": {"at": now.strftime(TS), "from": meta.get("publish_at"), "to": when, "verified": True}})
    return None
