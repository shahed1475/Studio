# Nightloom on Cloudflare (path A: free workers.dev)

The Worker serves the website from Workers Static Assets and forwards only `/api/*` and `/privacy.html` to the hub on the server, with a shared secret, so nobody can reach the hub around the Worker's bot check (Turnstile).
Nothing here is switched on until you do the steps below. Secrets are typed into prompts, never into chat, git or a file in this repo.

## Steps (you, about 15 minutes)
1. **Cloudflare dashboard -> Workers & Pages**: pick your free `workers.dev` name once. Your site will be `https://nightloom.<name>.workers.dev`.
2. **Turnstile** (dashboard -> Turnstile -> Add widget): hostname `nightloom.<name>.workers.dev`, mode Managed. Keep the **site key** and the **secret key**.
3. Make the shared secret on your PC: `openssl rand -hex 32` (keep it for the next two steps; do not paste it into chat).
4. **Server**: `ssh -t deploy@vps-ai '~/hub/deploy/hub.sh configure --edge'` and answer the three prompts (edge secret, site key, Turnstile secret). Also set `HUB_PUBLIC_URL=https://nightloom.<name>.workers.dev`, then `~/hub/deploy/hub.sh restart`.
5. **Worker deploy** (in this folder, with Node): `python3 build.py && npx wrangler login` (a browser window asks you to allow it; no token is typed anywhere) then `npx wrangler secret put EDGE_SECRET` (paste the step 3 value) and `npx wrangler deploy`.
6. **Origin**: the Worker reaches the hub at `ORIGIN` in `wrangler.jsonc` (`https://hub.187-127-107-64.sslip.io`). That needs the hub's HTTPS address on the server: `HUB_HOST=hub.187-127-107-64.sslip.io ~/hub/deploy/hub.sh caddy-apply --public` (needs the privacy contact line: `hub.sh configure --contact`, and the allow-list `HUB_ALLOWED_EMAILS` before anyone else may sign up).
7. **Login**: `ssh -t deploy@vps-ai '~/hub/deploy/hub.sh configure'` (Gmail app password, Google client id; add `https://nightloom.<name>.workers.dev` as an authorised JavaScript origin for the client id), restart, then test a real email code and a real Google sign-in.

## Checks that already pass
`node --test cloudflare/worker.test.mjs` (the Worker drops spoofed headers, forwards only the API, answers 404 for anything else), `tests/test_hub_edge.py` (edge secret, Turnstile, same-site check behind the Worker), `tests/test_hub_worker.py`.
Not yet tested: a real deploy, a real Turnstile widget, real mail, real Google sign-in.
