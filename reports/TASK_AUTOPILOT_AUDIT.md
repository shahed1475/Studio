# Tasks, Autopilot and documentary length (2026-11-20)

## What the "Task section" really is (inspected)
| Place | File | What it holds |
|---|---|---|
| **Tasks** page | `ownerdesk.py`, `data/owner_desk.json` | Notes for a Claude Code session or the doctor, plus standing advice (max 1,500 characters) that reaches the writing roles only. By design (CLAUDE.md, 2 Nov) it can change no rule, limit, switch or publishing decision. |
| **Autopilot** page, Schedule and Rules | `autopilot.json` | Publish slots (documentaries tue 18:00, thu 15:00, sat 10:00, sun 10:00 US Eastern; Shorts mon to fri 12:30, sat 13:00), uploads per day, review window, `make_videos`, `auto_approve`, `enabled` |
| Rules file | `config/rules.json` plus `data/rules_state.json` | Length targets: documentaries `long_min/max_minutes`, Shorts `shorts_min/max_seconds` |

So the schedule's source of truth is the Autopilot page, not the Tasks page. Turning the Tasks page into a scheduler would undo the owner's own rule that it cannot change switches, and would add a second place for the schedule. It was not done; that is the owner's decision.

## Documentary length: now configurable, separate from Shorts, and passed to the worker
- **Control:** Autopilot > Rules > "Documentary length (minutes)": two numbers (5 to 30; 30 is the reviewer's hard limit) and a Save button. Under it: "about N to M lines and W words".
- **Saving:** `POST /api/rules/doc-length` → `dashboard.set_doc_length`. It goes through `rulesfile.propose` then `resolve(approve=True)` with source "owner (dashboard)", so it is in the rules file's history, survives a restart (`data/rules_state.json`) and bumps the rules version.
- **Readers:** `scriptgen.DOC_MINUTES` (lines, words, chapters and line length via `doc_budget`), the reviewer's `doc_length` warning, `craftlearn`. Each worker job is a new process, so the next video uses it without a restart.
- **Default now:** 20 to 26 minutes (shipped `config/rules.json` and the `rulesfile` defaults).
- **Shorts:** unchanged, 35 to 58 seconds.
- **Evidence:**
  - `tests/test_doc_length_setting.py` (9): the view; saving is an approved rules change; **a new Python process reads 18 to 24 after saving** (as a worker job would) while the Shorts length stays 58 s; wrong values are refused and change nothing; the control and route exist.
  - In the real worker: `scriptgen.DOC_MINUTES = (20.0, 26.0)`, 84 to 100 lines, 2,939 words, Shorts 35 to 58 s.
  - The real `data/rules_state.json` was not written by the tests (conftest isolation).
- **Not yet verified in the real dashboard after a restart:** see `DASHBOARD_FULL_AUDIT.md`.

## Autopilot
- `make_videos: true`, so when it runs, Autopilot makes new videos, not only reviews.
- It is **switched off** (`enabled: false`, the owner's switch, unchanged).
- `pause_scheduling: false` and `auto_approve: true`: switching it on would approve, schedule and upload by itself. A controlled test run must first set `pause_scheduling: true`.
- **Traceability per job:**
  - Each worker job writes `logs/<HHMMSS>-<command>.log` and its result in `logs/worker.log` and `data/worker_state.json`.
  - Each video has a unique folder (`unique_folder`), its record `meta.json`, now with `handoffs` (each stage's checked result and time), `claims.json`, and the activity feed.
- **The schedule was not changed.**
