# Studio Roadmap: ship, host 24/7, cut cost, more views

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). Each phase has its own checklist; the ledger is `docs/superpowers/ledger-studio-roadmap.md`.

**Goal:** Put the project on GitHub (public, no keys), run it 24 hours a day in a container on the owner's VPS, make each video cheaper to produce, and add the features most likely to bring views and a path to monetization.

**Owner's situation (drives priorities):** very little money, so: no paid APIs by default, every model call measured, and the fastest honest route to the YouTube Partner Program. No setup can promise income by a date; the roadmap only removes what slows it down.

## Research facts used (secondary sources, verify on YouTube's own pages)
- Early tier (fan funding): 500 subscribers + 3 public uploads in 90 days + 3,000 watch hours (12 months) or 3M Shorts views (90 days). Full tier (ads): 1,000 subscribers + 4,000 watch hours or 10M Shorts views (90 days). Reported from 1 Feb 2027 for new applicants: 8,000 hours or 20M Shorts views (unconfirmed).
- YouTube's "inauthentic content" policy targets generic, repetitive, template-style output (AI voice over recycled footage). AI itself is allowed. So: original scripts, a real angle, variety, and human review are part of the product, not extras.
- Good Shorts from long videos: a self-contained 30 to 60 second moment, a rebuilt first-3-seconds hook, a visual change about every 4 seconds, captions, an ending that points to the full story. Retention falls as length grows (about 15s: 85-95%, 60s: 50-65%).
- Hard rule kept: Shorts are cut only from **our own** long videos. Never from other creators' videos.

## Global Constraints
- Never commit secrets: `.env`, `client_secret.json`, `token.json`, `settings.json`, `llm.json` stay out of git. The VPS address and user never appear in committed files (they come from environment variables).
- Containers publish only to `127.0.0.1` on the VPS (the dashboard has no login). Access is by SSH tunnel.
- On the shared VPS: touch only `~/studio` and the two `studio-*` containers; CPU and memory limited; no changes to other projects.
- Autopilot stays **off** after migration. Turning it on publishes to the real channel, so the owner does that.
- No new paid services. Dashboard text is plain, no em-dashes.

## Phase 1: Ship and host (build first, it unlocks 24 hour running)
- [ ] 1.1 `.gitignore`, `.dockerignore`, `requirements.txt`; secret scan of every tracked file.
- [ ] 1.2 `worker.py`: pure `due_jobs(now, last)` plus a loop that runs autopilot tick (30 min), the growth agent (daily 06:30), and news/trends/channels (Monday 09:00). Tests first.
- [ ] 1.3 `dashboard.py`: `STUDIO_HOST` env for the bind address; run jobs with `sys.executable`; "timer installed" also true when the worker runs.
- [ ] 1.4 `Dockerfile` (python slim + ffmpeg with libx264 + fonts), `docker-compose.yml` (services `studio-dashboard`, `studio-worker`, `restart: unless-stopped`, host network, CPU 2, memory 3g), `deploy/deploy.sh`.
- [ ] 1.5 Build the image locally, run the test suite inside it.
- [ ] 1.6 GitHub: public repo `Studio`, one clean commit, push.
- [ ] 1.7 VPS: clone, copy secrets and state by `scp`/`rsync` (not git), `docker compose up -d`, verify dashboard through a tunnel and one worker cycle.

## Phase 2: Audit and cost cut
- [ ] 2.1 Measure: tokens and seconds per Short and per documentary from `data/llm_usage.json` and real runs.
- [ ] 2.2 Fix what the audit finds (known: `make_short` failed once with "No audio was received" from edge-tts: add retry and voice fallback; stray `-encoders` file).
- [ ] 2.3 Cheaper: smaller prompts, one call where two are made, cache, free models first, local model only as fallback.
- [ ] 2.4 **(owner request)** Local Ollama on the VPS CPU is slow. Research OpenRouter free models (limits per day and per minute, quality for JSON scripts, which are reliable) and make them the first choice with the local model as the backup. Add a model health check so a rate-limited or dead free model falls through to the next one, and the dashboard shows which model wrote each script.

## Phase 3: Shorts from our own long videos
- [ ] 3.1 `clipper.py`: from a documentary's lines and chapters pick 1 to 3 self-contained 30 to 50 second windows; new hook line; end line pointing to the full video.
- [ ] 3.2 Re-render vertical from the same scene images and narration (no re-download), with large captions.
- [ ] 3.3 Autopilot makes them after each documentary; reviewer checks them.

## Phase 4: Animation
- [ ] 4.1 More motion in `render.py`: pan and parallax variants, crossfades, vignette and grain.
- [ ] 4.2 Animated text cards (date, place, quote with source) drawn with Pillow and ffmpeg.
- [ ] 4.3 `animation_style` in the edit profile so the growth agent can pick one.

## Phase 5: Road to monetization
- [ ] 5.1 Dashboard panel: subscribers against 500 and 1,000, Shorts views in 90 days against 3M and 10M, uploads in 90 days against 3. Watch hours need the YouTube Analytics permission and are shown as "needs permission" until granted.
- [ ] 5.2 The growth agent reads this progress and says what is the nearest gap.

## Review Focus
- A secret ends up in the repo or image: scan before commit; `.dockerignore` matches `.gitignore`.
- Worker crashes or the VPS reboots: compose restarts it; a missed slot runs once on the next loop, never twice.
- Two jobs at once (dashboard button and worker): existing locks must win; the second skips.
- Container has no systemd, no GUI: `notify-send` absence must not break anything.
- Disk fills (videos are large): worker prunes `cache/` and rendered work folders older than a limit.
