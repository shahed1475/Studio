# The studio on your own PC (since 17 Nov 2026)

Hostinger deleted the VPS and everything on it. The studio now runs on this Fedora PC, for $0.

## Where things are
- **The running studio:** `~/studio` (its own folder). Do not edit files there by hand.
- **Your workshop:** `~/Desktop/Youtube-automation` (code changes, tests). It is NOT the running studio.
- **Open the dashboard:** on this PC `http://127.0.0.1:8913`; on your phone (Tailscale on) `http://fedora:8913`. Same login as before.
- A dashboard started from the Desktop folder must use another port: `DASH_PORT=8914 .venv/bin/python dashboard.py`.

## It starts by itself
Docker starts at boot and brings back `studio-dashboard` and `studio-worker` (restart unless-stopped). Check: `docker ps`.

Two things only you can set, once:
1. The PC must not fall asleep: `gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type 'nothing'`
2. In the BIOS (press Del or F2 at start): "Restore on AC power loss" = **Power On**, so the PC starts again after a power cut.

## Blender comes first
The studio may use at most 3 cores (worker) and 2 (dashboard), with a low CPU weight, so Blender and the desktop win. Heavy studio renders will be slower while you work. To pause the studio completely: `cd ~/studio && docker compose stop worker` (start again: `docker compose up -d worker`; never while a render runs: `docker top studio-worker | grep run.py`).

## Updating the code
From the Desktop folder, after the tests pass and the commit is pushed to `main`:
`STUDIO_VPS=local deploy/deploy.sh dry-run-first`

## What was lost with the VPS
The server's video folders and records (upload records, claim ledgers, action log, growth numbers, owner tasks, approved rule values) were not in the 13 Nov copy. `~/studio` was rebuilt from the copy's code, secrets and settings plus this PC's own videos and data. `python run.py channel-sync` compares local records with the channel (read only); `--apply` writes the real YouTube ids so nothing is uploaded twice. Videos already scheduled on YouTube publish by themselves.

## Disk
The disk is about 95% full. The studio's folder shares space with the Desktop copy by btrfs reflinks (no double space until files change). Nothing is deleted automatically.
