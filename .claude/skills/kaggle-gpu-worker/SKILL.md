---
name: kaggle-gpu-worker
description: "Use when preparing, sending or monitoring a Kaggle notebook as a temporary GPU worker for a permitted job; Kaggle is never used for monetized production work while its terms are not cleared."
---

# Kaggle gpu worker (Story Studio)

Kaggle's Terms of Use (version 22 Jun 2025, read 23 Nov 2026): personal, non-commercial use only. Until the owner confirms a task is permitted, every Kaggle job is BLOCKED_PENDING_TERMS_REVIEW (`computerouter.kaggle_gate`).

- Never send production scripts, voice, unpublished video or the owner's private models (`never_send` in `config/compute.json`). Never a second account, never a keep-alive.
- `computerouter.KaggleAdapter.prepare` writes a private kernel package (kernel-metadata.json and run.py) that loads a PUBLIC Hugging Face model by repo id: nothing is uploaded from this PC, and no credential is in the package.
- `KaggleAdapter.submit` pushes only when the gate allows; `KaggleAdapter.status` maps an expired or cancelled session to INTERRUPTED.
- Finite sessions (12 h, unverified) and a 30 h weekly quota (account page, 23 Nov 2026): plan batches, not a server.
- Seen in a real session (23 Nov 2026): 2 x T4.

## Operational worker (24 Nov 2026): `kaggleworker.py`
- Only the owner's PERSONAL, non-commercial task `benchmark` is permitted (`owner_permitted_tasks` in `config/compute.json`); `commercial_use_permitted` stays false; draft permission request: reports/KAGGLE_COMMERCIAL_USE_PERMISSION_REQUEST.md (not sent).
- The owner's file never leaves the PC. A model runs on Kaggle only as a verified PUBLIC TWIN: `kaggleworker.verify_twin` (same SHA-256 and size as the maker's published file, licence on the production list) -> `data/compute/public_twins.json`; the notebook downloads the twin and runs nothing if the hash differs.
- Commands: `python run.py compute kaggle-check` (login without showing it, quota, competitions), `compute kaggle-twin <file> <hf repo> <file name>`, `compute kaggle-test` (push to `NvidiaTeslaT4` with `-t` = `session_cap_s`), `compute kaggle-poll <job>` (status, retrieval into a new `data/compute/kaggle_outputs/<job>/v<n>-<time>/`, manifest SHA-256 check), `compute kaggle-recover <job>` (an interrupted job resumes with its recovered answers skipped).
- `kaggleworker.verify` never lets unproven output become COMPLETED; job ids include the data class (`computejobs.job_id`).
- Login: the `~/.local/bin/kaggle` wrapper reads the token itself; never `kaggle auth print-access-token`, never `config view`.
