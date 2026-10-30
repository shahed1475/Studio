"""The studio's idea of what is on YouTube must be YouTube's (30 Oct 2026: three records said 'uploaded' and YouTube had none of the videos; the owner saw the studio's claim stay wrong).

Every hour (the health check calls this) each record with a video id is looked up on YouTube. An id YouTube cannot find on TWO checks in a row loses its id, is put on HOLD (it is never
uploaded again silently: the owner may have deleted it on purpose, or YouTube removed it) and the owner gets one plain event. Never read as 'gone': a video uploaded in the last 6 hours
(YouTube lags behind its own insert), a network error, or YouTube answering nothing for several ids at once (an outage). The owner releases the hold to upload a new copy."""
import datetime as dt
import json

import agentlog
import config
import records

FRESH = dt.timedelta(hours=6)
CONFIRM = 2          # consecutive checks that must miss the video
OUTAGE_ASKED = 3     # asked this many and none came back: YouTube is unwell, nothing is concluded
TS = "%Y-%m-%dT%H:%M:%SZ"


def _when(meta: dict, now: dt.datetime):
    try:
        return dt.datetime.strptime(str(meta.get("uploaded_at") or ""), TS).replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return now - FRESH * 100  # no upload time kept: old enough


def run(now: dt.datetime | None = None, yt=None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    rows = []
    for m in sorted(config.OUT.glob("*/meta.json")):
        try:
            meta = json.loads(m.read_text())
        except (OSError, ValueError):
            continue
        if meta.get("video_id") and now - _when(meta, now) >= FRESH:
            rows.append((m.parent, meta))
    if not rows:
        return {"checked": 0, "gone": []}
    try:
        if yt is None:
            import upload

            yt = upload._service()
        found, trusted = set(), set()
        for k in range(0, len(rows), 50):
            batch = rows[k:k + 50]
            got = {v["id"] for v in yt.videos().list(part="id", id=",".join(m["video_id"] for _, m in batch)).execute().get("items", [])}
            found |= got
            if got or len(batch) < OUTAGE_ASKED:  # a batch of several ids that returns none is an outage, judged per batch
                trusted |= {m["video_id"] for _, m in batch}
    except Exception as e:  # a network or login problem is the health check's to report, not a reason to forget a video
        return {"checked": 0, "gone": [], "error": f"{type(e).__name__}: {e}"[:160]}
    if not found and len(rows) >= OUTAGE_ASKED:  # decided over the whole run too: split into small batches it is still an outage
        return {"checked": len(rows), "gone": [], "error": "YouTube returned none of the videos: treated as an outage"}
    gone, gone_public = [], []
    for folder, meta in rows:
        if meta["video_id"] not in trusted:
            continue
        try:
            _one(folder, meta, found, now, gone, gone_public)
        except Exception:  # one bad record never discards the others' results
            continue
    return {"checked": len(rows), "gone": gone, "gone_public": gone_public}


def _one(folder, meta: dict, found: set, now: dt.datetime, gone: list, gone_public: list) -> None:
    if meta["video_id"] in found:
        if meta.get("missing_seen"):
            records.merge(folder, {"missing_seen": 0})
        return
    seen = int(meta.get("missing_seen") or 0) + 1
    if seen < CONFIRM:
        records.merge(folder, {"missing_seen": seen})
        return
    public = str(meta.get("publish_at") or meta.get("uploaded_at") or "") <= now.strftime(TS)  # same clock as the health check (publish_at, else uploaded_at): meant to be public by now
    records.merge(folder, {"pause_pending": public, "video_id": None, "upload_check": None, "uploaded_at": None, "thumbnail_uploaded": None, "missing_seen": 0, "hold": True,
                           "gone_from_youtube": {"video_id": meta["video_id"], "found_missing": now.strftime(TS), "note": "YouTube returned nothing for this id on two checks (deleted in Studio or removed by YouTube: unknown)"},
                           "hold_reason": "not on YouTube any more (deleted or removed): held so it is not uploaded again silently; release the hold to upload a new copy"})
    agentlog.event("error", f"A video is not on YouTube any more: {meta.get('title', folder.name)[:60]}", f"YouTube returned nothing for {meta['video_id']} on two checks in a row. The studio no longer calls it uploaded and "
                   "has held it (never uploaded again silently). Check YouTube Studio's Content page and your email for a removal notice; release the hold to upload a new copy.", notify=True, now=now)
    gone.append(folder.name)
    if public:
        gone_public.append(folder.name)

