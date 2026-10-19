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
    return build("youtube", "v3", credentials=creds)


def uploads_today(out_dir: Path, now: dt.datetime) -> int:
    """How many videos were uploaded on the current UTC day (the API quota and the 5-a-day policy)."""
    day = now.astimezone(dt.timezone.utc).strftime("%Y-%m-%d")
    n = 0
    for m in out_dir.glob("*/meta.json"):
        if str(json.loads(m.read_text()).get("uploaded_at", "")).startswith(day):
            n += 1
    return n


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
    (folder / "meta.json").write_text(json.dumps(meta, indent=2))
    return resp["id"]
