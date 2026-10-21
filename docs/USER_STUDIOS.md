# User studios (up to 5 more people, each with their own niche)

Built 21 Oct 2026. Design and decisions: docs/superpowers/plans/2026-10-21-user-side-5-tenants.md. The owner's studio behaves as before: everything here switches on only with `STUDIO_MODE=tenant`.

## How it fits together
- **One folder and two containers per user** on the server (`~/tenants/<name>`, containers `studio-<name>-dashboard` and `-worker`), from the same image and the same code as the owner's studio. Caps: dashboard 256 MB / 0.25 CPU, worker 1.5 GB / 1 CPU, lower priority than the owner's studio. Each user studio has its own container network; its dashboard is published on 127.0.0.1 only.
- **One public address, port 443:** `https://srv2029460.hstgr.cloud`. The server's provider firewall only lets a few ports through (80, 443 and a few others), so custom ports do not work. The invite link `https://HOST/u/<name>/claim?token=...` sets a routing cookie that sends that browser to its own studio (the Caddy proxy, container `studio-proxy`). The proxy removes every other studio's cookies before a request reaches a studio. Limit, said plainly: all user studios share one browser origin, so a bug that let a user run script in their own studio could reach another user's studio in the same browser. Separate origins would need the provider firewall to open one port per user (ports 8921 to 8925), after which the proxy can route by port instead.
- **Users pay for their own AI:** each adds their own OpenRouter key in Settings. Nothing starts until they do: Autopilot, auto-approve, paid models and AI drawing are all off on first run, the daily cap is $1.50, and the research agent only suggests.
- **Storage:** 10 GB per user kept by the app (an hourly check; warn at 80%, new videos paused at 100%, uploaded video files removed after 7 days). **Renders:** at most two at once across all user studios.
- **Safety:** an unclaimed studio serves nothing except its invite page; the invite is valid 24 hours and once; the user chooses their own password (nobody else sees it); five wrong passwords per ten minutes per visitor and 30 across all visitors; the first-password page is counted apart from the login page.

## Owner: commands (on the server, in `~/studio`)
```
deploy/tenant.sh create <name>     # 2 to 15 lowercase letters or digits; at most 5 studios
deploy/tenant.sh caddy             # publish the routes (run after create or remove)
deploy/tenant.sh invite <name>     # prints the link to send; valid 24 h, once
deploy/tenant.sh list              # state and storage; also refreshes data/tenants.json for the Risks card
deploy/tenant.sh sync [name|all]   # copy new code to users (a worker is restarted only when no video renders)
deploy/tenant.sh stop|start <name>
deploy/tenant.sh remove <name>     # moved to ~/tenants-removed, never deleted
```
`deploy/deploy.sh` updates your own studio only; run `deploy/tenant.sh sync all` after it. A crontab line runs `deploy/tenant.sh list` hourly.

## One thing only the owner can do: Google sign-in for users
The studio's current Google client is a *Desktop app* client and cannot send a user back to a web address. Create a **Web application** client once:
1. Google Cloud Console, project "stroy studio", Auth Platform, Clients, Create client, type **Web application**.
2. Authorized redirect URI: `https://srv2029460.hstgr.cloud/oauth/callback` (one address for every user).
3. Download the JSON and copy it to the server as `~/studio/web_client_secret.json`, then run `deploy/tenant.sh sync all`, and copy the same file into each user's folder once (`cp ~/studio/web_client_secret.json ~/tenants/<name>/`, mode 600).
Until that file is there, a user sees "Google sign-in is not set up on this server yet. Ask the owner." and can do everything else.

## User: first steps
1. Open the invite link, choose your email and password.
2. Settings: add your own OpenRouter key.
3. YouTube: Sign in with Google (Google warns the app is unverified: that is expected, choose Advanced and continue).
4. Niche: pick one of ten ready-made niches, or describe your own (it is checked against real Wikipedia articles first). The studio researches it and writes a plan; read it and confirm.
5. Autopilot: turn it on yourself when you want videos made. Every video is still reviewed and uploaded as private with a publish time.

## Niches (the engine's limits)
The studio writes calm narrated stories grounded in a Wikipedia article, with public-domain pictures, and checks every fact against that article. Ready-made: folklore and mystery; ancient civilizations; the medieval world; space history; science and invention history; exploration and shipwrecks; art and architecture; world mythology; documented historical mysteries; remarkable lives. A custom idea passes only when five of eight sample subjects have an article of 1,500+ characters. News, finance, health advice, products, gaming, fitness, politics, children's content and living people are refused with the reason.

## What was verified (21 Oct 2026) and what was not
Verified: the full suite (736 tests); a demo studio on the server end to end (create, publish through the proxy with a real Let's Encrypt certificate, invite, first password, safe defaults, niche refusal without a key, a real fit check and a real niche research with a real model, confirm, worker jobs start only after confirmation); the proxy's cookie stripping with an echo server; all ten presets' subjects against Wikipedia. Not verified: Google sign-in for users (needs the web client above), a real second person using it, a full week of load with five studios rendering. Wikipedia limits requests per address (HTTP 429) and every studio shares the server's address: the studio now spaces requests and waits as told.
