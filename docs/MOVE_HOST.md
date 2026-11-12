# Moving to a new server (read this when the VPS is ending)

Rule: **nothing is deleted or changed on the old server.** The old server keeps running until the new one is proven.

1. **Copy (done or running):** `~/vps-backup-2026-11-13/` on the owner's PC holds a full read-only copy of `~/studio`, `~/hub` and `~/tenants` (secrets included: keep that folder private, never in git, mode 700).
2. **Get a new server** (owner): Linux with 4 GB+ RAM and 30 GB+ free disk. As its admin install Docker with Compose, then Tailscale (`sudo tailscale up --hostname vps-ai-new`), and open ports 80 and 443 for the hub.
3. From the PC, in order (each step can be previewed with `--dry`):
   - `NEW=deploy@<new-host> deploy/move-host.sh check`
   - `NEW=deploy@<new-host> deploy/move-host.sh studio` (copies, loads the image from the old server, starts only the dashboard; open the printed address and log in with the same password)
   - `NEW=deploy@<new-host> deploy/move-host.sh hub` (copies the hub, puts Caddy in front at `https://hub.<ip>.sslip.io`)
   - `NEW=deploy@<new-host> deploy/move-host.sh verify`
4. **Cloudflare:** change `ORIGIN` in `cloudflare/wrangler.jsonc` (hub branch) to the new `https://hub.<ip>.sslip.io` and run `npx wrangler deploy`. The Turnstile widget, the edge secret and the website address do not change.
5. **Cut over, in this order:** stop the old worker (`ssh deploy@vps-ai docker stop studio-worker`: it stops, nothing is deleted), then `deploy/move-host.sh worker` (it asks you to confirm), then watch the dashboard Activity page for one Autopilot tick. Never run both workers: a video could be uploaded twice.
6. Keep the old server until you are sure. If anything is wrong: `ssh deploy@vps-ai docker start studio-worker` and stop the new one.

Not covered: the YouTube login (token.json) is copied with the studio and keeps working (a Google "testing" login lasts 7 days: docs/GOOGLE_PRODUCTION.md). The Tailscale name `vps-ai` belongs to the old machine: the new one uses `vps-ai-new` until you rename the old one.
