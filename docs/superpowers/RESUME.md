# Where we stopped (2026-10-19, evening)

Say "start from where we stopped" and read this file first.

## State (all checked, all green)
- GitHub: https://github.com/shahed1475/Studio, public, main at commit 21bf5c9, nothing uncommitted. Tests: 328 pass.
- VPS: containers `studio-dashboard` and `studio-worker` healthy, restart `unless-stopped`, Docker starts on boot, listening on loopback only. The worker keeps running when the PC is off.
- Autopilot is OFF on purpose. The growth agent is in hand-off mode (suggests only). Free OpenRouter models: ON on the VPS, OFF on the PC (one shared 45-a-day allowance).
- Channel has 0 uploaded videos. 4 videos are made and checked but not uploaded. 3 older Shorts are plain colour screens (missing footage), not fit to publish.
- Done today: GitHub and VPS rollout, free model chain and picture-check cache, Shorts cut from our own documentaries, camera shots, crossfades, grain, hook title, coloured keyword captions (bottom or top), road to monetization panel, new Videos page grouped by day, review fixes (locks, atomic writes, topic queue).

## Waiting for the owner
1. Answer on deleting old videos: confirm the keep list (suggested: newest Short and newest documentary on the VPS, plus the 3 approved ones). Files are moved to `output_old`, never hard-deleted by us.
2. Watch the ready videos, approve, then turn Autopilot on in the dashboard (each video waits 24 hours before going public, so Hold works).
3. Set the Google OAuth consent screen to "In production", or the YouTube login expires after 7 days.
4. Optional: the Facebook reel they wanted as inspiration needs a login, so ask for a screenshot or a description.

## Next work, in order
1. Look at the VPS after the first 06:30 UTC run: `ssh` then `studio/logs/worker.log`, the Growth tab feed, and that the daily housekeeping line appears.
2. After Autopilot is on: watch the first documentary built on the VPS with free models (time, quality, free requests used). Fix what shows up.
3. Stop making Shorts that are mostly colour screens (tighten `footage.enough_footage`) and re-make the three bad ones.
4. Check the new Videos page on a real phone.
5. Optional, ask first: Pixabay as a second footage source, a downloaded font or Lottie file, YouTube Analytics permission to read watch hours.

## How to resume the pieces
- Dashboard on the VPS from this PC: `STUDIO_VPS=deploy@<vps host> deploy/tunnel.sh`, then http://127.0.0.1:8913 (keep port 8913).
- Local dashboard: `./start.sh`.
- Redeploy after code changes: run the tests, commit, push, `STUDIO_VPS=deploy@<vps host> deploy/deploy.sh`.
- Plans and ledger: `docs/superpowers/plans/2026-10-19-studio-roadmap.md` and `docs/superpowers/ledger-studio-roadmap.md`.
