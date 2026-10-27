# Migration plan: Foundation (Phase 6, 25 Oct 2026)

Design: `docs/architecture/05-target-design.md`. Rules for every step: a branch, tests first, the full suite (`.venv/bin/python -m pytest -q`, 862 pass today), deploy with `STUDIO_VPS=deploy@vps-ai deploy/deploy.sh` and never while a render runs, one real video checked after, a note in `docs/studio/PROGRESS.md`. Nothing is pushed, deployed or run on the server without the owner's OK. Effort is in "working steps" (one focused session each), my estimate, not measured.

| # | Step | Goal | Changes | Tests | Done when | Rollback | Effort |
|---|---|---|---|---|---|---|---|
| 1 | Cloud tests | R8 | add `.github/workflows/tests.yml` (Python 3.12 or the version the code needs, install requirements, `pytest -q`, read-only permissions) | the workflow itself; first run on a pushed branch | a green run on GitHub | delete the file | 1 |
| 2 | `records.py` | R7 groundwork | new module `read/update/merge/create`, lock and atomic write | unit tests: parallel writers, crash mid-write (old file survives), refuse overwrite on create, timeout | tests pass; no caller yet | delete the file | 1 |
| 2b | Lock check on the server | verify the design assumption | a throwaway script in the worker and the dashboard container writing one test folder (outside `output/`) | the script shows the lock blocks across containers | evidence in `PROGRESS.md` | delete the test folder | 0.5 |
| 3a | Move group A | R7 | `recheck.py`, `controls.py`, `safety.py` use `records` | their existing tests plus one new test per module | tests pass; deployed | revert the commit | 1 |
| 3b | Move group B | R7 | `autopilot.py` (9 places) | existing autopilot tests plus a stale-write test | tests pass; one Autopilot pass runs clean on the server | revert | 1.5 |
| 3c | Move group C | R7 | `titletest.py`, `upload.py`, `fixer.py` | existing tests; upload retry still finds an earlier copy | tests pass; deployed | revert | 1.5 |
| 3d | Move group D and switch the grep test on | R7 complete | `run.py`, `videoinspect.py`, `channelwatch.py`, `thumbnail.py`, `subtitles.py`, `seo.py`, `reviewer.py`, `worker.py` | the grep test (no direct `meta.json` writes outside `records.py`) | grep test green in CI | revert; turn the grep test off | 1.5 |
| 4 | Settings and gate | R9, R10 | `profile.py`; `human_approval` read by Autopilot; old files still work | a test that `human_approval: true` leaves a passed video unapproved and `false` changes nothing | the owner's studio behaves the same with defaults | revert | 1 |
| 5 | Off-server backup | R4 | `backup_push.py` plus a timer; deploy key (owner adds); age shown on the Risks card | archive contents test (no secrets); a push to a test branch | the off-server copy is under 24 hours old | remove the timer and the key | 1 |

Order and dependencies: 1 can go first and alone; 2 needs nothing; 2b needs 2; 3a to 3d need 2 and 2b in order; 4 needs 3d; 5 needs the owner to create the private repo and add the key (their action). Quick wins first: step 1 and step 2 change no behavior. Nothing needs downtime; deploys restart only what changed and wait for renders.

Money: none of the steps calls a paid API. Real-video checks use videos Autopilot makes anyway.

Risks: the lock may not work across containers (step 2b tests it before any writer moves); a missed writer keeps the old bug (the step 3d test catches it); each deploy restarts the worker (the deploy script protects renders).
