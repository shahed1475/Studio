---
name: youtube-publisher
description: Use when a video is about to be uploaded or has been uploaded: confirms readiness, prevents duplicate uploads, and verifies what YouTube actually stored. Never publishes, deletes or changes channel settings without explicit approval.
---

# Publisher

The uploader is `upload.py` (official YouTube Data API). Uploads are private with a scheduled public time (`publishAt`), `containsSyntheticMedia` true, and `selfDeclaredMadeForKids` false.

## Before
`.venv/bin/python .claude/skills/youtube-publisher/scripts/check_publish.py <slug>` fails unless the video is approved, not on hold, reviewed and passed, not already uploaded, inside the daily limit (2), scheduled at least 5 minutes ahead, and has no unfinished earlier attempt.

## During
- The uploader writes `upload_started` before sending. If a retry finds that mark and no video id, it looks at the channel's newest uploads for the same title and adopts that video instead of sending a second copy.
- Never run `upload` twice by hand for the same slug.

## After
- `upload.py` reads the video back and stores `upload_check` in `meta.json` (title, privacy, scheduled time, upload status).
- `.venv/bin/python .claude/skills/youtube-publisher/scripts/verify_upload.py <slug>` asks the API again. Report its real output; a mismatch is reported, not smoothed over.
- Keep the record: video id, metadata, status and errors are in `meta.json`.

## Authority
The owner switched Autopilot on with auto-approve and a 24-hour veto window: scheduled publishing by Autopilot is their standing decision. You, in a conversation, must not publish a video publicly, make a private video public, delete a video, change channel settings, or turn Autopilot on or off without the owner's explicit instruction in that conversation.
