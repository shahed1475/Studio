---
name: studio-video-finish
description: "Use when a studio video (documentary or Short) must be checked, fixed and made ready: lag or dead air, a weak hook, voice speed and loudness, free 3D (2.5D parallax) and 2D animation, thumbnail, title, description and tags, then a clean review. The step-by-step method with the commands and numbers."
---

# Finish a studio video

The full method, with every command, number and limit, is `docs/studio/FINISHING_A_VIDEO_RUNBOOK.md`. Read it first; this card is the short form.

## Order
1. **State and money** (`video_detail`, `data/video_costs.json`, credit). A picture already in `cache/art/` is free; changing a line's text means a new picture unless you copy the cache file to the new key. Back up the folder to `backups/manual/`. Work inside `autopilot.exclusive()` and `llm.cost_scope(slug)`.
2. **Measure before judging**: words per minute and LUFS of every video, gaps between lines (`studiochecks.longest_gap`), frozen pictures (`studiochecks.freeze_checks`), `.claude/skills/youtube-video-editor/scripts/check_video.py`, then look at frames and say what was seen with times.
3. **Fix the cause**, not the symptom (table in the runbook): voice tail (`voice_tail`), open-question hook, subscribe not follow, loudness (`target_lufs`), free camera motion (`parallax`: depth maps from `tools/make_depth.py`, `parallax.py`), 2D chapter cards and date badges (`graphics`).
3b. **Standing finishing for every video (owner, 30 Oct 2026)**: the Gloamtale subscribe pop-up (`subscribe.py`, on by default, off in user studios; check its moments with `subscribe.moments`), flat gentle zoom for scenes that may show people (`parallax.flat_scenes`, `gentle`), clips fitted once (`render.clip_fit`). Never switch these off to save time; to skip the pop-up for one video set `subscribe_pop` to false in its record.
4. **Packaging** from what ranks (`seo.competitors`) and the thumbnail rules in `DOC_PACKAGING_AND_MOTION_RESEARCH_2026-10-29.md`: one focal point, 2 to 4 words that add to the title and offer a choice, honest, readable at 120 px, versions that differ in one big thing, `thumbscore.score`.
5. **Review** (`run.py review`, the quality-gate skill with `--visual`) and **stop**: the result stays a held draft. Report what changed, the evidence, the tests that ran, what is unverified, risks, and what needs the owner.

## Never
Change the pictures or the script text of a finished video without a reason that is worth a new picture; animate a real archive picture; upload, approve, schedule or release a hold without the owner's word; re-render a video that is on YouTube in place; delete cache files; claim a thumbnail or a motion effect raises views.
