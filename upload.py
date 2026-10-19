"""YouTube upload via the official Data API. Needs client_secret.json (see README)."""
import datetime as dt
import json
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

import config

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"]  # same as dashboard.py
SECRET = config.ROOT / "client_secret.json"
TOKEN = config.ROOT / "token.json"


def _service():
    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES) if TOKEN.exists() else None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not SECRET.exists():
                raise SystemExit("client_secret.json missing. Follow the YouTube setup steps in README.md.")
            creds = InstalledAppFlow.from_client_secrets_file(str(SECRET), SCOPES).run_local_server(port=0)
        TOKEN.write_text(creds.to_json())
        TOKEN.chmod(0o600)  # the login lets anyone who copies it upload to the channel
    return build("youtube", "v3", credentials=creds)


def uploads_today(out_dir: Path, now: dt.datetime) -> int:
    """How many videos were uploaded on the current UTC day (our own pace cap, config.MAX_UPLOADS_PER_DAY)."""
    day = now.astimezone(dt.timezone.utc).strftime("%Y-%m-%d")
    n = 0
    for m in out_dir.glob("*/meta.json"):
        if str(json.loads(m.read_text()).get("uploaded_at", "")).startswith(day):
            n += 1
    return n


def find_interrupted(yt, meta: dict) -> str | None:
    """An earlier attempt may have reached YouTube before this program wrote the video id down (a crash, a lost connection).
    Look at the channel's ten newest uploads for the same title created after that attempt began, so a retry never sends a second copy."""
    uploads = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    ids = [i["contentDetails"]["videoId"] for i in yt.playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=10).execute().get("items", [])]
    if not ids:
        return None
    for v in yt.videos().list(part="snippet", id=",".join(ids)).execute().get("items", []):
        if v["snippet"].get("title") == meta.get("title") and v["snippet"].get("publishedAt", "") >= meta.get("upload_started", "9"):
            return v["id"]
    return None


def verify_upload(yt, video_id: str, expect: dict) -> dict:
    """Ask YouTube what it actually stored and compare it with what we meant to send: title, privacy, scheduled time, upload status."""
    items = yt.videos().list(part="snippet,status", id=video_id).execute().get("items", [])
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not items:
        return {"ok": False, "problems": ["YouTube does not return this video"], "checked_at": now}
    st, sn = items[0].get("status", {}), items[0].get("snippet", {})
    problems = []
    if sn.get("title") != expect["title"]:
        problems.append(f"title is '{sn.get('title')}'")
    if st.get("privacyStatus") != expect["privacy"]:
        problems.append(f"privacy is {st.get('privacyStatus')}, expected {expect['privacy']}")
    if expect.get("publish_at") and str(st.get("publishAt", ""))[:19] != expect["publish_at"][:19]:
        problems.append(f"scheduled time is {st.get('publishAt')}, expected {expect['publish_at']}")
    if st.get("uploadStatus") not in ("uploaded", "processed"):
        problems.append(f"upload status is {st.get('uploadStatus')}")
    return {"ok": not problems, "privacyStatus": st.get("privacyStatus"), "publishAt": st.get("publishAt"), "uploadStatus": st.get("uploadStatus"),
            "problems": problems, "checked_at": now}


def upload(folder: Path, privacy: str = "private", publish_at: str | None = None) -> str:
    meta = json.loads((folder / "meta.json").read_text())
    if not meta.get("approved"):
        raise SystemExit(f"{folder.name} is not approved. Watch video.mp4, then run: python run.py approve {folder.name}")
    if meta.get("hold"):
        raise SystemExit(f"{folder.name} is on hold. Release it in the dashboard first.")
    if uploads_today(config.OUT, dt.datetime.now(dt.timezone.utc)) >= config.MAX_UPLOADS_PER_DAY:
        raise SystemExit(f"daily upload limit reached ({config.MAX_UPLOADS_PER_DAY} a day)")
    if publish_at and dt.datetime.fromisoformat(publish_at.replace("Z", "+00:00")) <= dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5):
        raise SystemExit("the publish time must be in the future (at least 5 minutes away)")
    if meta.get("video_id"):
        raise SystemExit(f"already uploaded: https://youtube.com/shorts/{meta['video_id']}")
    is_doc = meta.get("format") == "doc"
    tags = " ".join(h for h in config.niche()["hashtags"] if not (is_doc and h == "#Shorts"))
    credits = "\n\nFootage and image credits:\n" + "\n".join(meta["credits"]) if meta.get("credits") else ""
    body = {
        "snippet": {
            "title": meta["title"],
            "description": f"{meta['description']}{credits}\n\n{tags}\n\nNarration is AI-generated.",
            "tags": meta["tags"],
            "categoryId": "27",  # Education
            "defaultAudioLanguage": "en",
        },
        "status": {
            "privacyStatus": "private" if publish_at else privacy,
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,  # honest AI-content disclosure
        },
    }
    if publish_at:
        body["status"]["publishAt"] = publish_at  # RFC 3339, e.g. 2026-10-20T14:00:00Z
    yt = _service()
    if meta.get("upload_started") and not meta.get("video_id"):  # an earlier attempt did not finish cleanly: look before sending again
        found = find_interrupted(yt, meta)
        if found:
            meta.update(video_id=found, uploaded_at=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), publish_at=publish_at)
            (folder / "meta.json").write_text(json.dumps(meta, indent=2))
            print(f"An earlier upload of this video reached YouTube as {found}; not sending it again.")
            return found
    meta["upload_started"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")  # written before the send, so a crash leaves a trace
    (folder / "meta.json").write_text(json.dumps(meta, indent=2))
    req = yt.videos().insert(
        part="snippet,status", body=body, media_body=MediaFileUpload(str(folder / "video.mp4"), resumable=True)
    )
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    meta["video_id"] = resp["id"]
    meta["uploaded_at"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta["publish_at"] = publish_at
    thumb = folder / meta["thumbnail"] if meta.get("thumbnail") else None
    if thumb and thumb.exists():
        try:
            yt.thumbnails().set(videoId=resp["id"], media_body=MediaFileUpload(str(thumb), mimetype="image/jpeg")).execute()
            meta["thumbnail_uploaded"] = True
        except Exception as e:  # usually: channel not phone-verified yet. The video is already up.
            print(f"Thumbnail not set ({e}). Verify the channel at youtube.com/verify, then add it in YouTube Studio.")
    try:
        meta["upload_check"] = verify_upload(yt, resp["id"], {"title": meta["title"], "privacy": body["status"]["privacyStatus"], "publish_at": publish_at})
        if not meta["upload_check"]["ok"]:
            print("WARNING: YouTube stored something different from what was sent: " + "; ".join(meta["upload_check"]["problems"]))
    except Exception as e:  # the video is up; only the read-back failed
        meta["upload_check"] = {"ok": False, "problems": [f"could not read it back: {type(e).__name__}"]}
    (folder / "meta.json").write_text(json.dumps(meta, indent=2))
    return resp["id"]
