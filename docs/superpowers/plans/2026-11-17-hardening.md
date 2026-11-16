# Hardening after the move Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Close the three open review points of the home-server move with the better tool for each, not a patch: YouTube reads retry like Google's client is built to, the deploy gate blocks only what a running job would lose, clear names, and a guard so private addresses never reach the public repo again.

**Architecture:** Library-native retries (`HttpRequest.execute(num_retries=)`), a per-target deploy gate in `deploy/deploy.sh`, pure renames, and one repo-wide test.

**Tech Stack:** Python 3, google-api-python-client 2.201, bash, pytest.

**Spec:** docs/superpowers/specs/2026-11-16-home-server-design.md (anti-goal: no video uploaded twice; constraint: $0) plus the research of 17 Nov 2026:
- google-api-python-client `_should_retry_response` (installed source): retries 5xx, 429 and rate-limit 403s with exponential backoff when `num_retries` > 0; the default is 0.
- GitHub Docs, "Removing sensitive data from a repository": rotate first; rewriting history has heavy side effects; Support will not remove non-sensitive data; prevent repeats with a pre-commit check.
- Tailscale Docs, "How Tailscale assigns IP addresses": an admin can change a device's IP in the admin console.

## Global Constraints
- No force push, no history rewrite (GitHub's own advice for non-secret data; another session pushes to main).
- Nothing changes on YouTube. Tests never touch the owner's real files (tests/conftest.py).
- `.venv/bin/python -m pytest -q` and `deploy/clean_check.sh` green before every push.

## Review Focus
- A Google 500 or 429 on one page of a 3-page channel listing: the listing still completes.
- An Autopilot tick running while only dashboard code changed: the update restarts the dashboard and never touches the worker.
- Worker code changed while a render runs: still refused.
- Docker daemon unreachable: the update stops with a clear message instead of "No render is running".
- A test fixture that needs a CGNAT boundary address (100.64.0.1) must not trip the address guard.

### Task 1: YouTube reads retry with the library's backoff
- Files: `channelsync.py`, `tests/test_channelsync.py`
- `channelsync.RETRIES = 5`; every `.execute()` in `channel_videos` becomes `.execute(num_retries=RETRIES)`.
- Test: the fake records `num_retries` on every call; all equal 5.

### Task 2: clear names
- `channelsync`: `_same` -> `_matched_by`, `local_metas` -> `local_records`, `match` -> `plan_adoptions`, `apply` -> `apply_adoptions`; `governor.path` -> `governor.caps_file`. Update run.py, conftest and tests. Pure rename: the suite is the proof.

### Task 3: deploy gate per target, Docker reachability
- Files: `deploy/deploy.sh`, `tests/test_deploy_local.py`
- Dry run prints `Would restart: <none|dashboard|worker|both (rebuild)>` and `Blocked: yes|no` (yes only when a job runs in a container that would restart). `dry-run-first` stops on `Blocked: yes`, never on a job in a container that stays up. The server part starts with `docker info` and stops with "Docker is not reachable" (exit 4).
- Tests (fake `docker` on PATH answering `info`, `exec ... sh -c` with a job line, `compose restart`): dashboard-only change + worker job -> deploys and restarts only the dashboard; worker.py change + worker job -> stops (exit 3); docker info failing -> exit 4 with the message.

### Task 4: private-address guard
- Files: `tests/test_no_private_addresses.py`, `docs/superpowers/plans/2026-10-20-draft-repair-root-causes.md`
- Every git-tracked text file: no Tailscale address (100.64.0.0/10) except the boundary values tests need (100.64.0.0, 100.64.0.1, 100.127.255.254), and no `*.ts.net` name. Scrub the dead VPS address from the 20 Oct plan.

### Task 5: ship and verify
- Full suite, clean check, push, `STUDIO_VPS=local deploy/deploy.sh dry-run-first` with no FORCE, dashboard healthy, `run.py channel-sync` runs the new code.
- Owner's choice (account change, never done without a yes): change this PC's Tailscale address in the admin console (then `STUDIO_BIND` in ~/studio/.env) so the old one in git history means nothing.
