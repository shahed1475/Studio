# Current state (as built, 25 Oct 2026)

How this was made: consolidated from `docs/AUDIT_2026-10-24.md`, `docs/AUDIT_2026-10-24b.md`, `docs/SERVER_STATE.md`, `docs/PLAN_MULTI_CHANNEL_2026-10-24.md`, `CLAUDE.md`, and the code and server I read on 24-25 Oct (`autopilot.py`, `planner.py`, `controls.py`, `footage.py`, `safety.py`, `fixer.py`, `run.py`, `studio_mcp/`). Not re-read line by line today. Anything not marked VERIFIED below is from those documents.

## Components
| Component | What it owns | Where |
|---|---|---|
| Worker container `studio-worker` (3 GB, 4 CPUs) | timers, renders, uploads | `deploy/`, `autopilot.py` |
| Dashboard `studio-dashboard` (3 GB, 4 CPUs) | login, approvals, Risks card | `dashboard/` |
| User studio `studio-test-*` | one other user's studio (`test`) | `deploy/tenant.sh`, `tenantmode.py` |
| Proxy `studio-proxy` | one public address, cookie routing | `deploy/` |
| MCP gateway `~/studio-mcp` (host) | 7 read tools, 4 change tools (off unless `STUDIO_MCP_WRITE=1`), audit log | `studio_mcp/`, `controls.py` |
| Timers in the worker | Autopilot 30 min, re-check hourly, health hourly, backup 03:30, policy 06:10, growth 06:30, report 07:00, title test 08:00 | `autopilot.py`, `recheck.py`, `backup.py`, `dailyreport.py` |

## Pipeline (one video, about 25 min, about $1 for a documentary)
topic (`topicrank`, `seo.demand`) -> script from 2 Wikipedia pages (`scriptgen`) -> fact check and rewrite (`scriptgen.verify_and_revise`, `ledger`) -> voice (edge-tts, word timings) -> pictures (`footage.scene_images`: Commons search, a judge that now reads categories, AI art, variety retry) -> render (ffmpeg) -> packaging (`packaging.py`, `thumbnail.py`) -> review and repair (`reviewer`, `fixer`, 2 tries) -> slot and last picture check (`prelaunch`) -> private scheduled upload (`upload.py`) -> hourly re-check, daily title test, daily report.

## Data
Files only, no database: `output/<slug>/meta.json` (record), `claims.json` (claim ledger), `words.json`; `data/` (money, events, job state, playlists, title test); `backups/` (seven nightly archives, allowlist, no secrets, no videos, same disk). Written by many modules with plain `write_text` (no shared safe writer yet).

## Communication
All in-process Python calls and files; Docker exec from the host gateway into the worker (`docker exec -i ... python -m controls`, JSON on stdin). No queues, no events. Sync everywhere; Autopilot is a polling loop.

## External services
OpenRouter (Claude writes and reviews, Gemini draws; about $2.5 a day, credit $8.43 on 25 Oct), Wikipedia and Wikimedia, YouTube Data and Analytics APIs (token has 4 scopes), YouTube search autocomplete, Google sign-in.

## Infrastructure
One VPS (4 shared cores, 16 GB, about 20 other projects), Docker Compose, deploy by `deploy/deploy.sh` (pull, restart only what changed, protects running renders), tests run on the owner's PC before each deploy (no CI). Secrets reach the server by `scp` only. Server-only settings are documented in `docs/SERVER_STATE.md`.

## Cross-cutting
Dashboard login; hourly money guard and a daily cap ($3.00) plus per-video limits; policy watch and compliance agent; safety check of published videos (pauses Autopilot on a problem: fixed on 25 Oct so held videos are skipped); risk monitor with 12 rows.

## Stack
Python 3.14 on the host, venv; Python in the containers; ffmpeg; edge-tts; Docker; Caddy. 862 tests pass (run 25 Oct).

## What it cannot do yet
Run a second kind of channel, draw graphics that are not photos, show a presenter, post anywhere except YouTube.
