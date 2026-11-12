# Leaving the VPS (13 Nov 2026): plan, research, rules

**Owner's rule (13 Nov): do not delete or change any data.** Every step here only READS from the server (copy to the owner's PC) or builds NEW things beside it. Nothing on the VPS is removed, and nothing is moved: the VPS stays as it is until the new home is proven and the owner says so.

## What the VPS holds (measured 13 Nov)
studio 10 GB (output 3.3 GB, output_old 3.5 GB, cache 1.1 GB, backups 2.0 GB, data 203 MB, root JSON files: token.json, client_secret.json, settings.json, llm.json, autopilot*.json...), hub 192 KB, tenants 4.9 MB (one test studio, Caddy file). 36 videos in output. Images: studio 5.6 GB, nightloom-hub 146 MB. Host: 4 cores, 15 GB RAM (about 5 GB used), 197 GB disk (72% full), up 26 days.

## Research: can Cloudflare run it? (Cloudflare docs read 13 Nov 2026)
- Workers/Pages cannot run the engine (Python, ffmpeg, long renders, files on disk). Already on Cloudflare: the website and the hub's front door (Worker).
- **Cloudflare Containers** can run a Docker image, but: not on the free plan (Workers Paid $5/month, includes 25 GiB-hours memory, 375 vCPU-minutes, 200 GB-hours disk); overage $0.0000025 per GiB-second memory, $0.000020 per vCPU-second CPU (billed on active use), $0.00000007 per GB-second disk; largest instance 4 vCPU, 12 GiB RAM, 20 GB disk. The pages I read do not say the disk survives a sleep (only 20 GB snapshots), so the studio's file-based state (output/, data/, JSON files) would have to be synced to R2 on every start and stop: a large rewrite, not a copy. R2 is not enabled on the account (needs the owner). No GPU mentioned.
- My cost estimate (arithmetic, not from the docs): a 4 vCPU / 12 GiB instance awake 24/7 is about $78/month in memory alone; awake only for renders (about 1.5 h a day) is about $20 to $25/month.
- A named Cloudflare Tunnel, Access and Email Service need a domain on the account; there is none.

## Options for the engine (the 24/7 worker, Autopilot, dashboard)
A. **A new small Linux host** (another VPS, about $4 to $6/month for 4 GB+; or a free-tier VM if the owner has an account, terms and capacity unverified): the same Docker setup moves unchanged (clone repo, restore the copy, `deploy.sh`). Lowest risk.
B. **The owner's PC with Tailscale**: free; the PC is 92% full and loses power sometimes; renders would stop whenever it is off.
C. **Cloudflare Containers**: the closest to "everything on Cloudflare", but needs Workers Paid, R2 and the storage rewrite above; plan it as a project of its own, after A or B keeps the studio alive.
Recommendation: A (or B for free) now, Cloudflare in front for the public parts (done), C later only if wanted.

## Steps
1. DONE: fix the dashboard link (the full Tailscale name was refused: STUDIO_HOSTS now lists vps-ai.tail4c5c78.ts.net; backup .env.bak-hosts-13nov).
2. IN PROGRESS: read-only copy of ~/studio, ~/hub, ~/tenants to `~/vps-backup-2026-11-13/` on the PC (rsync -a, no --delete). Verify by file count and a checksum sample.
3. Owner picks A, B or C and gives the VPS end date.
4. Build the move script and runbook (`deploy/move-host.sh`, docs/MOVE_HOST.md): restore, env, compose, health checks, rollback = keep the old host running.
5. Rehearse on a scratch folder or a second host with the copy (no live traffic), then switch Tailscale name and the Worker's ORIGIN, then stop the old host only when the owner says.
