# Autopilot production test (20 Nov 2026)

## How Autopilot was run, and why this way
- Autopilot's own switches (autopilot.json, not changed): `enabled` false, `auto_approve` true, `pause_scheduling` false, `make_videos` true, house style `photo`.
- A full tick with Autopilot on would, at 08:23 UTC, have done: review Devil's Bible, **approve and schedule "doc-the-lost-colony-of-roanoke"**, review two Shorts (dry run of `plan_actions` with `enabled` forced true, nothing executed). The owner's mission forbids any approval, scheduling or upload, so no full tick was run.
- The planner saw no empty slot (`needs` = 0 documentaries, 0 Shorts): a normal tick would not have made anything. The two videos were made on the owner's explicit order.
- New command `python run.py autopilot make short|doc` (`autopilot.make_one`): Autopilot's own `make_short` / `make` executor under the Autopilot lock, with the governor's weekly caps (doc 4, short 7 this week), the pace guard and the storage check, then the reviewer's own review. It never approves (Autopilot's `do_review` approves a pass when auto_approve is on, so the reviewer is called directly), never schedules, never uploads. Tests: tests/test_supervised_make.py.

## Execution path traced (code and live logs)
1. Topic: `run._best_topic` -> pinned topic first, else `topicrank.pop_best(fmt, want_kind)` (research signals + search demand, source article must exist, premise screen by a free model, duplicate-story screen). Live: "Tenali Rama" (Short) and "Seven Sleepers" (documentary) chosen by it; each choice is in the activity feed with its score.
2. Script: `scriptgen.script` (Short) / `scriptgen.doc_script` (documentary: outline, chapters, length extension, saved draft, chunked fact-check by two free judges that never include a writer, length loop, line join), then `run._script_gate` (script reviewer).
3. Hand-overs checked between stages (`a2a.handoff`: script, voice, visuals, render).
4. Voice: edge-tts (free), word-timed captions.
5. Pictures: approved archives first (named real photos in the photo look), then free FLUX drawings on Cloudflare; Blender scenes where true to the line; 2.5D camera motion from depth maps; music bed.
6. Render (ffmpeg), subscribe pop-up and channel mark, sound cues, captions, chapters in the description.
7. `autopilot.finish_video`: SEO research, titles ranked and checked by the reviewer's own title check, tags, thumbnail (documentary).
8. Review: rule checks + two free judges + claim ledger; the verdict and checks are saved in the record.

## Results
| Video | Topic (source) | Made by | Review | Approved / scheduled / uploaded |
|---|---|---|---|---|
| the-true-story-of-tenali-rama (Short) | Tenali Rama (topicrank, score 3.648) | `autopilot make short`, 08:27-08:44 UTC | pass, then needs_human after the new overclaim check (line 10) | no / no / no |
| Seven Sleepers (documentary) | Seven Sleepers (topicrank at 08:44, pinned for each restart) | `autopilot make doc`, runs 1-6 | see DOCUMENTARY_PRODUCTION_REPORT.md | no / no / no |

## What failed while Autopilot ran, and what changed (details in FAILURE_AND_PERMANENT_FIXES.md)
Run 1: judges could not answer a 90-line fact-check (fixed: chunks, patience). Run 2: no free writer could answer (fixed: thinking budget). Run 3: 15.4 minutes after the check (fixed: length loop). Run 4: writers rotated across six models and left no free judge; the draft was in memory only (fixed: sticky writer, saved draft). Run 5: 119 short lines, one picture each (fixed: line join). Also found: a judge request held 600 s (fixed: total deadline), free_models.json wiped by concurrent writers (fixed: atomic, locked).
