# Home server: the studio moves from the VPS to the owner's Fedora PC (design, 16 Nov 2026)

## Why
The VPS subscription has ended (offline since about 16 Nov 2026, Tailscale "last seen 11h ago") and the owner has no money for any paid plan (VPS, Cloudflare Containers or anything else). The studio must keep running for $0, on the owner's own PC, while the PC is also used for Blender and other hobby work.

## Facts this design rests on (checked 16 Nov 2026)
- PC: Fedora 44, i5-9500 (6 cores), 23 GB RAM (about 11 GB in use), GTX 1050 Ti 4 GB, disk 95% full (50 GB free). Docker 29.8 (enabled at boot), Compose v5.5, Tailscale up (`fedora`, 100.66.186.116), cloudflared installed. GNOME suspends the PC when idle on AC (`sleep-inactive-ac-type 'suspend'`).
- Cloudflare's free plan cannot run the studio (long Python + ffmpeg jobs); Cloudflare Containers is paid. Free Cloudflare stays in use for pictures (Workers AI) and can add a Tunnel later.
- The VPS copy of 13 Nov (`~/vps-backup-2026-11-13/studio`) is INCOMPLETE: the transfer broke at 2.4 of 10.7 GB. It holds the code, the secrets and settings (.env, token.json, client_secret.json, llm.json, autopilot.json, settings.json, agent.json: verified identical to the server) and 298 MB of cache, but `data/` and `output/` contain folders with **no files**: the server's upload records, video folders, claim ledgers, action log and growth data are not in it.
- The PC's own working copy (`~/Desktop/Youtube-automation`, branch feature/footage-tool) has 54 video folders and its own `data/`, which only partly overlaps the server's state.

## Goals
1. The studio (dashboard + worker) runs on the PC in Docker, starts by itself after a reboot or power cut, costs $0.
2. Blender and the desktop come first: the studio gets lower CPU priority and a core limit.
3. The dashboard is reachable from the owner's phone through Tailscale (free, private), same login.
4. No video is uploaded twice and nothing reaches YouTube until the owner checks the restored state.

## Non-goals
- The Creator Hub (separate, not live; later).
- Cloudflare Tunnel / a public address (Tailscale is enough and safer; can be added free later).
- Code changes to the studio.

## Anti-goals (a failure even if it "works")
- A video already on YouTube uploaded again because its upload record was lost.
- The development copy on the Desktop mixed up with the running server (two dashboards on port 8913, or tests writing into the live data).
- Deleting anything to make disk space without the owner's yes.

## Approaches considered
- A. Keep the VPS as the always-on part: impossible, the VPS has ended.
- B. **Everything on the PC (chosen by the owner, 16 Nov).**
- C. Cloudflare-only: not possible on the free plan.

## Design (B)
1. **A separate server folder** `~/studio` (not the Desktop working copy): code from the latest pushed `main`, secrets and settings from the 13 Nov backup, `data/` and `output/` from the best available source (see "Open").
2. **Same compose file**, run with an override `deploy/home-compose.yml` that sets: worker 3 CPUs, dashboard 2 CPUs, `cpu_shares` low (256) and `oom_score_adj` raised, so the desktop and Blender win any contention; `restart: unless-stopped`; Docker is already enabled at boot.
3. **Access:** `STUDIO_BIND=100.66.186.116`, `STUDIO_HOSTS=100.66.186.116,fedora` so the phone opens `http://fedora:8913` over Tailscale with the existing login.
4. **Safe start:** dashboard first; worker started with `pause_scheduling: true` and `make_videos` off until the restored upload records are compared with the channel's real uploads (read-only YouTube API listing). The owner then switches them back on.
5. **Stay awake:** stop GNOME's idle suspend on AC (owner's yes; one gsettings line). BIOS "power on after AC loss" is an owner step (no software can do it).
6. **Disk:** a report of what takes space (output_old 3.8 GB, cache 4.5 GB, the Desktop copy) and a warning row; nothing deleted without the owner.
7. **Backups:** the nightly `backup.py` keeps working on the PC; a copy to a second disk or free R2 is a later step.

## Open (owner)
- Can the VPS be switched on again for a few hours (provider panel / grace period) to finish the copy of `data/` and `output/`? If yes, copy first, then move. If no, rebuild the upload records from YouTube and the PC's own `output/`.

## Left to the builder
Exact override values, the order of commands, the read-only YouTube check script.
