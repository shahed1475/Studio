# Power-outage recovery checkpoint (24 Nov 2026)

Recovery started 15:07 UTC (PC booted 14:52 UTC; local clock is UTC+6). Work only in ~/studio; the Desktop workshop was not read or changed.
Nothing committed, pushed, deployed, uploaded, scheduled, published or approved by this session.

## 1. What the outage interrupted
- Power lost between 14:45:42 UTC (last worker job: `health`) and 14:52:54 UTC (`worker started`).
- No Claude session was working at the cut. The previous session (transcript b0213166) finished its last task, the model and compute routing mission, at 04:37 UTC with the full suite green (3,084 passed, 11 skipped) and the final report sent; nothing ran after its 05:32 UTC context summary.
- Interrupted: only the worker's routine ticks (autopilot, specbuild, recheck, guardian, unstick, health), all re-run since. No render, voice, picture or model job was running: no pending_doc/draft/short, `autopilot.lock` empty, logs show only routine ticks after 06:17 UTC.

## 2. Last confirmed completed tasks
| Item | State found (inspected, not assumed) |
|---|---|
| Compute/model routing (04:37 UTC) | Completed and verified (full suite then). Uncommitted. |
| Mary Celeste UGC Short | **Built 04:20 UTC** by specrun (the 03:28 UTC report still said "waiting"). Held, `approved: false`, `hold: true`. MP4 checked by this session (below). |
| Seven Sleepers documentary | Rendered 02:13 UTC (MP4 unchanged since). **Approved at 06:15 UTC by the reviewer agent (auto_approve)** after a two-family AI review passed (gemini-3.5-flash-lite [google] + glm-4.7-flash [zhipu], risk 0/10). Not uploaded, no publish time. `pause_scheduling: true` is the only thing keeping it from a slot. |
| Voice lab | Chatterbox-Turbo downloaded (3.8 GB, no partial files), smoke tests run 23 Nov (2 samples). `recordings/` empty, no `PERMISSION.txt`: personal voice BLOCKED. |
| Kaggle | BLOCKED_PENDING_TERMS_REVIEW (non-commercial terms); worker off; nothing sent. Model inventory exists (data/compute/models.json). |
| Cloudflare | Account marked spent for 24 Nov by its own 429/4006 (data/cloudflare_account_spent.json, 02:40 UTC); studio counter 3,542.8 Neurons. Free again 00:00 UTC 25 Nov. |

## 3. Defect found during recovery and fixed
- `autopilot.read_pictures`: when the vision model could not run (Seven Sleepers, 06:17 UTC: OpenRouter 429), it stored `visual_check.ok = true`, so a film with a wrong-place picture (scene 67) and garbled AI lettering (52, 54) counted as picture-checked when it was approved.
- Fix (autopilot.py): a reading that cannot run (an error row or an exception) is stored as `ok: false, ran: false` with its reason, and still never blocks (the documented behaviour). A real reading stores `ran: true`.
- Tests: tests/test_autopilot.py (extended + 1 new), agenteval case `case_a_picture_reading_that_could_not_run_is_never_recorded_as_a_pass` + 2 mutation checks (tests/test_agents_training.py). Related suites 211 passed.
- Not changed: the Seven Sleepers record (its approval and stale `visual_check.ok: true` stay as Autopilot wrote them; owner decision below).
- Note: ~/studio is the running studio, so this edit is live for the worker's next tick.

### Second fix: 44.1 kHz audio
- Cause: render.AUDIO encodes at 48 kHz (finish commit ea0034e), but `sfx.apply`, the last audio pass on every film and Short, mixed at `aformat=sample_rates=44100`, so every finished video came out 44.1 kHz (Seven Sleepers, Mary Celeste UGC).
- Fix (sfx.py): the mix runs at 48 kHz with `-ar 48000`; the cached effect files are resampled in the mix (no cache touched).
- Test: tests/test_sfx.py real-film test asserts 48000; mutation check: the same test against the HEAD sfx.py fails with `'44100' == '48000'`. test_sfx 9 passed.
- Videos already rendered are not changed.

## 4. Mary Celeste UGC Short (inspected)
- ffprobe: 60.43 s, 1080x1920 H.264 30 fps, AAC 44.1 kHz stereo, 44.7 Mbit/s (338 MB, very high for a Short; YouTube accepts it).
- `studiochecks.py video`: 13/13 ok (decode, captions 100% match, no dead air over 0.5 s, no frozen picture).
- One frame per scene looked at (12 frames; nothing else watched): 12 different AI pictures, no garbled text. Scene 1 shows a three-masted ship; the Mary Celeste was a two-masted brigantine (minor accuracy note).
- No duplicate build triggered; specrun status `built`.

## 5. Seven Sleepers: remaining work and budget (not started)
- Problems still in the MP4 (unchanged): last third replays pictures (60 unique / 93), scene 67 wrong place, garbled text 52/54, 1,095 s (18.3 min) under the 20-26 min target, audio 44.1 kHz.
- Budget: about 28 new drawings (variety to ~85+/93 and 3 redraws) at ~104-156 Neurons each = ~2,900-4,400 of the 9,000 daily cap. The per-film limit today is 16 + 12 variety extra (aiart.MAX_PER_VIDEO, EXTRA_FOR_VARIETY).
- Blocked until 00:00 UTC 25 Nov (Cloudflare account spent). Lengthening to 20-23 min also needs new lines, two-family fact-check rounds and re-voicing.

## 6. Tests this session
- Related: test_autopilot, test_agents_training, test_records, test_risk, test_fixes: 211 passed (2 lock tests need to run outside the sandbox; they pass there).
- Full suite: 3,086 passed, 11 skipped, 0 failed (twice; see section 8).

## 7. Owner decisions
1. Seven Sleepers is approved with known picture defects: withdraw the approval (or hold it) until the re-render, or leave it (pause_scheduling still blocks a slot)?
2. Re-render plan after 00:00 UTC: raise the per-film drawing limit to ~28-32 for this film, fix 52/54/67, and lengthen to 20-23 min (new script lines, fact-check, re-voice)?
3. 48 kHz audio: fixed in code for new renders (section 3); the Seven Sleepers re-render will come out at 48 kHz.
4. Commit the uncommitted work (19 modified + compute files + this fix); push the 4 local commits.
5. Voice: recordings + PERMISSION.txt.
6. Kaggle: no task permitted (recommendation: keep it so for the channel).

## 8. Next recovery point
- Full suite, run twice (the second after the sfx fix): 3,086 passed, 11 skipped, 0 failed, 4 warnings (305 s each).
- Next recovery point: after 00:00 UTC 25 Nov, with the owner's answers to decisions 1-2, the Seven Sleepers re-render: back up the folder to output_old, raise this film's drawing limit, redraw 52/54/67, lengthen the script (two-family fact-check before voice), re-render, inspect the MP4. Until then nothing is running for this mission.

## 9. Kaggle re-check in the owner's Chrome (24 Nov 2026, ~15:50 UTC, read only, not signed in, nothing clicked but navigation)
- Terms of Use: still version 22 Jun 2025 (active). Unchanged clause: use only "for your own internal, personal, non-commercial use, and not on behalf of or for the benefit of any third party".
- Acceptable Use Policy (22 Jun 2025): no use of resources for "server farming" or "activity unrelated to ML data science".
- Notebook docs: a free single P100 or 2x T4; 12-hour session limit; extra GPU hours (15-30 a week) only for Colab Pro subscribers (experimental).
- Conclusion: running models on Kaggle to make videos for the monetised channel is commercial production, and running inference for a pipeline is not ML data science. Both rules rule it out. The compute router's Kaggle gate stays BLOCKED (`enabled: false`, no permitted tasks); nothing changed in config. Personal, non-commercial ML experiments (for example testing a model) would fit the terms; that is the owner's call.
