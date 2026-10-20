# Autopilot repairs: make every blocked video fixable without the owner

> **For agentic workers:** execute task by task (native), tests first, one commit per task. Run `.venv/bin/python -m pytest -q` before every commit.

**Goal:** One passing long video can go out every day, and videos the reviewer blocks are repaired by the fixer instead of waiting for the owner.

**Architecture:** Evidence first (done 2026-10-20): of 24 unfinished videos, 9 fail `title_matches`, 8 `visual_review`, 5 `variety_script`; the fixer had no remedy for the last two, picked titles without checking them, and repairs ran one per 30-minute tick while production kept adding videos.

**Spec:** the owner's request of 2026-10-20 ("fix the problems, daily long video, stop preparing videos until Autopilot works"); CLAUDE.md rules A to F.

## Global Constraints
- Never weaken a safety gate silently: every loosened rule is named in the final report. Nothing is published or made public by these changes.
- Tests must pass before each commit. No cache deletion by pattern. No worker restart while a render runs.
- `make_videos` stays off until Task 5 is verified on the live backlog.

## Review Focus
- A fixed title that the reviewer still rejects must not loop forever (MAX_ATTEMPTS stays 2).
- The visual gate must still hold a video with two or more WRONG pictures or garbled captions.
- A Short ending must never repeat a recent Short's ending.

### Task 1: Titles are checked before they are accepted
Files: `reviewer.py` (llm_review records `title_reason`, `covers`; new `title_ok(meta, title) -> tuple[bool, str]`), `fixer.py` (`pick_title` checks each candidate with `title_ok`, writer prompt gets the reason and what the video covers, last resort `plain_title`), tests in `tests/test_fixer.py`, `tests/test_reviewer.py`.
- [ ] failing tests: candidate rejected by `title_ok` is skipped; plain fallback used when all rejected; reason stored in the check detail.
- [ ] implement; run tests; commit.

### Task 2: Shorts endings and openings vary
Files: `clipper.py` (`outro_for(topic, recent) -> str`), `fixer.py` (remedy for `variety_script`: new last line / opening, then re-render), `run.py` (`cmd_redo_short(slug)`).
- [ ] failing tests: `outro_for` never returns a line with similarity >= 0.75 to a recent ending; fixer clears `variety_script` on a fake Short.
- [ ] implement; tests; commit.

### Task 3: The picture gate separates wrong pictures from mood pictures
Files: `videoinspect.py` (SCHEMA: picture issue has `kind` of `wrong` or `mood`), `autopilot.py` (`visually_ok` counts `wrong` >= 2 or garbled), `footage.py` (`scene_images(..., art_first=True)` skips the generic reserve), `fixer.py` (remedy: set `art_first`, re-render once), `run.py` (`_produce_doc` / `_produce_short` honour `art_first`).
- [ ] failing tests for each; implement; tests; commit.

### Task 4: Repairs keep pace
Files: `autopilot.py` (`build_state` marks `cheap_fix` when only title or metadata checks fail; `tick` lets cheap fixes run beside one heavy action).
- [ ] failing test: three cheap fixes plus one heavy are all planned and executed in one tick; commit.

### Task 5: Daily supply, deploy, resume
Files: `risk.py` (row "Daily video supply": passing, approved, not yet uploaded long videos vs days of cover), deploy, run the fixer over the live backlog, then switch `make_videos` on with documentaries first.
- [ ] tests for the risk row; deploy with `deploy/deploy.sh`; watch the backlog drain; report what still needs the owner.
