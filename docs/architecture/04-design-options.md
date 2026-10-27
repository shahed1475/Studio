# Design options for the Foundation (Phase 4, 25 Oct 2026)

Scope: only what requirements R4 and R7 to R10 need (`docs/architecture/03-requirements.md`). Nothing here adds a channel.

## Facts this rests on (VERIFIED by grep on 25 Oct)
- 24 Python files mention `meta.json`; about 15 of them write it directly with `write_text` (`autopilot.py` 9 places, `titletest.py` 4, `run.py` 4, `upload.py` 3, then fixer, videoinspect, channelwatch and 8 others with 1 each). `recheck._merge` is the only careful merge (reads the current file, changes its own keys, writes).
- There is no `.github/` folder: no cloud tests (R8).
- Money tracking exists in `llm.py` (cost scopes, `video_costs.json`, daily cap) and is per studio because each studio has its own files; there is no cross-studio cap.
- Backups (`backup.py`) already exist, on the same disk.

## Option A: one small record module, files stay the truth (recommended)
A new `records.py`: `read(slug)`, `merge(slug, changes)` (re-read, change only the named keys, write to a temp file, `os.replace`, under a file lock) and `create(slug, data)`. The 15 writers move over one at a time, each with its test. A test greps the code and fails if a module writes `meta.json` itself. GitHub Actions runs `pytest` on every push. Per-studio budget and the human gate are two keys read from a channel profile file.
- Solves: problem 3 (lost or stale writes) and 4 (no cloud tests); prepares 8 (profiles).
- Requirements: R7 met, R8 met, R9 met (cap per studio from its own profile), R10 met (a `human_approval` setting), R4 separate (see below).
- Cost: $0 a month (GitHub Actions is free for a public repo). Effort: about 4 to 6 working steps; the smallest is CI (about 1 step), the biggest is moving 15 writers (about 3 steps).
- Risks: a missed writer keeps the old bug until the test catches it; a file lock misbehaves on the server's disk (test it there first).
- Harder afterwards: nothing; the files, the dashboard, backups and the MCP gateway read the same files.
- Fit: plain Python and files, the same as everything else; the owner and Claude sessions can run it.

## Option B: move records into SQLite
Replace `meta.json` by a database table (transactions, one file `studio.db`).
- Solves: problem 3 completely (real transactions) and makes queries easy.
- Requirements: R7 met; R8 to R10 the same as A.
- Cost: $0 a month. Effort: large, about 10 or more steps: every reader (dashboard, backup, MCP, the MCP gateway, the risk monitor, 24 files) must change, plus a migration of 13 videos and a rollback path.
- Risks: a bad migration loses records, which is the thing R4 protects; every tool that reads files by eye (`cat meta.json`, the audits, the Claude web project) stops working.
- Harder afterwards: debugging by reading files; backups need a database dump.
- Fit: too big for the problem and the credit.

## Option C: only cloud tests and the backup, leave the writers alone
Add GitHub Actions and the off-server backup now; document "use `_merge`" in CLAUDE.md.
- Solves: problems 4 and 7. Does not solve 3.
- Requirements: R4 and R8 met; R7 not met; R9 and R10 partly.
- Cost: $0. Effort: about 2 steps.
- Risks: the stale-write bug can return with the next feature; every new channel adds writers.
- Fit: cheapest, and a good first half of A.

## Recommendation: A, in this order
1. CI (Option C's half): GitHub Actions running `pytest`. Smallest, safest, no behavior change.
2. Off-server backup push (R4), after you create the private repo.
3. `records.py` with its tests, then move the writers in small groups (autopilot first), each deployed on its own, not while a render runs.
4. Per-studio budget and the human gate as profile keys.
What I would give up: SQLite's guarantees. For one studio and 13 videos, atomic file writes under a lock are enough, and the files stay readable.

| Requirement | A | B | C |
|---|---|---|---|
| R4 off-server copy | with step 2 | with step 2 | met |
| R7 one safe writer | met | met | not met |
| R8 cloud tests | met | met | met |
| R9 budget per studio | met | met | partly |
| R10 human gate | met | met | partly |
