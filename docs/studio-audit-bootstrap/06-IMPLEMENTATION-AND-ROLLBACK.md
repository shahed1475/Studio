# 06 — Implementation and rollback

Status: COMPLETE for R1, R2 and R3 (26 Nov 2026, about 12:20 to 12:40, PC time +06).

Who did it: a second Claude Code session. That session was itself started in the forbidden folder
(working directory `/home/fahad/Desktop/Youtube-automation`, `CLAUDE_CODE_CHILD_SESSION=1`, entrypoint `cli`). It read
nothing inside that folder: every command used absolute paths into Studio or the home folder. Writes to Studio went
through Claude Code's permission prompts (Edit and Write) and single git commands run outside the sandbox.

## Approval

The owner, in that session, 26 Nov 2026: "get the blocker from the studio folder and fix and set, and then test and
push commit and deploy". Taken as approval of R1, R2 and R3 in 05, of the commits and of the push. See "Deploy" for why
nothing was redeployed.

## Changes

| ID | Change | Where | Commit or backup | Rollback |
|---|---|---|---|---|
| R2 | Launcher committed unchanged (it was untracked) | `tools/claude-studio.sh` | `0e0aebd` | none needed |
| R1 | The worker-mount check fails closed: only "no such object/container" counts as not running; any other docker error refuses and names it | `tools/claude-studio.sh` | `76dcbcf` | `git revert 76dcbcf` |
| F10 | The launcher refuses inside a Claude Code session (`CLAUDECODE` set) with a plain message: exit and run it from a normal terminal. Before, it listed `GIT_CONFIG_VALUE_0/1`, which invited unsetting them | `tools/claude-studio.sh` | `76dcbcf` | `git revert 76dcbcf` |
| tests | 10 cases, empty environment, fake `docker` and `claude` | `tests/test_claude_studio_launcher.py` | `76dcbcf` | `git revert 76dcbcf` |
| R3 | Removed `permissions.additional_directories: ["/home/fahad"]` (misspelled, ignored, dangerous if "corrected"). Nothing else changed (checked by comparing the parsed JSON with the backup) | `~/.claude/settings.json` | backup `~/.claude/settings.json.bak-2026-11-26-before-additional-dirs` | `cp ~/.claude/settings.json.bak-2026-11-26-before-additional-dirs ~/.claude/settings.json` |

Each commit contains only its own files (`git commit -- <paths>`; nothing else was staged). The other modified files in
the working tree belong to other work and were left untouched.

## New findings (not in 00 to 05)

| ID | Severity | Classification | Finding |
|---|---|---|---|
| F10 | medium | confirmed, fixed | Inside a session started in the forbidden folder, Claude Code sets `GIT_CONFIG_KEY_0/1=safe.directory` with values `/home/fahad/Desktop/Youtube-automation` and `.../*`. The launcher's variable check therefore refused with only those names. The refusal was right; the message was not. |
| F11 | high | confirmed, **owner decision** | Two enabled user services run the workshop's code from the forbidden folder: `story-newswatch.timer` (weekly; `run.py newswatch`, then `trends` and `channels`) and `studio-mydownloads.service` (starts at login, `127.0.0.1:8923`). Studio's worker already runs `newswatch` every Monday (`worker.py:39`), so the timer duplicates it with older code. Studio's venv has no `yt_dlp`, so My Downloads cannot be moved to Studio until it is installed there. My Downloads keeps its settings in `~/.config/studio-mydownloads`, so moving it loses nothing. |
| F12 | medium (latent) | confirmed, not active | `story-autopilot.service` and its timer also point at the forbidden folder. The timer is **not** enabled. Enabling it would start a second Autopilot (make, schedule, upload) beside the worker's. |
| F13 | info | confirmed | How the wrong-folder sessions are started is still unproven. `CLAUDE_CODE_CHILD_SESSION=1` shows that this one was started by another Claude Code process (desktop app, URL handler or background service), not typed in a terminal. The process tree is hidden by the sandbox. |

## Deploy

Not needed and not done. `tools/claude-studio.sh` runs on the host and is not used by either container; `~/studio` is
the live checkout, so the change took effect when the file was saved. Running `deploy/deploy.sh` would only risk a
restart while the tree holds other, uncommitted work.

## Not done (needs the owner)

- F11: disable the duplicate newswatch timer; install `yt-dlp` in Studio's venv and move My Downloads. Commands are in 07.
- Launching through the launcher from a normal terminal: only the owner can do it (07).
