# YouTube upload and scheduling audit (22 Nov 2026, read-only)

Section 13 of the owner's master mission. Skill loaded first: youtube-publisher (`~/studio/.claude/skills/youtube-publisher`). Nothing was uploaded, scheduled, made public or changed on YouTube.

| Check | Status | Evidence |
|---|---|---|
| OAuth login | PASS | `run.py youtube-login`: production mode, login 29.0 days old, last check 2026-11-22 09:08 UTC ok |
| Permissions | PASS | token scopes: youtube.upload, youtube.readonly, youtube, yt-analytics.readonly (values of the token not read) |
| Schedule source of truth | PASS | `autopilot.json` `slots`: Tue 18:00, Thu 15:00, Sat 10:00, Sun 10:00 (US Eastern, as the dashboard shows), `review_window_hours` 24, `auto_approve` true (owner's decision 22 Nov), `pause_scheduling` true: no slot is given and nothing is sent to YouTube until the owner unpauses |
| Upload records | PASS | 24 videos carry a YouTube id and an `upload_check`; the latest uploads were private with a publish time (Antikythera 11 and 12 Nov, Kappa 17 Nov) |
| Read-back of a live video | PASS after fix | `verify_upload.py` on Kappa (a8yukGLiknI): YouTube says public, processed. Before the fix the check reported two "problems" (public, schedule gone) for a video that went public exactly as scheduled; fixed in `upload.verify_upload` (public with the schedule cleared after its time = the plan carried out; public before its time, or private with its schedule gone, still reported). Test: `tests/test_upload_hardening.py` |
| AI disclosure | PARTIALLY VERIFIED | sent with every upload (`containsSyntheticMedia` true); YouTube's API never returns the field, so it cannot be read back: "Altered content" in YouTube Studio is the owner's check |
| Duplicate prevention, recovery | PASS (by tests) | `upload_started` written before sending, a retry adopts the earlier copy by title or description, a per-video lock refuses a second process (`tests/test_upload_hardening.py`, 19 passed) |
| Private upload of the new documentary | NOT TESTED | waits for the Maximilian documentary and the owner's approval; scheduling is paused |

## What needs the owner
- Scheduling is paused (`pause_scheduling` true). Uploads and new slots resume only when the owner unpauses it.
- "Altered content" for AI pictures can only be confirmed in YouTube Studio.
