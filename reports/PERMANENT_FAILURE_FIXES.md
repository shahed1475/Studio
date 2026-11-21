# Permanent failure fixes (20 to 21 Nov 2026)

Each row: what failed (or could fail), the root cause, the fix in code, the regression test, and the mutation check that proves the test catches the old behaviour. Earlier rows (20 Nov, 33 production fixes) are in FAILURE_AND_PERMANENT_FIXES.md. Nothing committed.

| # | Failure | Root cause | Fix | Test | Mutation check |
|---|---|---|---|---|---|
| 1 | A cut run could be missed and counted as a failed try | inside a restarted container, a new process can carry the old run's pid | `checkpoint.proc_start`: run alive only with the same boot, pid and process start time | `test_a_restarted_container_that_gives_the_old_pid_...` | pid-and-boot-only: fails |
| 2 | A cut just after a video's record was saved would make the same video again in a new folder | the resume ignored a finished folder | `run._finished_pending` completes the last steps and returns the folder | parametrised film/Short test + "another story" test | no check: 2 fail |
| 3 | A cut during a long film's final pass restarted it from the first frame | one ffmpeg pass for 20+ minutes | `render._assemble_in_parts`: ~2-minute checked parts, sound once, stream-copy join | `tests/test_final_parts.py` | captions not shifted / parts never trusted: fail |
| 4 | Joined parts had colliding timestamps (only with libx264) | parts claimed one frame less than they hold | fixed frame rate per part + exact durations in the join list | parts tests run inside the worker | without both: full decode fails |
| 5 | **Seven Sleepers part 1 came out 60.1 s of 121.7 s** (real production) | `setpts=PTS-STARTPTS` restarts at zero when ffmpeg rebuilds filters at a scene with another pixel format/colour tags (the Blender globe among JPEG stills) | the shift back is the same constant as the shift forward | `test_a_part_whose_scenes_change_pixel_format_keeps_every_frame` (globe-like clip) | STARTPTS: fails |
| 6 | **Every Autopilot documentary crashed after its video was finished** (real production) | `ccdoc.source_lines` assumed spec dicts; Autopilot's sources are text lines | accepts both | `test_source_lines_accept_autopilots_plain_text_sources_...` | dict-only: TypeError |
| 7 | **A 19.1-minute film passed the 20-minute script minimum** (real production) | one word rate (127.8/min, from 9-minute films with many pauses) for every length; long films measured 148.3/min | `scriptgen.words_per_minute`: short films keep the old rate, long films the measured one | `test_the_word_rate_is_the_one_measured_on_a_real_long_film...` | old rate: fails |
| 8 | **The Short's overclaim repair counted a fix that did not happen** (real production: asked to fix line 9, the writer rewrote line 3; the reviewer flagged line 9 again) | `fixer.rewrite_lines` accepted an edit to any line; nothing checked the flagged line afterwards | only flagged lines may be edited; a flagged line still over-certain is softened by rule ("prove" -> "suggest") and only real fixes are counted | `test_a_writer_that_rewrites_another_line_does_not_count...`, `test_soften_...` | no softening / any line accepted: fail |
| 9 | A free judge could be the writer through a router | `openrouter/free` routes to any free model; served model recorded only for the owner's proxy | served model recorded for every reply; a judgement served by a writer is refused | 2 tests in `tests/test_extra_provider.py` | 2 mutations fail |
| 10 | Shorts had no checked stage hand-overs | only films had them | Short script/voice/visuals/render hand-overs; rows carry job, task id, contract, file refs, checkpoint, models | producer tests | - |
| 11 | The recovery scan gave a cut Short the wrong next step | it knew only `pending_doc.json` | `recovery.RESUME_SHORT`, kept parts counted | `test_the_recovery_scan_names_an_interrupted_short...` + agenteval | 3 mutations fail |
| 12 | A resume did not say why scenes were made again (first real resume kept 22 of 81) | no diagnostics | each scene record keeps its source; the resume prints the reason per scene (new, inputs changed, another picture, file changed) | recovery tests still pass | - (diagnostic only; cause still open) |
| 13 | `_keep_line` probed a voice file that does not exist | no existence check | returns when the file is missing | the failing test passes again | - |

## Not fixed (open)
- Why the first resume after a fresh voice kept only 22 of 81 scenes (row 12 will show it next time).
- The subscribe/brand overlay is still one full re-encode that a cut repeats.
- The Seven Sleepers film's invented-facts flags are content, not code: `run.py repair` is the path.
