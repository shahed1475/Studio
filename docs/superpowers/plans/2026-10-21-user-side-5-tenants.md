# User side: five more studios on this server, each with its own niche

> Status: the owner decided on 21 Oct 2026: each user brings their own OpenRouter key, public HTTPS on the free hostname, a fixed list of niches the engine does well plus a fit check for custom ones. Execution below, step by step, test first. The main studio behaves as today unless `STUDIO_MODE=tenant` is set.

**Goal:** up to 5 more people can open a studio like the owner's from any device, sign in, connect their own YouTube channel, pick a niche, and have the automation research that niche and prepare videos for it. The owner's studio keeps working exactly as today.

## What the code and the server say (all VERIFIED on 21 Oct 2026)
- **The app is single-tenant by construction.** `config.ROOT = Path(__file__).parent`, so the data, videos, secrets (`token.json`, `client_secret.json`, `settings.json` with the OpenRouter key), the niche (`niche.json`) and the one dashboard login all live next to the code. Fully separate users therefore means separate copies of the code folder (4.8 MB each, no videos), each with its own containers. That needs **no change to how the main studio works**.
- **Server:** 4 vCPU, 15 GB RAM (about 10 GB free), 79 GB disk free (ext4, 59% used), shared with about 25 other containers. The deploy account has **no sudo**, so no disk quotas or loopback mounts. Ports 80 and 443 are free; no web proxy runs. The free hostname is `srv2029460.hstgr.cloud`. Today the main studio worker may use 2 CPU and 3 GB.
- **The engine does one kind of video well:** a narrated story grounded in a Wikipedia article, public-domain pictures plus labelled AI storybook art, facts checked against that article. News, finance, reviews, gaming, fitness, living people and anything that cannot be grounded in an encyclopedia are outside what it can do honestly.
- **Login protection exists:** hashed password, server-side sessions, five wrong tries per ten minutes per address. **YouTube connect does not work for remote users today:** it opens a browser on the server itself.
- **YouTube limits are per Google project, shared by everyone:** 100 uploads a day (we need about 2 each) and 10,000 other units a day (research uses about 600 to 1,000 per user per day).

## Design (my calls, marked; the owner decides the three in "Decisions")
1. **One folder, one pair of containers per user** (`~/tenants/<name>`, compose project `studio-<name>`, own port 8921 to 8925). Caps per user: dashboard 256 MB and 0.25 CPU, worker 1.5 GB and 1 CPU, lower CPU priority than the owner's studio. *(My call.)*
2. **Features for users are switched on by `STUDIO_MODE=tenant`.** Without it the code behaves exactly as now, which the full test suite proves. *(My call.)*
3. **Storage without root:** a per-user limit of 10 GB enforced by the app (hourly size check, a warning at 80%, new videos paused at 100%), uploaded video files removed after 7 days (`STUDIO_PRUNE_UPLOADED_DAYS`, exists today), archived videos cleaned. At one documentary and one Short a day a user needs about 2 GB steady. Five users reserve 50 GB; the host keeps 29 GB.
4. **Render gate:** at most two videos render at once across all users and the owner, so ten free GB are never exceeded. Waiting users see "queued".
5. **First sign-in by invite link** (valid 24 hours): the user sets their own password; nobody else ever sees it.
6. **Everything starts safe:** Autopilot off, auto-approve off, AI drawing off until the user adds an OpenRouter key, daily cap $1.50.
7. **YouTube connect for remote users:** a normal "Sign in with Google" web flow on the user's own address. The owner adds each user address as a redirect link on the Google OAuth client (the owner's click; I give the exact text).
8. **Niche wizard:** the user picks one of the niches the engine can do well, or describes their own. The studio checks the fit (can five real Wikipedia articles be found, is the topic not on the unsuitable list), then researches the niche with the tools it already has (trend study, reference channels, topic ideas screened for false premises), writes the niche settings, a plain-language brief (audience, style, cadence, first topics) and a first topic queue. The user can edit the brief before Autopilot is turned on.

## Steps (test first for code; each ends with the full suite and a check on a demo user)
1. Provisioning script `deploy/tenant.sh` (create, list, stop, remove, sync code, quota) and compose template. No app code. Demo user on loopback only.
2. `STUDIO_MODE=tenant` defaults (Autopilot off, cap, AI art off).
3. Invite link and first-password page.
4. Render gate and quota guard.
5. Public HTTPS: a Caddy container on 443 and ports 8921 to 8925 for `srv2029460.hstgr.cloud`; `STUDIO_HOSTS` set; the owner's studio stays Tailscale-only (checked).
6. Web Google sign-in for users.
7. Niche wizard and niche-aware research (`search_seeds` in the niche file, default unchanged).
8. End-to-end demo user, Risks row "user studios", docs.

## Limits to say out loud
- A niche outside the engine's strengths is refused with a reason, not faked.
- Five users share one Google project: one bad user can hurt everyone's quota. The per-user upload cap and research throttle limit that.
- Unverified-app warning shows for every user at Google sign-in; allowed up to 100 users.
- Each user's videos are their responsibility on their own channel; the same review rules apply.

## Decisions (made by the owner, 21 Oct 2026)
1. Who pays for AI (OpenRouter): **each user adds their own key** (recommended) or the owner pays for everyone.
2. How users reach their studio: **public HTTPS on `srv2029460.hstgr.cloud`** (recommended, protected by the login) or only through Tailscale invites.
3. Niche scope: **niches the engine can ground in Wikipedia, with a fit check for custom ones** (recommended), not "any niche".

## Implementation tasks (interfaces fixed here so each step can be checked)
Every Python step: failing test first, then code, then the whole suite (`.venv/bin/python -m pytest -q`) before commit. Server steps are checked on a demo user named `demo`.

**T1 `tenantmode.py`** (tenant defaults, quota, render gate, invites on the command line)
- `is_tenant() -> bool` (`STUDIO_MODE=tenant`).
- `apply_defaults(root=config.ROOT)`: first run only (marker `data/tenant_ready.json`): `autopilot.json` enabled false and auto_approve false, `llm.json` enabled false, cap 1.5, ai_art false, `agent.json` mode "handoff".
- `usage_gb(root) -> float`; `quota_state(root, limit_gb=10) -> {"used_gb", "pct", "state": "ok"|"warn"|"full"}`; `enforce_quota(root, now)`: at "full" sets `make_videos` false in autopilot.json and writes one Activity event, remembering that it did; below 90% it restores only what it paused.
- `render_gate(slots=2)`: context manager; a no-op unless `STUDIO_RENDER_GATE` names a directory; otherwise waits for one of `slots` file locks there. Wrapped around `render.render`.

**T2 invites (`webauth.py`, `dashboard.py`)**: `create_invite(hours=24) -> token` (only the hash is stored in `data/invites.json`), `claim(token, email, password)` (valid once, only while no login exists, 10+ character password). In tenant mode with no login yet the dashboard answers only `/claim`, `/healthz` and static files (it never serves the studio to an unclaimed address). `python tenantmode.py invite <base_url>` prints the link.

**T3 niches (`niche.py`)**: `PRESETS` (ten, each with id, name, audience, style, channel_angle, hashtags, search_seeds, starter_topics); `fit_check(description, chat, article_of) -> {"fit": bool, "reason": str, "closest": id|None}` (word filter for unsuitable subjects, one model judgement, five sample topics each needing a real article of 1,500+ characters, article reads retried as in `topicrank.read_article`); `build(choice_or_description, chat) -> niche dict`; `research(niche, yt=None, chat=None) -> brief` (trend study when YouTube is connected, ten topic ideas screened by `topicrank.premise_check`, cadence and format advice); `apply(niche, brief)` writes `niche.json` (adds `id`, `search_seeds`), `data/niche_brief.json`, the topic queue. `discover.SEEDS` and `trendwatch.SEEDS` read `niche["search_seeds"]` when present.

**T4 dashboard (tenant mode only)**: "Get started" card (key, YouTube, niche, Autopilot) and a Niche page with the presets, the custom box, progress, the brief and an Edit/Confirm step. APIs `/api/niche`, `/api/niche/choose`, `/api/niche/custom`, `/api/niche/confirm`.

**T5 `deploy/tenant.sh` and `deploy/tenant-compose.yml`**: `create <name> <port>`, `invite <name>`, `list`, `stop`, `start`, `sync [name|all]`, `remove <name>` (archives, never deletes), `quota`. Copies code only (never `.env`, settings, llm.json, token, data, output), copies `client_secret.json` mode 600, per-user caps: dashboard 256 MB / 0.25 CPU, worker 1.5 GB / 1 CPU / low priority.

**T6 public HTTPS**: Caddy container (host network) with a generated Caddyfile for `srv2029460.hstgr.cloud` on 443 and one port per user (8921 to 8925); `STUDIO_HOSTS` per user; the owner's studio unchanged and Tailscale-only (checked).

**T7 `ytweb.py`: Google sign-in on the web**: `start(redirect_uri, email) -> url` and `finish(code, state, redirect_uri)` with state and PKCE verifier kept 10 minutes, then the same token file and `ytlogin.stamp`. **Needs a "Web application" OAuth client** (the current one is a Desktop client, which cannot take a web redirect): the owner creates it and copies `web_client_secret.json` to the server; I write the exact steps.

**T8 proof**: demo user end to end (create, claim, key, niche, research brief), the owner's studio re-checked, Risks row "user studios" (count, disk per user, last quota state), docs and CLAUDE.md.
