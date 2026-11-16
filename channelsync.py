"""Write the channel's real video ids into local records (17 Nov 2026: the VPS and its upload records were deleted by the host).
Without an id, an approved video that is already on YouTube looks unsent and Autopilot would upload it a second time.
Reads YouTube only; writes nothing there. `python run.py channel-sync` shows the plan, `--apply` writes it."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import compliance
import records

RETRIES = 5  # google-api-python-client retries 5xx, 429 and rate-limit 403s with exponential backoff only when execute() is given num_retries


def channel_videos(yt) -> list[dict]:
    """Every upload of the channel (all pages), with the fields matching needs."""
    uploads = yt.channels().list(part="contentDetails", mine=True).execute(num_retries=RETRIES)["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, token = [], None
    while True:
        res = yt.playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=50, pageToken=token).execute(num_retries=RETRIES)
        ids += [i["contentDetails"]["videoId"] for i in res.get("items", [])]
        token = res.get("nextPageToken")
        if not token:
            break
    out = []
    for k in range(0, len(ids), 50):
        got = {v["id"]: v for v in yt.videos().list(part="snippet,status", id=",".join(ids[k:k + 50])).execute(num_retries=RETRIES).get("items", [])}
        for i in ids[k:k + 50]:
            if i in got:
                sn, st = got[i].get("snippet", {}), got[i].get("status", {})
                out.append({"id": i, "title": sn.get("title", ""), "description": sn.get("description", ""), "publishedAt": sn.get("publishedAt", ""),
                            "privacyStatus": st.get("privacyStatus", ""), "publishAt": st.get("publishAt")})
    return out


def _matched_by(meta: dict, v: dict) -> str | None:
    if meta.get("title") and v["title"] == meta["title"]:
        return "title"
    try:
        head = compliance.final_description(meta)[:120].strip()
    except Exception:
        head = ""
    if len(head) >= 40 and v["description"].strip().startswith(head):
        return "description"
    return None


def plan_adoptions(metas: list[dict], videos: list[dict]) -> dict:
    """Which local folders without an id are already on the channel. A video claimed by two folders (or a folder matching two videos) is a conflict for the owner."""
    unreadable = [m["slug"] for m in metas if m.get("unreadable")]
    metas = [m for m in metas if not m.get("unreadable")]
    held = {m["video_id"] for m in metas if m.get("video_id")}
    free = [v for v in videos if v["id"] not in held]
    open_ = [m for m in metas if not m.get("video_id")]
    hits = {m["slug"]: [(v, by) for v in free if (by := _matched_by(m, v))] for m in open_}
    claims: dict[str, list[str]] = {}
    for slug, hs in hits.items():
        for v, _ in hs:
            claims.setdefault(v["id"], []).append(slug)
    conflicts = [{"video_id": vid, "slugs": sorted(s)} for vid, s in claims.items() if len(s) > 1]
    bad = {s for c in conflicts for s in c["slugs"]}
    adopt = []
    for slug, hs in hits.items():
        if len(hs) > 1 and slug not in bad:
            conflicts.append({"slug": slug, "video_ids": [v["id"] for v, _ in hs]})
        elif len(hs) == 1 and slug not in bad:
            v, by = hs[0]
            adopt.append({"slug": slug, "video_id": v["id"], "by": by, "publishedAt": v["publishedAt"], "publishAt": v["publishAt"]})
    return {"adopt": adopt, "conflicts": conflicts, "unmatched_local": [m["slug"] for m in open_ if m.get("approved") and not hits[m["slug"]]],
            "already": len(metas) - len(open_), "unreadable": unreadable}


def apply_adoptions(out_dir: Path, plan: dict) -> int:
    """Merge each adopted id into its folder's record, unless the folder got an id in the meantime. A record that cannot be written is
    listed in plan["failed"] and the others are still written; running it again finishes the job."""
    n = 0
    plan["failed"] = []
    for row in plan.get("adopt", []):
        folder = Path(out_dir) / row["slug"]
        try:
            if records.read(folder).get("video_id"):
                continue
            records.merge(folder, {"video_id": row["video_id"], "uploaded_at": row["publishedAt"], "publish_at": row["publishAt"], "adopted_from_channel": True,
                                   "adopted_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
            n += 1
        except (OSError, ValueError) as e:
            plan["failed"].append({"slug": row["slug"], "error": f"{type(e).__name__}: {e}"})
    return n


def local_records(out_dir: Path) -> list[dict]:
    """Every local record; one that cannot be read comes back as {"slug", "unreadable": True} so the others are still checked."""
    out = []
    for m in sorted(Path(out_dir).glob("*/meta.json")):
        try:
            out.append({**records.read(m.parent), "slug": m.parent.name})
        except (OSError, ValueError):
            out.append({"slug": m.parent.name, "unreadable": True})
    return out
