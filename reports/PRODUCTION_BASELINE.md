# Production baseline (2026-11-20, 09:20 Bangladesh time / 03:20 UTC)

Everything below was observed by command at that time unless marked **historical**. No code was changed while collecting this.

## Code and git
- Production folder: `/home/fahad/studio`, branch `main`, HEAD `8e060dc` (same as the last commit pulled from GitHub `shahed1475/Studio`).
- Working tree: 32 modified tracked files, 39 untracked entries. These are the owner's hand edits plus the 20 Nov changes (see `CODEBASE_RECONCILIATION.md`). Nothing has been committed since `8e060dc`.

## Containers
| | studio-dashboard | studio-worker |
|---|---|---|
| Image | `studio:local` sha256:1f8ef923… | the same image |
| Mount | `/home/fahad/studio -> /app` (rw) | the same mount |
| Network | host | host |
| User | 1000:1000 | 1000:1000 |
| Memory limit | 3 GiB | 3 GiB |
| Started | 2026-11-20 02:44 UTC (restarted after the Competitor removal) | 2026-11-19 15:41 UTC |
| Health | healthy, `/healthz` 200 | healthy, health check exit 0 |

- Both containers run the code in `/home/fahad/studio` directly: it is bind-mounted, not baked into the image.
- **Code versions in memory:** the dashboard loaded the current files when it started. The worker process (`worker.py`) imports only `agentlog`, `config` and `records`, and none of those changed after it started. Every job runs as a new `python run.py …` process (`worker.py:109`), so jobs always use the current files. Files changed after the worker started: `animate.py`, `dashboard.py`, `packaging.py`, `reviewer.py`, `run.py`. None of them is held by the worker process.

## Running work
- No ffmpeg, `run.py` or Blender process in either container at 03:20 UTC. Nothing is rendering.

## Machine capacity
| Item | Now | Historical report |
|---|---|---|
| Disk `/` and `/home` (one partition) | 952 GB, 696 GB used, **250 GB free (74 %)** | "nearly full root filesystem": no longer true |
| RAM | 23 GiB, about 10 GiB available | |
| Swap | **7.0 of 8.0 GiB used** (memory pressure from desktop apps: Chrome and others) | |
| CPU | 6 cores, load 2.5 | |
| OOM kills, last 7 days (`journalctl -k`) | **0** | |
| Studio sizes | output 5.5 GB, cache 638 MB, data 176 MB, backups 18 MB | |

**Rendering risk:** each container is capped at 3 GiB and swap is almost full. A long render must be watched for memory, but disk space is no longer a blocker.

## Providers and Free Mode (values read from the config files, secrets masked)
- `llm.json`:
  - `enabled: false` (paid models off), `free: true`, `free_review: true`.
  - `ai_art: false` (paid pictures off), `free_art: true` (Cloudflare), `free_art_cap: 9000`, `free_daily_limit: 900`.
  - `daily_budget_usd: 5.0`, `local_fallback: false`.
- `llm.free_only()` returns **True** inside the worker.
- The live `llm.py` has **no** `mode()` / `paid_allowed()`. Those exist only in the workshop copy, so Free Mode here is the older set of switches (`enabled`, `free`, `free_review`, `ai_art`).
- Extra provider (Settings card): on, `http://127.0.0.1:31415/v1` (the owner's local proxy, local-box tick set), with the models listed below. The proxy answers (401 without a key, so it is up).

  | Role | Models |
  |---|---|
  | script | `gemini-3.5-flash, gemini-3.6-flash, auto` |
  | review | `gemini-3.6-flash, auto` |
- OpenRouter models in `llm.json`: script, review and cheap are all `google/gemma-4-26b-a4b-it:free`.
- Free pictures: `freeart.usable()` is True. Cloudflare usage file: 6,408 neurons on 2026-11-19 (that day's count; the count starts again each day).
- Keys present (values not read out): `OPENROUTER_API_KEY`, the OpenRouter key in settings, the extra provider key, Pixabay, Smithsonian, Cloudflare account and token, and the backup repository.

## Autopilot (`autopilot.json`)
- **`enabled: false`**, `make_videos: true`, `auto_approve: true`, **`pause_scheduling: false`**, `uploads_per_day: 1`.
- `governor.base`: doc 4 and short 7.
- `weekly.enabled: true`.
- `house_style.look: photo` with `min_credit 8.0`.
- `second_sources.enabled: true`.

**Safety note:** while `pause_scheduling` is false and `auto_approve` is true, switching `enabled` on would let Autopilot approve and schedule videos by itself. Any controlled test run must set `pause_scheduling: true` first.

## Account
- OpenRouter credit: −$0.05 (historical, read on 20 Nov by the earlier check; not re-read here, to avoid a provider call).
- YouTube login: worked on 20 Nov (historical).
