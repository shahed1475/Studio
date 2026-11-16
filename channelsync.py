"""Write the channel's real video ids into local records (17 Nov 2026: the VPS and its upload records were deleted by the host).
Without an id, an approved video that is already on YouTube looks unsent and Autopilot would upload it a second time.
Reads YouTube only; writes nothing there. `python run.py channel-sync` shows the plan, `--apply` writes it."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import compliance
import records


def channel_videos(yt) -> list[dict]:
    """Every upload of the channel (all pages), with the fields matching needs."""
    uploads = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, token = [], None
    while True:
        res = yt.playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=50, pageToken=token).execute()
        ids += [i["contentDetails"]["videoId"] for i in res.get("items", [])]
        token = res.get("nextPageToken")
        if not token:
            break
    out = []
    for k in range(0, len(ids), 50):
        got = {v["id"]: v for v in yt.videos().list(part="snippet,status", id=",".join(ids[k:k + 50])).execute().get("items", [])}
        for i in ids[k:k + 50]:
            if i in got:
                sn, st = got[i].get("snippet", {}), got[i].get("status", {})
                out.append({"id": i, "title": sn.get("title", ""), "description": sn.get("description", ""), "publishedAt": sn.get("publishedAt", ""),
                            "privacyStatus": st.get("privacyStatus", ""), "publishAt": st.get("publishAt")})
    return out


def _same(meta: dict, v: dict) -> str | None:
    if meta.get("title") and v["title"] == meta["title"]:
        return "title"
    try:
        head = compliance.final_description(meta)[:120].strip()
    except Exception:
        head = ""
    if len(head) >= 40 and v["description"].strip().startswith(head):
        return "description"
    return None


def match(metas: list[dict], videos: list[dict]) -> dict:
    """Which local folders without an id are already on the channel. A video claimed by two folders (or a folder matching two videos) is a conflict for the owner."""
    held = {m["video_id"] for m in metas if m.get("video_id")}
    free = [v for v in videos if v["id"] not in held]
    open_ = [m for m in metas if not m.get("video_id")]
    hits = {m["slug"]: [(v, by) for v in free if (by := _same(m, v))] for m in open_}
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
            "already": len(metas) - len(open_)}


def apply(out_dir: Path, plan: dict) -> int:
    """Merge each adopted id into its folder's record, unless the folder got an id in the meantime."""
    n = 0
    for row in plan.get("adopt", []):
        folder = Path(out_dir) / row["slug"]
        if records.read(folder).get("video_id"):
            continue
        records.merge(folder, {"video_id": row["video_id"], "uploaded_at": row["publishedAt"], "publish_at": row["publishAt"], "adopted_from_channel": True,
                               "adopted_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
        n += 1
    return n


def local_metas(out_dir: Path) -> list[dict]:
    return [{**records.read(m.parent), "slug": m.parent.name} for m in sorted(Path(out_dir).glob("*/meta.json"))]
