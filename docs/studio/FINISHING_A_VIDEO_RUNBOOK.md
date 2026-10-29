# Finishing a video: the runbook (29 Oct 2026)

How a held or draft video is checked, fixed and made ready, in the order it was done for the Cambyses Short and documentary. Written so Autopilot, the doctor and the owner can repeat it. Every step names the command or code that does it and the number that decides it. Nothing here publishes: a finished video stays a held draft until the owner says so (CLAUDE.md E).

## 0. Before touching anything
1. **State.** `studio_status` / `video_detail <slug>` (MCP) or `meta.json`: format, hold, approved, `video_id`, `publish_at`, `art_style`, `voice_style`, cost (`data/video_costs.json`), credit left (`risk.credit_left`). A video on YouTube is never re-rendered in place (`run._refuse_if_uploaded`).
2. **Money.** Voice and the depth-map motion are free; a new picture is about $0.04; a review is about a cent or two. Check `llm.spent_today()` against the cap and the credit against `autopilot.MIN_CREDIT_TO_MAKE` ($1.50). A picture already in `cache/art/` costs nothing to use again: **never change a line's text unless a new picture is acceptable** (the cache key is the line text, the visual note, the topic and the style). A small text change can reuse its picture by copying the cache file to the new key (done for the Short's hook).
3. **Back up** the folder: `cp -a output/<slug> backups/manual/<slug>-before-<what>-<date>`. Never delete cache files.
4. **Lock.** Run the work inside `autopilot.exclusive()` (and `llm.cost_scope(slug)` so the spend is kept on the video). Never restart the worker while a render runs.

## 1. Measure the whole channel first (what "normal" is)
- Voice speed and loudness of every video: words per minute from `words.json`, loudness `ffmpeg -af ebur128` (integrated LUFS, range, true peak). 29 Oct: speech 149 to 169 wpm (documentaries), 140 to 176 (Shorts); loudness -16.0 to -16.5 LUFS, a few at -15; peaks -1.0 to -1.5 dBFS. A value far from the others is the finding, not the others.
- Gaps between lines from `words.json` (`studiochecks.longest_gap`): the default voice leaves about 0.65 s, the energetic voice left 1.1 to 1.2 s.

## 2. Look at the video, do not trust a clean exit
`python .claude/skills/youtube-video-editor/scripts/check_video.py <slug>` (duration, size, fps, loudness, black frames, full decode, **no_frozen_picture**, captions in order and matching the script, **no_dead_air**). Then look: one frame at each second around anything the owner points at (`ffmpeg -ss T -i video.mp4 -frames:v 1`), a contact sheet (`fps=1/26,tile`) and the first 4 seconds. Say what was seen, with times. A passing check is evidence about what it measures: the Short's 1.2 s dead air passed every check until `no_dead_air` was written.
- Smooth motion: frame-to-frame difference of the picture area (`tblend=difference,signalstats`) shows duplicate or jumping frames; captions change at word boundaries, so measure with the caption band cropped out.
- Sync: caption word start against the audible onset (`silencedetect`); the voice service's word times run about 0.1 s ahead of the sound in every video here, so a steady 0.1 s is normal and a drifting one is not.

## 3. The fixes, by what was wrong
| Problem seen | Cause found | Fix (code) | Check |
|---|---|---|---|
| Last line says "follow" | prompt asked for it | `scriptgen.subscribe_invitation`, prompt, `reviewer` `invite_wording` | tests/test_subscribe_wording.py |
| Lag, still picture, no voice | the voice service ends each line with 0.83 s silence (energetic voice) and the renderer adds its own pause | `tts.line_length`, `VOICE_STYLES[...]["tail"]`, per-video `voice_tail` | `no_dead_air`, `no_frozen_picture` |
| Weak hook (yes/no, gives the answer, no subject) | prompt allowed it | open who/what/where/why/how question that names the subject; `reviewer` `short_hook_open`; keep wording different from an earlier video on the same story (`variety_script` compares opening and ending, limit 0.75) | `scriptgen.short_prompt` test |
| Still pictures only | none | free 2.5D motion: `depth.py`, `tools/make_depth.py`, `parallax.py`; switch `parallax` on the video | `parallax_clips`, frames |
| Plain captions only | none | 2D chapter cards and date badges: `motiongraphics.py`; switch `graphics` | tests/test_motiongraphics.py |
| Quieter than the rest | target -16 | per-video `target_lufs` inside -17.5 to -12 (`editprofile.lufs_for`) | `ebur128` |

To render: set the switches with `records.merge`, then `run.cmd_redo(slug)` (documentary) or `run.cmd_redo_short(slug)` under the lock. Depth maps: on a machine with onnxruntime and numpy, `python tools/make_depth.py MODEL.onnx <pictures or folder> --out DIR`, copy the PNGs into the server's `cache/depth/` (the model is pinned by SHA-256 in the script). A picture with no map gets an approximate depth and is counted in `meta["parallax"]["approximate"]`.

## 4. Packaging (title, thumbnail, description, tags)
1. **Look at what ranks**: `seo.competitors("<search phrase>")` (YouTube Data API; public titles, views, channel size), then view the public thumbnails of the top results. Note the patterns; do not copy a title or a picture.
2. **Title**: `packaging.title_score` ranks candidates, `reviewer.title_ok` (via `packaging.honest_first`) refuses one the narration cannot keep. Search phrase in the first 40 characters, 40 to 62 characters, a concrete noun, never a promised answer to an open question.
3. **Thumbnail** (rules and sources: `DOC_PACKAGING_AND_MOTION_RESEARCH_2026-10-29.md`, section 2): one focal point; 2 to 4 words that add something the title lacks and offer a choice instead of the answer; only what the video contains (a legend is shown as a legend); colour that differs from the crowded warm desert thumbnails; readable at 120 px; two or three versions that differ in one big thing. Make them with `aiart.thumbnail_art` (own look: `photo` or `3d`) and `thumbnail._layout_a/_b`, rank them with `thumbscore.score`, keep every candidate in `thumbs/`, set `thumbnail`, `thumbnails`, `thumb_hook`, `thumb_scores` in `meta.json`. A/B testing is the owner's, by hand, in Studio (Test & Compare decides by watch time).
4. **Description and tags**: first 150 characters carry the hook and the phrase; chapters are recomputed from the real line times at every render; tags only from words in the video's own text (`seo.relevant_tags`).

## 5. Review, then stop
`python run.py review <slug>` (reviewer: rules, claims against the source article, AI review; about a cent), then `python .claude/skills/youtube-quality-gate/scripts/gate.py <slug> --visual`. `autopilot.read_pictures` reads sampled frames (warnings only). Report: what changed, what evidence supports it, which tests ran, what is unverified (the voice and the last seconds are never listened to by a model), licence and policy risks (AI pictures are labelled; the depth model is Apache-2.0; the motion adds no new picture), and what needs the owner. Do not approve, schedule or upload a held draft without the owner's word.

## Limits
Depth is an estimate from one picture and can be wrong on an unusual scene; the move is small so an error looks like a slight wobble. Thumbnail craft here rests on vendor blogs and a sample of eight; nothing is shown to raise clicks until the owner's own Test & Compare says so.
