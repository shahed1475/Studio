# Load-shedding and render recovery

20 Nov 2026 (UTC), done in `~/studio`. Nothing was committed, pushed, deployed, approved, scheduled or uploaded. The worker and dashboard were not restarted. No real job was interrupted: both drills ran on throwaway jobs in the session's scratch folder.

## The problem, measured in the code before the change

- `render._render_ungated` rendered every scene again on every run. A cut at scene 70 of 81 meant starting the scene renders from scene 1.
- The final video was written straight to `video.mp4`. A cut during the final pass left a broken file under the finished file's name.
- `tts.narrate` asked the voice service for every line again on every run. The new voice gives slightly different timings, so every scene changed too.
- `data/pending_doc.json`, which holds the saved script (hours of free-model work), was written with `write_text`. A cut during that write could leave half a file, and the script would be lost.
- A power cut used up one of a film's three tries (`MAX_RESUMES`), the same as a real failure.
- `_produce_doc` removed `work/` **before** it saved `meta.json`. A cut between the two left a folder with neither.
- Already safe: drawn pictures (cache by key), Blender stills (cache by spec hash), Blender globe clips (frames kept, re-rendered only when a frame is missing or empty), the subscribe and sound-effect passes (temporary file, then rename).

## What changed

| File | Change |
|---|---|
| `checkpoint.py` (new) | Atomic JSON (write a temporary file, flush it to disk, check it, rename it over the old one, keep `.prev`; reads fall back to `.prev`). SHA-256 and size facts. `check_media` (ffprobe streams, length, a decode of the file's end, or of the whole file). Run markers (pid and boot id, so a run that never recorded its end is seen as interrupted). A per-job `fcntl` lock: the kernel releases it when the process dies, so a stale lock can never block a resume. A disk check (needed space plus a 2 GB margin; nothing is deleted to make room). A memory note. |
| `render.py` | Each scene is written to `segNN.part.mp4`, checked (video stream, length within 2 frames, a decode of its end), renamed into place and recorded in `work/segments.json` with its input key, size and SHA-256. A later run reuses a scene only while its inputs and its file are unchanged. The final video goes to `video.part.mp4`, is decoded in full, checked for audio, video and length, and only then renamed over `video.mp4`. An unchanged finished video is kept. One render per job at a time. No render starts without disk room. |
| `tts.py` | Each voice line goes to `lineNN.part.mp3` and is renamed when complete. Its word timings, size and hash go to `lineNN.json`. A resumed film keeps every finished line and its exact timing, so its scenes stay valid. A changed line, or a damaged file, is made again. |
| `run.py` | `_produce_doc` records its run and its stages (voice, visuals, assembled) in `work/checkpoint.json`. A stop with an error records the end and its reason. A power cut or a kill records nothing, so the next run sees the interruption. When the last run was interrupted, `_cmd_doc` **does not count it as a try**; a real failure still counts. `work/` is removed only after `meta.json` is saved. `pending_doc.json` is written atomically with a fallback copy. New read-only command: `python run.py recover [--thorough] [--json]`. |
| `recovery.py` (new) | Lists every unfinished job folder (has `work/`, no `meta.json`) with: interrupted or not, stages done, voice lines kept, scenes kept and broken, half-written files (never used), and the one safe next step. Read-only. |
| `doctor.py`, `playbooks/doctor.md` | `production_status` adds `interrupted`. The doctor posts one owner task per interrupted film, with `python run.py recover` and the resume step. Per its playbook, the doctor never starts or resumes a render itself: Autopilot already resumes the saved film first (`_pending_doc`), and renders belong to Autopilot's lock. |
| `agenteval.py`, `tests/test_agents_training.py` | New case: a cut film is found, a damaged scene is not trusted, finished folders are skipped, and the scan changes nothing on disk. Two mutation checks. |
| `tools/recovery_drill.py` (new) | The controlled interruption drill below. It refuses to run except in a new, empty folder. |

## Controlled interruption tests (real processes, real ffmpeg)

Throwaway job: 8 scenes × 4 s at 1280×720 with camera moves, plus a 32 s narration. The render ran in its own process group and was killed with **SIGKILL**. SIGKILL allows no clean-up and leaves no end record, which is what a power cut means for this process. Raw JSON output is in the session scratch folder (`drill2/`, `drill.json`). These are the second run's numbers; the first run gave the same result.

| | Drill 1: cut mid-render | Drill 2: cut during the final assembly |
|---|---|---|
| Interruption | SIGKILL after 2 checked scenes (6.9 s) | SIGKILL while `video.part.mp4` was being written (24.7 s) |
| Last valid checkpoint | `segments.json` with 2 scenes | `segments.json` with 8 scenes |
| Checked scenes still valid after the cut | yes (size and SHA-256 match) | yes |
| Half-written files after the cut | none | `video.part.mp4` (never used) |
| `video.mp4` after the cut | absent | absent (no broken file under the finished name) |
| Recovery scan saw "interrupted" | yes, with `python run.py autopilot make doc` | yes |
| Doctor listed it | `doc-drill-1` | `doc-drill-2` |
| Resume | exit 0, 24.9 s: "2 of 8 kept from an earlier run, 6 rendered now" | exit 0, 13.9 s: "8 of 8 kept, 0 rendered now" |
| Scenes re-rendered | none (inode and mtime unchanged) | none |
| Final verification | 32.0 s, video and audio, decodes in full | 32.0 s, decodes in full |
| `.part` files left | none | none |

## Tests that ran

- `tests/test_render_recovery.py`, 13 new tests, all passed. They cover: a second run renders nothing; a cut on scene 3 keeps scenes 1 and 2 and renders only 3 and 4; a truncated scene and a changed picture are made again while the others are kept; a cut during assembly leaves no finished-looking file; a changed finished video is assembled again; a second render of the same job is refused; no render starts on a full disk and nothing is deleted; the state file falls back to `.prev`; an interrupted run is told apart from a finished one; voice lines survive a cut with the same timing; a power cut does not use a try but a real failure does; a half-written saved script falls back to its previous copy; the recovery scan.
- In-memory mutation checks (nothing written to the live files). Each of the following was caught by failing tests: trust any recorded scene (3 failed); skip the media check (1 failed); count every try (3 failed); write state non-atomically (2 failed).
- Neighbouring suites (renderer, animation, voice, doctor, a2a, resume and others): 118 passed. Three existing tests were adapted because they stub ffmpeg and write no files: `test_animation.py` and `test_smooth_people_and_no_loops.py` now ignore the refusal, or give the stub a file; `tts.py` tolerates a test voice that writes nothing.
- Agent training and playbook tests: 82 passed. The doctor brief is 1,386 characters and still contains its Never section.
- Full suite: see the result appended at the end of this report.

## Acceptance criteria

- [x] Render progress is saved persistently (`segments.json`, `checkpoint.json`, voice-line records, all atomic).
- [x] Completed scenes survive a killed worker process (drill 1). A Docker restart kills the same way.
- [x] Incomplete outputs are detected (`.part` names, ffprobe, the decode check, size and SHA-256).
- [x] Corrupted outputs are not accepted (truncated-scene test, drill 2's half final file).
- [x] Autopilot continues the interrupted film (`_pending_doc` resumes first, and the cut does not use a try).
- [x] The doctor guides safe recovery (interrupted list, owner task, exact commands). It never renders itself.
- [x] Blender resumes safely (stills and globe clips were already cached by spec hash; nothing changed there).
- [x] FFmpeg assembly can be retried safely (drill 2).
- [x] Duplicate rendering is prevented (per-job lock; Autopilot's lock as before).
- [x] Controlled interruption tests pass (both drills).
- [~] A documentary resumes without repeating finished work: proven on the throwaway job, **not yet on a real 20 to 26 minute film**. The first real resume should be watched (see below).

## Remaining limits (honest)

- **A real power cut was not tested.** SIGKILL covers the process. It does not cover a file system losing writes that had not yet reached the disk. State files are fsynced. Scene files are not fsynced, but each is checked against its SHA-256 before reuse, so a lost write means the scene is made again, never trusted.
- The Seven Sleepers film waiting in `data/pending_doc.json` has voice lines made before this change, which have no records. Its next run (planned for 00:12 UTC) makes its voice once more, then everything is kept from that run on. Its drawn pictures are cached and are not drawn again.
- Shorts start a new folder on every make, so a cut Short is made again from the start. A Short is about a minute long and its pictures are cached, so this was left as it is.
- When a resumed film finds too few on-topic pictures, `_produce_doc` still removes `work/`, kept scenes included, as before. This happens before any render, and the voice is free to make again.
- The final pass (subtitles burned in, loudness) is one ffmpeg run. A cut inside it repeats that pass from the kept scenes. It cannot resume half way.
- Disk space is checked before a render starts, not watched during it. A disk that fills mid-render fails that scene's check, and the scenes before it are kept.
- No GPU check: the studio renders on the CPU (Blender Cycles on the CPU, ffmpeg).
- Render quality is unchanged: no profile lowers the owner's final quality.

## Needs the owner

- Nothing here publishes or spends anything. The changes are live in `~/studio` (new `run.py` processes use them), uncommitted.
- Committing is your call. These files go with the rest of the uncommitted 20 Nov work: `checkpoint.py`, `recovery.py`, `tools/recovery_drill.py`, `tests/test_render_recovery.py`, and the edits to `render.py`, `tts.py`, `run.py`, `doctor.py`, `playbooks/doctor.md`, `agenteval.py`, `tests/test_agents_training.py`, `tests/test_animation.py` and `tests/test_smooth_people_and_no_loops.py`.
- The first real recovery: after the next real cut, run `python run.py recover` before anything else, then let Autopilot continue (or run `python run.py autopilot make doc`). Send me the output and I will check that the kept scenes were not rendered again.

## Full suite result (20 Nov 2026, about 18:30 UTC)

- First run: 2,747 passed, 4 failed, 11 skipped. Three of the failures were more tests that stub ffmpeg and write no files (`test_editprofile.py` twice, `test_motion.py`). They now give the stub a stand-in file and pass. The fourth, `test_freemodels.py::test_paid_claude_is_used_while_credit_lasts`, passes alone and in its own file. It tests the model router, which this work did not touch, and is recorded here as a possible order-dependent flake.
- Second run: **2,752 passed, 0 failed, 11 skipped** (the same 11 explained skips as before).
