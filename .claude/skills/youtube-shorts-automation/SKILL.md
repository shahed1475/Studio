---
name: youtube-shorts-automation
description: Use when making, reviewing or uploading YouTube Shorts with this project's pipeline (ideas, make, approve, upload), or changing the niche, voice or footage settings.
---

# YouTube Shorts automation

Project root: run everything with `.venv/bin/python run.py ...`.

- `ideas N` queues topics (topics.json). `make [topic]` writes output/<slug>/{video.mp4,meta.json}.
- Never upload before the user has watched the video. `approve <slug>` then `upload <slug>` (private by default).
- Niche, audience and tone live in niche.json; voice/model/Pexels key in config.py or env (YT_VOICE, YT_MODEL, PEXELS_API_KEY).
- Policy guardrails (keep them): each video needs a specific tip, human approval, AI disclosure on upload, max 5 uploads/day.
- This ffmpeg lacks libx264; render.py falls back to libopenh264.
