# Target design: Foundation, option A (Phase 5, 25 Oct 2026)

Chosen by the owner at Checkpoint 3. Scope: requirements R4, R7, R8, R9, R10. The owner's studio must behave exactly as before (CLAUDE.md, user studios section).

## 1. Components
| Component | Responsibility | Owns | Must not |
|---|---|---|---|
| `records.py` (new) | the only code that writes a video's `meta.json` | atomic write, lock, merge | decide what a key means; call YouTube or the model |
| `.github/workflows/tests.yml` (new) | run `pytest` on every push and pull request | the cloud test result | deploy, hold secrets, call real APIs |
| `profile.py` (new, small) | read `data/profile.json`: `daily_budget_usd`, `human_approval`, `max_videos_per_week` defaults | the per-studio settings file | hold secrets |
| `backup_push.py` (new, later) | push the newest backup archive to a private repo | the off-server copy | push `.env`, tokens, videos, `data/auth*` |

## 2. Interface of `records.py`
- `read(folder) -> dict`: current record (shared lock).
- `update(folder, fn)`: take the exclusive lock, read the current file, call `fn(record)` which changes the dict in place, write to `meta.json.tmp` in the same folder, `fsync`, `os.replace` to `meta.json`, release the lock. Returns the new record.
- `merge(folder, changes)`: `update` with `record.update(changes)`.
- `create(folder, data)`: refuses if `meta.json` exists (the existing rule: never write into a folder that holds a video).
- Lock: `fcntl.flock` on a sidecar `.meta.lock` in the folder; the worker and the dashboard share the volume, so one lock covers both containers.
- Versioning: the file format does not change; the keys stay the same, so the dashboard, backups, MCP gateway and audits keep working.

## 3. Data design
No schema change. `meta.json` stays the record, `claims.json` the ledger. The temp file and `.meta.lock` are in the video's folder and are excluded from backups by the existing allowlist rule (backups copy named files only; to verify in the test).

## 4. Reliability
- A crash mid-write leaves the old `meta.json` intact (temp file plus `os.replace`).
- Two writers no longer overwrite each other: the second waits for the lock and then re-reads.
- Lock wait times out after 10 s with a clear error (never a silent skip).
- Idempotency stays as now (`upload_started` is written first).

## 5. Security
- CI has no secrets: tests use fakes (`tests/` already do). The workflow gets read-only repo permission.
- Off-server backup: a deploy key limited to the one private backup repo, stored on the server only (`scp`, mode 600), never in the repo. The pushed archive is the existing allowlisted backup (records only, no videos, no `data/auth*`, `.env`, tokens).
- A test greps the code for direct writes to `meta.json` (R7) and for secret patterns.

## 6. Observability
Every `records.update` that fails or times out writes one activity-feed event. The Risks card row "Losing the records" also reports the age of the off-server copy once it exists.

## 7. Cost plan
$0 a month: GitHub Actions is free for a public repo; a private backup repo is free. No new API calls. Tests make none.

## 8. Settings (R9, R10) - as built in step 4
Built as `channelprofile.py` (not `profile.py`: that name is a Python standard-library module) with `data/profile.json` holding only `human_approval` (default false). Money and weekly caps stay in `llm.json` and `autopilot.json`, which every studio already has of its own, so R9 (budget per studio) is met by the existing files. `autopilot.auto_approves(cfg)` combines the old `auto_approve` setting with the gate and never rewrites the saved config.

Original plan:
`data/profile.json` (server only, not committed): `{"daily_budget_usd": 1.5, "human_approval": false, "max_videos_per_week": 5}`. Today these live in `llm.json` and `autopilot.json`; step 4 reads them from one place and keeps the old files working. `human_approval: true` makes Autopilot leave a reviewed video unapproved until the owner clicks approve (default false, so the owner's studio does not change).

## 9. Build order, each step shippable and reversible
1. **CI**: add the workflow; the first run must be green. Rollback: delete the file.
2. **`records.py` + tests** (no caller yet). Rollback: delete the file.
3. **Move writers in groups**, each deployed alone and not while a render runs: (a) `recheck`, `controls`, `safety`; (b) `autopilot`; (c) `titletest`, `upload`, `fixer`; (d) the rest (`run`, `videoinspect`, `channelwatch`, `thumbnail`, `subtitles`, `seo`, `reviewer`, `worker`). After the last group, the grep test is switched on. Rollback: revert the group's commit.
4. **Settings + gate** (`profile.py`, `human_approval`).
5. **Off-server backup push** once the owner creates the private repo and adds the deploy key.
Every step: full tests, one real video checked, the Risks card read, a note in `docs/studio/PROGRESS.md`. Nothing is pushed, deployed or run on the server without the owner's OK.

## 10. Not verified
That `flock` works across the worker and dashboard containers on this server's disk (test on the server before step 3); how long the first CI run takes; that backups skip `.meta.lock` and the temp file.
