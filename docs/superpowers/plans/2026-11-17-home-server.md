# Home Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The studio (dashboard + worker) runs 24/7 on the owner's Fedora PC for $0, after Hostinger deleted the VPS and its data, without uploading any video twice.

**Architecture:** A fresh clone of `main` in `~/studio` (separate from the Desktop working copy), secrets and settings from the 13 Nov VPS copy, videos and data seeded from the PC's own working copy by btrfs reflink (no extra disk). The existing `docker-compose.yml` plus a home override (fewer cores, low CPU priority so Blender wins). A new read-only `channelsync` step writes the channel's real video ids into local records before the worker may upload anything.

**Tech Stack:** Python 3 (studio), Docker 29 + Compose v5, Tailscale, YouTube Data API v3 (read-only calls), bash.

**Spec:** docs/superpowers/specs/2026-11-16-home-server-design.md

## Global Constraints
- $0: no paid plan of any kind.
- Never commit `.env`, `client_secret.json`, `token.json`, `settings.json`, `llm.json`, `agent.json`, `autopilot.json`, `data/`, `output/`, `output_old/`, `backups/`.
- Nothing is changed on YouTube by this work (channel reads only).
- The Desktop working copy is not modified except for the committed code below; nothing is deleted anywhere.
- `pause_scheduling: true` on the server until the owner releases it.
- Tests: `.venv/bin/python -m pytest -q` (4 known environment failures on this PC, listed in memory, are not regressions).

## Review Focus
- A local video retitled after upload (title differs from YouTube): must still match by description head, as `upload.find_interrupted` does.
- A channel with more than 50 uploads: the listing must follow `nextPageToken`.
- Two local folders matching one YouTube video (a doc and a redo): both are reported, neither is silently adopted twice; the one already carrying that id wins.
- An expired YouTube login: `channel-sync` must say so and change nothing.
- Port 8913 already used by a dashboard started from the Desktop copy: the server dashboard must not fight it.

---

### Task 1: channelsync, a read-only check of local records against the channel

**Files:**
- Create: `channelsync.py`
- Modify: `run.py` (command `channel-sync [--apply]`)
- Test: `tests/test_channelsync.py`

**Interfaces:**
- Produces: `channel_videos(yt) -> list[dict]` (every upload: `id`, `title`, `description`, `publishedAt`, `privacyStatus`, `publishAt`), `match(metas: list[dict], videos: list[dict]) -> dict` with keys `adopt` (list of `{slug, video_id, by}`), `conflicts`, `unmatched_local` (approved, no id, not on the channel), `already` (count). `apply(out_dir, plan) -> int` merges `video_id`, `uploaded_at` (= `publishedAt`), `publish_at`, `adopted_from_channel: true` via `records.merge`.

- [ ] Tests: title match; description-head match (>= 40 chars, `compliance.final_description`); paging over two pages; one video claimed by two folders -> `conflicts`, not adopted; a folder already holding an id is never changed; `apply` writes only adopt rows.
- [ ] Implement; CLI prints the plan, writes only with `--apply`; an auth error prints "YouTube login expired or refused: re-run the login" and exits 2.
- [ ] Run tests, commit.

### Task 2: home Compose override and local deploy

**Files:**
- Create: `deploy/home-compose.yml` (worker `cpus: 3`, dashboard `cpus: 2`, both `cpu_shares: 256`, `oom_score_adj: 500`)
- Modify: `deploy/deploy.sh` (`STUDIO_VPS=local` runs the server part on this machine, in `$HOME/$DIR`, without ssh; `first` refuses `local`)
- Test: `tests/test_deploy_local.py` (a temporary HOME with a clone of a bare repo: `deploy.sh dry` prints "DRY RUN" and "Fast-forward: yes"; `docker compose -f docker-compose.yml -f deploy/home-compose.yml config` shows the limits, skipped when docker is missing)
- [ ] Tests fail, implement, pass, commit.

### Task 3: docs
- `docs/HOME_SERVER.md` (owner guide: where it runs, how to open it, how to update, what to do after a power cut, the owner steps), CLAUDE.md top section and `studio-deploy` skill updated from "VPS" to "the owner's PC", the spec updated with the facts of 17 Nov. Commit, full test suite, `deploy/clean_check.sh`, push to `main`.

### Task 4: build the server folder (no code)
- `git clone` of GitHub `main` into `~/studio`; copy from `~/vps-backup-2026-11-13/studio` every file the clone lacks (`rsync -a --ignore-existing`, excluding `.git`, `data`, `output`, `output_old`, `__pycache__`), then the server's two `branding/*.png`.
- `cp -a --reflink=always` the Desktop `data/` and `output/` into `~/studio`.
- Back up `.env` and `autopilot.json`; set `STUDIO_BIND=<this PC's Tailscale IP>`, `STUDIO_HOSTS=<this PC's Tailscale IP>,fedora,<its ts.net name>`, `COMPOSE_FILE=docker-compose.yml:deploy/home-compose.yml`; set `pause_scheduling: true`. chmod 600 on secrets.
- Verify: `git status` clean apart from ignored files; secret files present (names only).

### Task 5: start and reconcile
- Stop the Desktop dev dashboard on 8913 (after checking it runs no job). `docker compose build`, `up -d dashboard`; `/healthz` 200 on 127.0.0.1 and on the Tailscale address.
- `docker exec studio-dashboard python run.py channel-sync` (read), then `--apply`.
- `up -d worker`; both containers healthy; one worker tick in the log; `python risk.py`.

### Task 6: owner steps and report
- The owner runs the two things only they can: GNOME idle suspend off on AC (`gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type 'nothing'`), BIOS "Restore on AC power loss: Power On". The owner releases `pause_scheduling` after reading the channel-sync result.
- Memory and completion report (CLAUDE.md section F).
