# Autopilot prepares each video just in time

> **For agentic workers:** native execution, tests first, one commit per task, full suite green before each commit. The behaviour contract is `docs/AUTOPILOT.md`.

**Goal:** A slot's video is made and approved 24 hours before its post time, started 12 hours before that window opens; nothing is made or repaired for slots that are not due.

**Evidence (2026-10-20, dashboard in the browser):** "Next videos" showed every slot to 28 Oct filled with "In work" or "Scheduled": `planner.needs` kept three posts covered and the pipeline of 17 drafts was assigned to far-off slots, so Autopilot repaired Shorts for 26 to 28 Oct today.

## Global Constraints
- Nothing is published or approved by these changes. A ready video is still scheduled at once. Parked drafts are never deleted.

## Review Focus
- A due slot with no draft and no topic must not crash: it asks for ideas.
- A slot becoming due while a repair is running must not start a second job.

### Task 1: `planner.py` horizon
`prepare_hours` (default 12) replaces `plan_ahead`. Horizon = now + review window + prepare hours. Rows: ready videos take the earliest empty slots; drafts only take due slots; empty due slots are `empty`; later slots are `later` with `starts` (when Autopilot begins). `needs` = empty due slots. `repair_targets` = drafts assigned to due slots.
### Task 2: `autopilot.py`
`plan_actions`: repair only targets; make only for due empty slots. Config and dashboard validation: `prepare_hours` 0 to 72.
### Task 3: Page
Rows say "Autopilot starts <time>" for later slots; Rules field "Start preparing (hours before the review window)"; a collapsed "How Autopilot works" with the contract in plain words.
### Task 4: Deploy and verify on the live backlog; then a full feature audit.
