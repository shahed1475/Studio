Phase 2.2: tts retry (4 tries, waits 1/3/8 s) — fixes 'No audio was received' seen in autopilot.log; tests -> 242 pass
# SDD ledger — plan: docs/superpowers/plans/2026-10-19-studio-roadmap.md
Phase 1: complete. Repo https://github.com/shahed1475/Studio (public, 125 files, secret scan clean). Image builds; 240 tests pass inside the container; libx264 present. VPS: ~/studio, containers studio-dashboard (0.5 CPU, 512m) and studio-worker (2 CPU, 3g), host network, loopback 8913 only, restart unless-stopped, docker enabled on boot. State and 1.9 GB of videos copied by rsync; secrets copied by scp.
Ruling: fonts vendored into static/fonts (Noto Sans, OFL) — Debian's fonts-noto-core lacks the Black/ExtraBold weights — cost if wrong: +2.5 MB in repo.
Ruling: VPS uses the existing custom-ollama container (127.0.0.1:11436, model dolphin3) read-only; I did not pull models into or change other projects' containers — cost if wrong: slow scripts until Phase 2.4 adds free OpenRouter models.
Ruling: autopilot stays disabled after migration (publishing is the owner's decision) — cost if wrong: none until the owner switches it on.
Finding: channel has 0 uploads (10 videos made, 3 approved, 0 uploaded). Fastest lever for the monetization clock is to publish the approved videos.
