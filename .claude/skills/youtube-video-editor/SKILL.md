---
name: youtube-video-editor
description: Use for edit decisions and technical checks of a rendered video: ffprobe facts, a full decode, caption timing and wording against the script, scene pacing, and how to re-render with ffmpeg.
---

# Video editor and technical check

## Check a render
`.venv/bin/python .claude/skills/youtube-video-editor/scripts/check_video.py <slug> [--quick]` runs ffprobe and a full decode, then checks: duration and size for the format (Shorts 1080x1920, 20 to 180 s; documentaries 1920x1080, 180 to 900 s), frame rate, mean volume (clear speech near -16 dB), black frames, that captions are in order and inside the video, that captions match the script word for word, and that voice timing matches the video length.
A clean ffmpeg exit is not proof of quality. Look at frames: `.venv/bin/python .claude/skills/youtube-research/scripts/inspect.py <slug>`.

## Edit plans
- Pacing: a cut every 4 to 8 seconds for Shorts; the inspection reports the measured mean seconds between cuts.
- Captions: up to 3 words, at most 16 characters a group, bottom position, keywords coloured. Documentary captions keep the script's punctuation and break at clauses.
- Pictures: real public-domain first; AI storybook art only to fill gaps (max 10 per documentary, 4 per Short); no picture more than twice.
- Re-render a documentary from its saved script with `.venv/bin/python run.py redo <slug>`; never edit `video.mp4` by hand. Remember that re-rendering resets review and approval.

## Never
Re-render while the worker is busy with another render without telling the owner; delete cache files by pattern.
