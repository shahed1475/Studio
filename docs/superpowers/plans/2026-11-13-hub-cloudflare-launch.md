# Nightloom on Cloudflare: website, login, launch (research and plan, 13 Nov 2026)

> For agentic workers: executing-plans, task by task. Nothing goes public without the owner's yes (the owner asked on 13 Nov to publish; the inputs below are still theirs).

**Goal:** the Creator Hub (Nightloom: landing site, sign-in, workspace; already built and running privately on the VPS) reachable from the internet through Cloudflare, with a login that really delivers.

## What exists (checked 13 Nov)
- Website, sign-in page (email code, Google ID token) and workspace are served by the hub itself (`hub/web`, container `nightloom-hub`, 127.0.0.1:8931). The code never reaches users yet: no mail is configured, codes land in `~/hub/data/outbox`.
- Cloudflare account (read-only checks): token valid and active; **no domain, no Workers, no tunnels**; the token is **refused** for workers.dev subdomain and Pages (code 10000), so it cannot deploy. The VPS has Caddy on 80/443 (studio-proxy) and no `cloudflared`.

## Research findings (sources: Cloudflare docs read 13 Nov 2026)
1. A Worker with Static Assets is the recommended host for a new site; it gets a free `*.workers.dev` address with no domain, after the owner registers a workers.dev subdomain once in the dashboard.
2. A named Cloudflare Tunnel, Access and Email Service need a domain on the account. A Quick Tunnel (`cloudflared tunnel --url`, trycloudflare.com) needs none but its address changes every start: testing only.
3. Email Service sends to arbitrary users only on Workers Paid ($5 a month; 3,000 mails included): **not free**. Free alternatives: Google sign-in (free, needs the owner's OAuth client id) and Gmail SMTP with an app password (the hub already supports both).
4. Turnstile (bot check) is free and fits the sign-in form.
5. Workers cannot call a raw IP, so a Worker in front of the VPS needs a hostname for the origin (`hub.187-127-107-64.sslip.io` resolves, Caddy can serve it).

## Paths
- **A. Free, no domain:** Worker at workers.dev serves the site and proxies `/api` to the VPS origin; Turnstile on sign-in; the origin accepts only the Worker (shared secret header). Cost $0. Needs: a Cloudflare token with Workers edit (or `wrangler login` by the owner), the workers.dev name, Caddy block for the origin.
- **B. Own domain (about $10 a year at Cloudflare Registrar):** named Tunnel from the VPS (no open port, no Caddy), the site on the domain, Turnstile, optional Access allow-list; Email Service later ($5 a month).
- **C. Test only:** Quick Tunnel, nothing deployed to Cloudflare.

## Tasks (same for A and B unless marked)
1. Design pass on `hub/web` (landing, sign-in, workspace) with the frontend-design skill; real Chrome checks at phone and desktop width.
2. Login that delivers: owner runs `hub.sh configure` (Gmail app password and/or Google client id); test real mail and a real Google click-through.
3. Turnstile on sign-in: widget in `signin.html`, server check in `hub/auth.py` (env `HUB_TURNSTILE_SECRET`, off when unset); tests with a fake verifier.
4. Origin lock (A): env `HUB_EDGE_SECRET`; every request except `/healthz` must carry it; tests.
5. Cloudflare side: `cloudflare/` folder in the repo (A: `wrangler.jsonc`, Worker proxy, static assets; B: tunnel config). Dry-run deploy, then real deploy with the owner's token.
6. Push `feature/hub` to GitHub, deploy the hub image update to the VPS (`hub.sh`), switch on Phase B (allow-list `HUB_ALLOWED_EMAILS`) before any open signup; privacy contact line filled by the owner.

## Owner inputs (not asked for in chat as secrets)
Path A, B or C; Cloudflare token with Workers edit or a `wrangler login`; workers.dev name or domain; Gmail app password and/or Google client id (entered on the server); privacy contact line; allow-list emails.
