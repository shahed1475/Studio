# Cambyses documentary: 3D and 2D motion, packaging, and a repeatable finish (plan, 29 Oct 2026)

> **For agentic workers:** execute task by task (`superpowers:executing-plans`); steps use checkboxes.

**Goal:** Finish "The Lost Army of Cambyses, Said to Vanish in 525 BC" (held draft, 468 s, 48 realistic AI pictures already paid for) as a documentary with free 2.5D camera motion and 2D animated graphics, a better thumbnail, search packaging and a clean review, then store the method so Autopilot can repeat it.

**Architecture:** Pictures stay exactly as they are (same cache files, no new picture cost). A depth map per picture (Depth Anything V2 Small, made once on a machine with the model, stored as a small picture in `cache/depth/`) drives a mesh warp in Pillow, piped to ffmpeg as one clip per scene; `render.render` already accepts video clips. 2D graphics are extra events written into the burned-in ASS captions. Voice, loudness and review go through the existing paths with per-video settings.

**Tech Stack:** Python, Pillow (already on the server), ffmpeg (already), ONNX Runtime on the PC only for the depth maps.

**Spec:** `docs/studio/DOC_PACKAGING_AND_MOTION_RESEARCH_2026-10-29.md` and `docs/studio/VIDEO_CRAFT_RESEARCH_2026-10-29.md`.

## Global Constraints
- Do not change the pictures or the script text (a changed line is a changed picture prompt and costs a new picture). Credit left is about $2.00; the video has already cost $2.37.
- Nothing is made public, uploaded or approved: the result stays a held draft until the owner says so (CLAUDE.md E).
- No new dependency on the server (`requirements.txt` unchanged). Only drawn (AI) pictures are given motion; real archive pictures never are (creator playbook).
- Back up the video folder before an in-place re-render; never delete cache files; never restart the worker while a render runs; hold the Autopilot lock (`autopilot.exclusive`).
- Every new rule gets an `agenteval` case with a mutation check; the creator playbook brief must still end with its Never section (1,500 characters).

## Review Focus
- A picture with no depth map (new videos): approximate depth, labelled, still looks fine.
- A scene shorter than a second, or a repeated picture: no seam, a different camera move.
- A narration line with two dates, or "1970s", or "50,000": only a real year in the line becomes a badge.
- Two graphics at once (chapter card and badge) or graphics over the hook: never.
- The render uses the same loudness, captions and chapter times as before the change.

## Tasks
- [ ] **T1 `depth.py`** (`depth_key(path) -> str`, `load_depth(path) -> Image|None`, `approximate_depth(size) -> Image`, `depth_for(path) -> (Image, "model"|"approximate")`) + tests: key is stable and content-based, a stored map is found, the approximate map is far at the top and near at the bottom.
- [ ] **T2 `tools/make_depth.py`** (run on a machine with onnxruntime, numpy and the model; refuses a model whose SHA-256 differs from the pinned one) and run it for the 48 pictures; copy the maps to the server `cache/depth/`.
- [ ] **T3 `parallax.py`** (`camera(move, t)`, `mesh(...)`, `render_clip(...)`, `apply(clips, durations, size, data) -> (clips, stats)`) + tests: camera path ends where it should, mesh stays inside the source, a real 1 s clip is encoded and has the right size and length, a cached clip is reused, only cache pictures are animated.
- [ ] **T4 `motiongraphics.py`** (`graphics_events(data, durations, size) -> list[str]`, `add_to_ass(path, events)`) + tests for the five Review Focus lines above.
- [ ] **T5 wiring**: `tts.narrate(..., tail=)` for any video (`voice_tail`), per-video `target_lufs` for a documentary, `data["parallax"]` and `data["graphics"]` switches in `_produce_doc` and `_produce_short`, reviewer check that a parallax video's clips cover its scenes; tests.
- [ ] **T6 render** the documentary in place (backup first, Autopilot lock), then check: `check_video.py`, motion analysis, frames before and after, chapter times, loudness (-14), dead air, captions.
- [ ] **T7 packaging**: thumbnail (brief from the research, 2 versions on the 3D army picture and one realistic, scored, 120 px test), title and description and tags through the studio's SEO code, full reviewer, picture reading.
- [ ] **T8 store the method**: `docs/studio/FINISHING_A_VIDEO_RUNBOOK.md`, skill `studio-video-finish`, CLAUDE.md note, `agenteval` cases with mutation checks, lessons, memory.
- [ ] **T9 deploy** (`deploy/clean_check.sh`, push, `deploy.sh dry-run-first`) and report: what changed, evidence, tests, what is unverified, risks, what needs the owner.

## Not in this plan
Uploading or scheduling the documentary; changing the script; the default loudness of every video (owner's call: the channel is bedtime listening); a server job that makes depth maps (needs the owner's yes for onnxruntime and numpy); paid animation clips.
