# Doctor agent audit (2026-11-20)

The doctor (`doctor.py`, job every 6 hours, playbook `playbooks/doctor.md`) is kept and was extended. Nothing was removed.

## What it already does (inspected)
- **Monitors:** every agent that has a worker job, against its own cadence (stale after 2.5 periods) and against `logs/worker.log` (failing after 2 failed runs in a row); the dashboard (`/healthz`); the model key; YouTube edit permission in apply mode; the off-server backup.
- **Recovers, safe fixes only** (`escalate.solve`: lessons, then two model opinions, then the owner): runs the registered job again (never `autopilot`, never while a render runs), makes secret files private, creates missing folders.
- **Records:** a post-mortem in `data/agent/proposals/`; a skill draft (quarantined, never installed) for a problem family seen 3 or more times, at most once a month per family; `setup_request` tasks with exact commands, closed again when the item is fixed.
- **Inbox:** `agent_problem` tasks from the script reviewer (`handle_inbox`).
- **Never:** installs, publishes, deletes, flips an owner switch, uses a browser.

## Added today
| Monitor | How | Recovery allowed |
|---|---|---|
| Disk space | `doctor.free_gb()`; below `MIN_FREE_GB` (20 GB) a `setup_request` "disk space" | Commands to **look** (`du`, `df`) and the sentence "the studio never deletes a video to make room". No delete command; a test pins it. |
| Provider availability and routing | `doctor.provider_status(now)` in `data/agent/doctor.json`: Free Mode, whether paid is allowed, own provider and OpenRouter free models usable now (from the studio's own records, no network) | Report only. Free tiers rate-limit and recover on their own; a task every 6 hours would be noise. |
| Free disk in the report | `result["free_gb"]` | — |

Tests: `tests/test_doctor_capacity.py` (3) and the existing doctor tests (`tests/test_doctor_noise.py`, the doctor cases in `tests/test_agents_training.py`) pass.

## Real reading in the worker (20 Nov, read-only; no tasks posted)
- Free disk 268.1 GB, so no disk request.
- Providers: `free_mode: true`, `paid_allowed: false`, own provider 3 of 3 not parked, OpenRouter free 11 of 13 not parked. The direct 429 test earlier came through `extra_ping`, which does not park a model. The first real call parks it for its Retry-After.
- Needs: `off-server backup` (still open; the owner's step).
- Agents with a job: 16 ok, 0 stale, 0 failing.

## Other failure classes and who handles them (existing, verified by reading)
| Failure | Handled by |
|---|---|
| Provider rate limit | `freemodels.record` busy cool-down plus `soonest_free` wait |
| Invalid model response | `llm._ask_free` (`json_bad`, ask again with twice the room when cut off) |
| Missing source | Script flagged, held for the owner |
| Invalid script | `scriptreview`, `_script_gate`, and now `a2a.handoff("script")` |
| Missing visual | `footage.scene_images` fallback, and now `a2a.handoff("visuals")` |
| ffmpeg failure | The job fails, an activity error appears, triage groups it, the doctor writes a post-mortem. The GIF cause is fixed (`render.still_for_ffmpeg`). |
| Interrupted render | `run.py repair`, `unstick.py` |
| Worker crash | Docker `restart: unless-stopped` plus the worker heartbeat |
| Registration | `a2a.handoff("render")` runs before `records.save` |
| Corrupt or invented data | Today's test and eval pollution of `free_models.json` and `llm_usage.json` is fixed at the cause (see `FREE_MODEL_OPTIMIZATION.md`) |

## Not done
- The doctor does not yet read `a2a.expire()` for timed-out agent tasks. Nothing posts A2A tasks in production yet (see `A2A_ARCHITECTURE_AUDIT.md`), so there is nothing to expire.
