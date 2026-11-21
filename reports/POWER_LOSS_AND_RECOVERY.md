# Power loss and recovery (21 Nov 2026)

Builds on `LOAD_SHEDDING_AND_RENDER_RECOVERY.md` (20 Nov). Work done in `~/studio`. Nothing committed, pushed, approved, scheduled or uploaded.

## 1. A real power cut, checked (evidence, not a drill)
- The PC lost power at about 18:53 UTC on 20 Nov (`last -x`: a boot at 00:53 Dhaka with no shutdown record for the previous boot; `journalctl --list-boots` shows boot -1 ending without a clean stop). The containers came back by themselves.
- Nothing was rendering at the moment of the cut, so this was **not** a test of a render resume. It was a test of every saved state file:
  - All **839 JSON state files** under `data/`, `output/` and the studio root parsed after the cut (0 empty, 0 broken). Script used: a read-only parse of every `*.json`.
  - No `.part` (half-written) file anywhere in `output/` or `data/`.
  - `python run.py recover` in the worker: "No unfinished render found" (true: the Seven Sleepers film waits in `data/pending_doc.json` at its picture checkpoint, before any render).
  - `data/pending_doc.json` (the 81-line, 2,839-word film script, hours of free-model work) survived and parses.
- Limit: a real cut **during** a render on this PC has still not happened. The drills below use SIGKILL, which is what the cut does to the process; they do not cover the disk losing writes that were never flushed (scene and part files are verified by SHA-256 before reuse, so such a loss means a re-render, never a bad file trusted).

## 2. Defects found in the recovery code today, and fixed
| # | Defect (found by reading the code or by a drill) | Fix | Test / mutation check |
|---|---|---|---|
| R1 | A run was "still alive" when the same boot and its pid existed. Inside a restarted container pids start again from 1, so a new process could carry the old pid: a cut would be missed and counted as one of the film's three tries. | `checkpoint.proc_start` records the process start time (`/proc/<pid>/stat` field 22); `_run_alive` needs boot, pid **and** start time. Old records without it are judged as before. | `test_a_restarted_container_that_gives_the_old_pid_to_a_new_process_still_counts_as_a_cut`; mutation "pid and boot only" fails it. |
| R2 | A cut after `records.save` but before the saved script was cleared left both. The resume saw `meta.json`, passed no folder, and the producer made the **same film or Short again in a new folder** (a duplicate). | `run._finished_pending`: when the saved video's own folder has its record and video (same title, or same topic after a title polish), the resume finishes the two missing steps (removes `work/`, clears the saved script and its `.prev`) and returns that folder. | Parametrised test for film and Short; a second test: a folder holding another story is not taken as finished. Mutation "no finished-folder check": 2 tests fail. |
| R3 | The final pass of a long film was one ffmpeg run (tens of minutes for 22 minutes of 1080p). A cut inside it repeated the whole pass. | `render._assemble_in_parts` (films of 240 s or more, no dissolves): about 2-minute parts, captions and grain burned in at the part's place in the film's time, each part written to `.part`, checked, renamed and recorded (key, size, SHA-256); the sound (narration, music bed, loudness) made once; the parts joined by stream copy. Shorts keep their single pass. | `tests/test_final_parts.py` (5 tests, real ffmpeg): same picture and caption frames as the single pass, exact frame count, a cut between parts keeps the finished parts, a damaged part or new captions are made again. Mutations "captions not shifted" and "a recorded part never trusted" fail them. |
| R4 | Found by drill 3 at full size, **not** by the host tests: in the worker (libx264 with B-frames) each part claimed to be one frame short (119.967 s for 3,600 frames), so every join put two frames on one timestamp ("non monotonically increasing dts"). The full-decode check refused the file, so no broken film was accepted, but the film would not have finished. The host's Fedora ffmpeg has only openh264 and could not show it. | Parts are encoded at a fixed rate (`-fps_mode cfr -r 30`) and the join list gives each part's exact length (`frames / 30`). | The parts tests were run **inside the worker** (25 passed); a mutation removing both fixes fails the full-decode check there. |
| R5 | The recovery scan told the owner a cut Short "starts a new folder", but Shorts resume in their own folder from `data/pending_short.json` (this was already in the code; the report of 20 Nov was out of date). | `recovery.RESUME_SHORT` for the saved Short's folder; kept final parts and the sound are counted and reported. | `test_the_recovery_scan_names_an_interrupted_short_...`; agenteval case below, mutation "a Short gets the film's step". |
| R6 | `tts._keep_line` probed a voice file that does not exist (a test's stand-in voice), and one existing test failed in the current tree. | It returns at once when the file is missing. | The test passes again. |

Agenteval: `case_a_cut_at_the_very_end_never_makes_the_video_twice_and_a_cut_short_resumes_in_its_folder` with three mutation checks in `tests/test_agents_training.py`.

## 3. Controlled interruption drill 3 (worker container, real ffmpeg, libx264)
Throwaway job in the container's `/tmp`: 10 scenes x 30 s at 1280x720, burned captions every 5 s, loudness -16. The render ran in its own process group and was killed with **SIGKILL** while part 2 of the final pass was being written. Tool: `python tools/recovery_drill.py <empty folder> 3`.

| | First run (before R4) | After R4 |
|---|---|---|
| Cut after | 92.8 s | 90.4 s |
| Recorded before the cut | 10 scenes, part00 | 10 scenes, part00 |
| Half-written file after the cut | `part01.part.mp4` (never used) | `part01.part.mp4` (never used) |
| Scan / doctor saw it | yes / yes | yes / yes |
| Resume | exit 1: final join refused by the full-decode check (R4) | exit 0 in 53 s: "10 of 10 kept, 0 rendered now", "3 parts: 1 kept, 2 made now" |
| Final film | none (correctly refused) | 300.0 s, **9,000 frames counted by a full decode** (= 300 x 30), 0 decoder messages |
| Captions | - | frame at 152.5 s (inside part 2) shows "Caption at 151 seconds": the captions sit at the film's own time |

Drills 1 and 2 (20 Nov) still describe the scene and single-pass behaviour, which is unchanged for Shorts.

## 4. What still repeats after a cut (honest limits)
- The subscribe pop-up and channel mark (`subscribe.apply`) are a second full-length encode of the finished film (veryfast). A cut inside it repeats that pass (about 10 minutes for 22 minutes at 1080p, estimated, not measured). Folding the overlays into the parts would remove one encode and make it resumable; not done today (it changes the branded overlay code).
- A cut after the overlay but before the record is saved re-joins the parts (seconds) and repeats the overlay.
- Shorts: one final pass of about a minute; a cut repeats it.
- Voice lines made before 20 Nov have no records (the Seven Sleepers film's voice is made once more on its next run).
- No GPU check: renders are on the CPU (the GTX 1050 Ti driver does not load on kernel 7.3.4).

## 5. Owner
- Nothing to approve for this work; it is uncommitted in `~/studio` and live for every new `run.py` process.
