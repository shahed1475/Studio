# User side: five more studios on this server, each with its own niche

> Status: research done, plan written, **waiting for the owner's three decisions** (section "Decisions"). Nothing below is built yet. The main studio is not touched by this document.

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

## Decisions (needed before step 1)
1. Who pays for AI (OpenRouter): **each user adds their own key** (recommended) or the owner pays for everyone.
2. How users reach their studio: **public HTTPS on `srv2029460.hstgr.cloud`** (recommended, protected by the login) or only through Tailscale invites.
3. Niche scope: **niches the engine can ground in Wikipedia, with a fit check for custom ones** (recommended), not "any niche".
