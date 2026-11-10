# Creator Hub deploy plan (10 Nov 2026): a plan only, nothing here has been run on the server

> Written for the owner to read and decide. Every step that touches the server, a domain, an account or the public internet waits for the owner's yes. Execution later: superpowers:executing-plans, one task per commit, `deploy/deploy.sh dry-run-first` rules from `.claude/skills/studio-deploy/SKILL.md`.

**Goal:** Run the Creator Hub (`hub/`, branch `feature/hub`) on the VPS as a third, separate service that creators reach over HTTPS, without putting the owner's studio, its secrets, its videos or its renders at risk.

## 1. What I read (evidence, 10 Nov 2026)

- The studio runs as two containers from one image `studio:local` (Dockerfile: python 3.13-slim with ffmpeg), the whole project folder mounted at `/app`, host networking, owner dashboard on port 8913 through Tailscale (`docker-compose.yml`).
- User studios run in their own container networks and are published on `127.0.0.1` only; a Caddy container is the only thing the internet reaches, on 443 at `https://srv2029460.hstgr.cloud`. Its Caddyfile is **generated** by `deploy/tenant.sh caddy` and routes by a `studio_tenant` cookie on that one host (`docs/USER_STUDIOS.md`, `deploy/tenant.sh`). The provider firewall lets 80 and 443 through; a real Let's Encrypt certificate has been issued there before.
- `deploy/deploy.sh` rebuilds and restarts the owner's containers whenever `Dockerfile`, `requirements*.txt` or `docker-compose.yml` change, and refuses while a render runs (`FORCE=1` overrides). **My `cryptography` line in `requirements.txt` would therefore force a rebuild at the owner's next deploy.**
- Tested here: the hub's imports (`config`, `niche`, `wikipedia`, `hub.server`) work on a read-only copy of the tracked files and write nothing at import. The hub pulls three studio modules through `niche` (`filelock`, `topicqueue`, `topicrank`).
- The hub's own needs: `requests`, `cryptography`, `google-auth` (installed in the dev venv; the minimal list for a slim image is still to be proven by a build, Task 1).
- Not known and not guessed: the VPS's free memory and CPU, its public IP, whether a domain exists, whether Tailscale HTTPS (`tailscale serve`) is enabled (UNVERIFIED).

## 2. Design decisions (my calls; each can be overruled)

1. **A separate image and container, not the owner's.** `deploy/Dockerfile.hub` (slim, no ffmpeg) with the tracked code copied in and its own `deploy/hub-requirements.txt`. The owner's `requirements.txt` goes back to what it was, so the owner's next deploy does not rebuild. Reason: the hub is public-facing; the owner's folder holds `.env`, `token.json`, `llm.json`, videos. **The hub never mounts `/app` of the owner's studio.**
2. **Hardened container:** non-root user, `read_only: true`, `tmpfs: /tmp`, `cap_drop: [ALL]`, `no-new-privileges`, `mem_limit` 256m, `cpus` 0.5, its own Docker network, published on `127.0.0.1:8931` only. Writable mounts: `~/hub/data` (database) only. Secrets: an owner-only env file `~/hub/secrets/hub.env` mounted read-only (mode 600, delivered by `scp`, never git), master key for stored AI keys in it as `HUB_KEYSTORE_KEY` (kept out of the data folder so a database backup does not carry the key to decrypt it).
3. **Its own hostname.** The hub uses absolute paths (`/api/...`, cookies with `Path=/`) and cannot live under a path of the studios' host, whose root is taken by cookie routing. So it needs its own host name (a domain or subdomain pointed at the server). This is the owner's decision and gates the public step.
4. **Caddy:** the generator in `deploy/tenant.sh` gets one extra site block for the hub host (`reverse_proxy 127.0.0.1:8931`), added only when `HUB_HOST` is set, tested with a unit test of the generated text. The studios' block is not changed. `HUB_TRUST_PROXY=1` so rate limits use the real client address Caddy forwards.
5. **Three phases:** (A) private trial on the owner's PC and Tailscale only; (B) the same container behind Caddy on the new hostname, closed to the public by a sign-in allow-list of a few emails for a week; (C) open sign-up. Each phase is a separate yes.
6. **Hub-wide guards that must exist before any public phase** (code, test first): a hub-wide cap on Wikipedia reading (many accounts together must not draw HTTP 429 on the server's one address, which also serves the studio's own research); a hub-wide daily cap on sign-in emails (a Gmail account has a daily sending limit; the figure for a personal account is UNVERIFIED); a sign-up allow-list switch (`HUB_ALLOWED_EMAILS`).

## 3. Tasks

**Phase 0: the owner provides (nothing I can do):**
- A host name for the hub and its DNS record pointing at the server (or a decision to stay in phase A).
- A mail setup: the Gmail app password via `python -m hub.configure` is a stopgap; for phase C a mail service on the owner's domain.
- The Google Web client id with the real origin `https://<hub host>` added (Google's page: origins are scheme plus host; read 10 Nov 2026), and whether the app needs Google's consent-screen steps for public use (UNVERIFIED: read Google's pages first).
- A privacy page text decision (what is kept: email, niche, research, encrypted AI key, audit log; how to delete an account).

**Phase 1: code and files, all local, tests first (no server):**
- Task 1: `deploy/Dockerfile.hub`, `deploy/hub-requirements.txt`, `deploy/hub-compose.yml`; `docker build` locally and run it with a fake data folder: health check 200, signed-in flow in real Chrome, a write attempt outside `/app/data` fails (read-only proof). Revert the `cryptography` line in `requirements.txt` (moves to the hub list).
- Task 2: `deploy/hub.sh` (modelled on `tenant.sh`): `build`, `up`, `down`, `status`, `logs`, `backup`, `caddy-block` (prints, does not apply), `rollback`. Dry-run mode like `deploy.sh`. Shell checks plus a Python test of the generated compose and Caddy text (no secrets in them, loopback only, read-only, limits present).
- Task 3: the three guards in 2.6 with failing tests first, plus mutation checks.
- Task 4: `hub/web/privacy.html` (text only after the owner decides what is kept) and an account delete button (`POST /api/account/delete`: cascades the research, key and sessions, audit rows keep no personal text); linked from the footer and sign-in page.
- Task 5: backup: nightly `sqlite3 .backup` of `~/hub/data/hub.db` to a folder outside the container, seven kept (same rule as `backup.py`); restore tested once on a copy; a Risks-card row "Creator Hub" (up, last backup age, failed sign-in emails today) read from a small status file the hub writes.

**Phase A: private trial (needs the owner's yes):** `scp` the env file; `deploy/hub.sh build && up` bound to the Tailscale address; owner signs in, adds a (their own) key, runs research.
**Phase B: public with allow-list (needs the owner's yes and Phase 0):** Caddy block applied through the generator; check certificate, headers (HSTS, CSP), sign-in from a phone, Google button on the real host; one week with only listed emails.
**Phase C: open sign-up (needs the owner's yes):** remove the allow-list; watch the Risks row and the audit table for sign-in failures and sign-in email volume.

## 4. Rollback and safety

- `deploy/hub.sh down` stops the hub; data stays; the studios' containers are untouched throughout (different compose project, network, image, folder). Removing the hub's Caddy block and re-running `tenant.sh caddy` restores the old proxy text exactly.
- The hub container cannot read the owner's `.env`, tokens, videos or settings: they are not in its image or mounts.
- Never deploy while a render runs (the hub's own deploy does not touch the worker, but the shared `docker compose` habits stay the same).

## 5. Risks and limits (honest)

- Public sign-in invites abuse: per-IP and per-email limits exist (tested), the new hub-wide caps are Task 3; a determined attacker with many addresses is not stopped by these alone.
- Gmail is a stopgap sender: sign-in codes from a personal address to strangers may land in spam; the daily limit is UNVERIFIED.
- Each creator's research runs read Wikipedia from the server's address; the new cap protects the studio's own research.
- The hub's agents are model output: facts need sources (labels already say so).
- The render engine still serves at most five user studios; the hub does not render videos for hub accounts yet.
- Sizing: unknown until the owner (or I, with a yes) checks the server's free memory; the hub is budgeted at 256 MB plus its Docker overhead.

## 6. What needs the owner's yes (in order)

1. The design above (separate image, own hostname, three phases).
2. A hostname/domain, or "stay private for now".
3. Phase 1 work (local only): I can do it now.
4. Merging `feature/hub` into `main` and pushing (the server pulls `main`).
5. Each phase A, B, C, and the mail provider and Google settings.

## Status after Phase 1 (10 Nov 2026): all local, nothing run on the server

Done, test first, committed: Task 1 `deploy/Dockerfile.hub`, `hub-requirements.txt`, `hub-compose.yml`; Task 2 `deploy/hub.sh` (check, build, up, down, status, logs, backup, caddy-block) and a non-fatal hub hook in `deploy/tenant.sh`; Task 3 the guards (sign-up allow-list for email and Google, hub-wide Wikipedia cap, hub-wide sign-in email cap, per-IP daily email limit); Task 4 `privacy.html`, `POST /api/account/delete` and a "Your data" panel; Task 5 backup (in `hub.sh`, seven kept). The studio's `requirements.txt` is unchanged (the `cryptography` line moved to the hub list).

Evidence (this PC): hub suite 247 passed, 1 skipped; project suite 2,412 passed, 1 skipped, 1 failed (`tests/test_depth_model.py`, needs `data/models` of the main checkout; same as before). 20 mutation checks, 20 killed (one survivor found a missing test, now added). The real Caddy binary validated the generated block ("Valid configuration"). A real image was built (215 MB) and run through `hub.sh up`: health 200, read-only root, no capabilities, 256 MB, non-root, own network, loopback port only, only the data folder mounted, no secret-looking file in the image. In real Chrome against that container: live Wikipedia research (5 topics in 6 s, 1 unreadable counted), privacy page, wrong word then right word to delete an account, old cookie refused, and the real database file no longer held the email or the research text. `hub.sh backup` kept seven copies, mode 600, integrity ok. `hub.sh up --public` refused with the test setup (dev flag). Test containers, image and folder were removed afterwards; the base images `python:3.14-slim` and `caddy:2` are now cached on this PC.

Not done, on purpose: the Risks-card row "Creator Hub" (needs a studio-side change and the server's real folder layout: do it in Phase A); scheduling the nightly backup (a server cron line: Phase A); the owner's contact line in `privacy.html` (the marker `OWNER-TO-FILL` blocks `up --public` until it is written); reserving part of the email budget for existing accounts (it would reveal whether an address has an account, so it is a Phase C design decision); the privacy page is a draft for the owner and a lawyer-free plain-language text, not legal advice.

Security review notes (automated, 10 Nov): the hub-wide email cap can be drained by many sources; mitigated by the allow-list (Phases A and B), the per-address hourly limit, and the new per-IP daily limit; the residual risk (many IPs in open sign-up) stays for Phase C.

## Operator runbook for Phase A (needs the owner's yes first)

1. On the server: `mkdir -p ~/hub/secrets` ; `scp` the env file to `~/hub/secrets/hub.env` ; `chmod 600` it. It holds `HUB_KEYSTORE_KEY` (a Fernet key), `HUB_PUBLIC_URL`, the mail settings (or `python -m hub.configure` output), `HUB_ALLOWED_EMAILS`, optionally `HUB_INSECURE_DEV=1` for a private http trial only.
2. In a clone of the repo at the merged commit: `deploy/hub.sh check`, then `deploy/hub.sh build`, then `deploy/hub.sh up` (add `--public` only in Phase B).
3. Look: `deploy/hub.sh status`, `deploy/hub.sh logs`, `curl http://127.0.0.1:8931/healthz`.
4. Rollback: `deploy/hub.sh down` (data stays in `~/hub/data`).
5. Nightly backup: a cron line running `deploy/hub.sh backup` (never while the owner's deploy is running a rebuild).

## Phase A is live on the server (10 Nov 2026, the owner said: host it in the cloud so it stays always live)

Done by shipping a locally built image (no git push, nothing in GitHub): `docker save | ssh docker load`, files copied to `~/hub/deploy/` (hub.sh, hub-compose.yml), settings file `~/hub/secrets/hub.env` made ON the server (master key generated there, never shown; mode 600), started with `~/hub/deploy/hub.sh up` after a dry run. Container `nightloom-hub`, compose project `hub`, restart policy `unless-stopped`, Docker enabled at boot. Reachable on the server's loopback only (`127.0.0.1:8931`); from the owner's PC through an SSH tunnel: `ssh -N -L 8931:127.0.0.1:8931 deploy@vps-ai` then http://localhost:8931. Dev flag `HUB_INSECURE_DEV=1` is set (private trial only; `hub.sh check --public` refuses it).

Verified on the server: health 200; read-only root, no capabilities, 256 MB (uses about 25 MB), user 1001, own network, only the data folder mounted; the studio containers kept their uptimes (worker 11 days, dashboard, proxy) and no render was running; real Chrome through the tunnel: sign-in, workspace, live Wikipedia research from the server (5 topics, 6.7 s), account deletion, and the email gone from the server's database file; a deliberate kill -9 of the hub process: Docker restarted it by itself, back in 1.7 s, session and stored research intact.

Found by deploying and fixed with tests first: (1) the setup prompt would have dropped the server's other settings (master key, public address, allow-list) when saving Gmail details: `HUB_KEYSTORE_KEY`, `HUB_PUBLIC_URL`, `HUB_ALLOWED_EMAILS`, `HUB_MAIL_DAILY_CAP`, `HUB_INSECURE_DEV` are now preserved; (2) the workspace showed an empty team whenever the address in the browser differed from `HUB_PUBLIC_URL` (the page fetched absolute card addresses and its CSP only allows its own origin): it now asks the path at its own origin (a real-Chrome regression test). New in `hub.sh`: `restart` (recreate, so changed settings are read) and `configure` (the Gmail and Google prompt in a throwaway locked-down container: `ssh -t deploy@vps-ai '~/hub/deploy/hub.sh configure'` then `hub.sh restart`).

Not done, with reasons: the public address (needs a hostname: the owner's decision); Gmail and Google settings (need the owner's secrets); nightly backup (the server has no `crontab`; the studio schedules inside its worker; proposal: a small daily self-backup inside the hub, or a systemd timer); a restart alert (Docker restarts a crashed hub, but a hung one that stays "unhealthy" is not restarted by plain compose).

## Public trial prepared (10 Nov 2026): the owner chose the free name `hub.187-127-107-64.sslip.io`; not switched on yet

The name resolves to the server (187.127.107.64). Switching it on is Phase B and needs three things only the owner can give (below), so the hub is still private. Built and tested for it (265 hub tests pass, 12 mutation checks killed): `HUB_CONTACT` (the privacy page's contact line is a setting the server fills in as escaped text; `hub.sh check --public` now FAILS CLOSED without it: the earlier page-file check would have passed silently on the server because the file is not there); `hub.sh configure --contact`; `hub.sh caddy-merge` and `caddy-apply` (the studio's proxy file is generated by `tenant.sh`, and the proxy container bind-mounts that single file, so apply validates with real Caddy first, writes IN PLACE, reloads gracefully, keeps `Caddyfile.bak-before-hub`, and restores the previous file if the reload is refused; tested end to end with a stand-in `docker`, including inode unchanged and rollback). On the server: the merge of the hub block into a copy of the live `~/tenants/caddy/Caddyfile` adds only the hub block and real Caddy says "Valid configuration"; the live file was not touched. The tests' fake AI keys no longer match OpenRouter's real key format (a push could have tripped secret scanning).

Known caveat: `deploy/tenant.sh caddy` rewrites the proxy file and drops the hub block; run `hub.sh caddy-apply --public` again after it (the block carries that note), until the tenant.sh hook is merged into main.

Owner inputs for Phase B: (1) the contact line: `ssh -t deploy@vps-ai '~/hub/deploy/hub.sh configure --contact'` (public text, a name and an email or web address; nobody else's choice); (2) who may sign up in the closed trial (emails or @domains) for `HUB_ALLOWED_EMAILS`; (3) a way to receive sign-in codes: the Gmail app password (`ssh -t deploy@vps-ai '~/hub/deploy/hub.sh configure'`) and/or a Google Web client id with `https://hub.187-127-107-64.sslip.io` as an authorized JavaScript origin. Then: set `HUB_PUBLIC_URL=https://hub.187-127-107-64.sslip.io`, remove `HUB_INSECURE_DEV`, `hub.sh restart`, `HUB_HOST=hub.187-127-107-64.sslip.io hub.sh caddy-apply --public`, check the certificate (Caddy tries Let's Encrypt and falls back to ZeroSSL; sslip.io shares Let's Encrypt's per-domain limit with all its users, so a first attempt can fail), test sign-in on the real address.
