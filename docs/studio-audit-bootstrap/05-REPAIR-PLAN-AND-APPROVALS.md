# 05 — Repair plan and approvals

Status: IN_PROGRESS (waiting for the owner's decision). Nothing listed here has been changed.

| ID | Severity | Classification | Path | Finding |
|---|---|---|---|---|
| F1 | high | likely cause (strongly supported) | n/a (how the session was started) | Earlier session started in the forbidden folder: wrong CLAUDE.md and skills, Studio outside the write scope (00, 03) |
| F2 | high | likely cause | sandbox / file tools | Write failure = Studio was not a working directory. Not Unix permissions (03) |
| F3 | high (latent) | confirmed, currently inert | `~/.claude/settings.json` `permissions.additional_directories: ["/home/fahad"]` | Misspelled, so ignored. If corrected, it would make the forbidden folder writable (02) |
| F4 | medium | confirmed | `tools/claude-studio.sh` lines 37–38 | The worker-mount check fails open when docker is unreachable (01, L-1) |
| F5 | low | confirmed | `tools/claude-studio.sh` | Launcher untracked in git, so a clean or reset can lose it |
| F6 | low | confirmed | `.claude/hooks/studio_guard.py` | Guard hook present but registered nowhere (04) |
| F7 | low | inferred | shell profile (not opened) | Junk and duplicate PATH entries from an `npm` command (01) |
| F8 | info | not a problem | Git variables | `safe.directory` for Studio comes from the harness; no bypass |
| F9 | info | not a problem | `/home/fahad/studio` ownership | `fahad:fahad 775` |

## Proposed changes

### R1: F4, make the worker-mount check fail closed (inside the approved scope; needs approval)
- **File:** `/home/fahad/studio/tools/claude-studio.sh` (physical path verified, outside the forbidden folder)
- **Current behaviour:** any docker error counts as "not running" and passes.
- **Change:** keep docker's error text. "No such object/container" counts as not running (pass). Any other error (daemon unreachable, permission denied) **refuses to start**, naming the error. About 6 lines; no check is removed.
- **Security impact:** stricter only.
- **Regression risk:** the launcher refuses while the system docker daemon is stopped or unreachable, and `--check` run inside a Claude sandbox fails (docker is denied there). Run it from a normal terminal.
- **Backup / rollback:** copy to `tools/claude-studio.sh.bak-2026-11-26` first; roll back with `cp tools/claude-studio.sh.bak-2026-11-26 tools/claude-studio.sh`.
- **Verification:** `bash -n`; `--check` from a normal terminal (expected exit 0); `--check` inside the Claude sandbox (expected refusal naming "permission denied").

### R2: F5, commit the launcher (needs an explicit "commit" from the owner; no push)

### R3: F3, owner's manual step, outside the approved scope
Delete the `additional_directories` line from `~/.claude/settings.json` yourself (back it up first). Do **not** rename it to `additionalDirectories`.

### Deliberately not proposed
Permission or sandbox changes (none needed). Registering `studio_guard.py`, editing the shell profile, installing anything.

## Approvals
(recorded in 06 once the owner answers)
