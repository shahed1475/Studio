# Autopilot works on one video at a time

> **For agentic workers:** native execution, tests first, one commit per task, full suite green before each commit.

**Goal:** Autopilot takes one video, finishes it (passes, is set aside, or is handed to the owner), and only then starts another. Long videos come before Shorts. No new video is made while a fixable one exists.

**Evidence (2026-10-20, autopilot.log and meta.json of 24 videos):**
1. The heavy slot went to the first video in folder order (alphabetical): five Shorts (anansi, korean, nine-tailed, antikythera, srivijaya) were re-rendered one per 30 minutes while the Pied Piper and Delphi documentaries waited with zero attempts.
2. `make_short` ran every tick beside the repairs: 21 Shorts piled up, 11 made overnight.
3. When the cap was reached the free fallback models answered reviews with malformed JSON; `review unavailable: KeyError` became a blocking check, so a good video counted as failed and burned a fix attempt.
4. The picture remedy re-rendered a documentary (about 30 minutes, $0.5) before checking whether the flagged pictures are still wrong under the current rule.

## Global Constraints
- Nothing is published or approved by these changes. Upload, schedule and approve steps are unchanged.
- A video the owner approved is never touched. MAX_ATTEMPTS stays 2. `make_videos` stays off until the owner's queue is clear.

## Review Focus
- A broken video that can never be fixed must not block production forever: it leaves the fixable list after 2 tries.
- An unavailable model must never turn into a fail, a pass or a used attempt.

### Task 1: An unavailable reviewer model is "unreviewed", not "failed"
Files: `reviewer.py` (`llm_review` raises/returns an `llm_review` check with `retry=True` on any error or missing key; `verdict_from` returns `"unreviewed"`), `fixer.py` (refund the attempt on `"unreviewed"`), `autopilot.py` (`do_review`/`do_fix` ignore it; a video with no stored verdict is reviewed again next tick).
- [ ] tests: missing key in the reply gives `unreviewed`; fixer leaves `fix_attempts` unchanged; plan re-reviews it.

### Task 2: One video at a time
Files: `autopilot.py` (`focus_rank`, `repair_candidates`, `plan_actions` emits one fix for the top candidate and makes new videos only when none is fixable; `tick` runs the next candidate right away when the last repair was quick), `fixer.py` (`fix` returns `rerendered`).
- [ ] tests: documentaries before Shorts; in-progress before untouched; only one fix planned; production blocked while any is fixable; tick moves on after an archive but stops after a re-render.

### Task 3: Re-read the pictures before redrawing
Files: `fixer.py` (`visual_recheck(folder) -> bool` using `videoinspect.visual_review` and `autopilot.WRONG_PICTURES`).
- [ ] tests: still-wrong pictures redraw; now-acceptable pictures only clear the flag.

### Task 4: Show it
Files: `autopilot.py` (`status()` gains `focus`), `dashboard.html` (a line "Working on: title, step").
- [ ] test: `status()["focus"]` names the top candidate.

### Task 5: Deploy and watch the two documentaries finish.
