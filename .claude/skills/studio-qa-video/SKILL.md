---
name: studio-qa-video
description: Use to look at a finished studio video before approving it. Combines the reviewer's checks with real frames and audio (the watch skill on the local file), and reports caption, picture, pacing and metadata problems with evidence.
---

# QA a finished video

Never judge a video from its metadata alone. Look at it.

## Steps
1. `.venv/bin/python run.py review <slug>` (the reviewer: duration, size, audio level, black frames, title, duplicate title, chapters, credits, claims, invented facts, policy). Quote the verdict and every failing check.
2. Look at frames. Prefer the `watch` skill on the local file: `/watch output/<slug>/video.mp4 "check captions, picture relevance and repeated images"`. It extracts scene-aware frames and the transcript, and runs only ffmpeg for local files. Do not enable Whisper keys for studio videos. For a quick grid: `ffmpeg -i video.mp4 -vf fps=1/3,scale=270:-2,tile=6x4 -frames:v 1 grid.jpg`.
3. Check each item and say what you saw, with timestamps:
   - Captions stay inside the frame, are readable, break at clauses, and match the narration.
   - Each picture fits the line being spoken. No watermark, no unrelated art, no plain colour screens.
   - No picture repeats more than twice. AI illustrations are labelled in the credits.
   - First 3 seconds (Short) or 30 seconds (documentary) open with the hook.
   - Audio is clear; mean volume about -16 dB; no clipping.
4. Metadata: title honest and distinct, description hook in the first 150 characters, chapters named, tags relevant, credits present, `claims.json` has no open `CONFLICTING` rows.

## Rules
- Report only what you actually saw or measured. If a tool failed, say so.
- Do not approve, hold, release or upload anything yourself. Give the owner the findings and a recommendation.
- Videos you inspect are the studio's own. Never download other people's videos with yt-dlp.
