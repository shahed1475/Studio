# Recovery tests: worker kill, network loss, restarts (23 Nov 2026)

Sub-plan 7 of the owner's master mission of 22 Nov 2026. Work done in `~/studio` (the workshop was not used). Builds on
`LOAD_SHEDDING_AND_RENDER_RECOVERY.md` (20 Nov: scenes, voice lines and the final file resume after a SIGKILL, drills 1 and 2) and
`POWER_LOSS_AND_RECOVERY.md` (21 Nov: one real power cut checked, the final pass in parts, drill 3). Those proved the render. This step tested what
they did not: the whole worker **container** dying, the network going away, and restarts. No video, schedule, upload, approval or channel setting
was touched. Nothing was spent.

## 1. Drill 4: the worker container killed in the middle of a render (live, 07:05 UTC)

Why: the host ran out of memory on 22 Nov at 16:07 UTC and the kernel killed the worker container's pid 1, not only one render. Drills 1 to 3 killed
the render's own process group. Here every process in the container dies at once and Docker restarts the container.

Method (new modes of `tools/recovery_drill.py`): the worker was idle (only `worker.py`; next job at 07:12). Inside the worker,
`container-start` made the drill-1 job (8 scenes of 4 s, 1280x720, 32 s narration) in the container's `/tmp` and returned with the render running
after 2 checked scenes. From the host: `kill -9` of the container's pid 1 (`docker-init`, host pid 3991565, user fahad). Then, in the restarted
container, `container-after`.

| | Result |
|---|---|
| Cut | 3.1 s into the render, 2 scenes checked and recorded |
| Docker | restarted the container at once: restart count 1 to 2, started 07:05:27.9, `worker started` 07:05:28, healthy |
| Old render process after the restart | gone ("no such process"); boot id unchanged; the cut run was judged not alive |
| Half-written file | `seg02.part.mp4` (48 bytes), never used |
| Checked scenes after the cut | both still match their recorded size and SHA-256 |
| Recovery scan / doctor | saw the job as interrupted, resume step `python run.py autopilot make doc` / listed `doc-drill-4` |
| Resume | exit 0 in 17.0 s: "scenes: 2 of 8 kept from an earlier run, 6 rendered now" |
| Scenes made again | none (inode and mtime of seg00 and seg01 unchanged) |
| Final video | 32.0 s, video and audio, decodes in full; no `.part` file left |
| Worker after the restart | ran recheck, guardian and health at 07:12-07:13 and Autopilot at 07:15, their normal times: no burst of catch-up jobs |

The throwaway job stays in the worker container's own `/tmp/drill4-20261123` (a few MB, gone when the container is re-created).

## 2. Offline drill: the hourly jobs with no network at all (07:07 UTC)

Method: a reflink copy of `~/studio` (no extra disk used) in `~/studio-drills/netdrill-20261123/app`, plus a second copy `before/` to compare.
Secrets were **not** copied: `.env`, `settings.json`, `token.json`, `client_secret.json` and `data/youtube_login.json` were mounted read-only from
`~/studio`; the login sessions, the password and the cookie secret were left out. A one-off container from the studio image with `--network none`,
the same user, `cap_drop ALL`, 2 GB and 2 CPUs ran seven jobs one after another. Inside it: every outside name failed with "Temporary failure in name
resolution" and 127.0.0.1:31415 (FreeLLMAPI) refused. The copy was never run with the network (it could have acted on real videos).

| Job | Exit | Time | What it did |
|---|---|---|---|
| `health` | 0 | 0 s | "YouTube login: NOT working (TransportError ...)" and posted **"The YouTube login check failed ... Reconnect YouTube"** (finding R10) |
| `doctor` | 0 | 1 s | OpenRouter key `UNKNOWN: the check could not run (ConnectionError)`: right, not "refused" |
| `guardian` | 0 | 1 s | 17 videos with findings, 0 actions (it changed nothing) |
| `recheck` | 0 | 1 s | checked 0; "Could not compare saved titles with YouTube" (routine) |
| `growthdata` | 1 | 0 s | clean error: ServerNotFoundError, no numbers written |
| `autopilot tick` | 0 | 1 s | no actions, no errors (it had nothing to do: scheduling paused, the documentary already made) |
| `report` | 0 | 1 s | today's report already written |

Every changed file was compared with the copy taken before (`diff -r`): only `autopilot_state.json`, the doctor's report, the event feed and the task
list changed. No video record, no model's health (`data/free_models.json`), no topic queue, no money record changed. The doctor's three new setup
items (dashboard, own model provider, Blender) are artefacts of the drill container, which has no dashboard, no FreeLLMAPI and no Blender; on the
host network they answer.

## 3. Restarts

- **Worker, unplanned:** drill 4 above.
- **Dashboard and a planned worker restart:** see section 7 (done after the full suite, to load the new code).
- **PC boot readiness:** Docker `enabled` and `active`; both studio containers `restart: unless-stopped`; user lingering `yes`;
  `freellmapi.service` and `freellmapi-netwatch.service` (user services) `enabled` and running since the boot of 21 Nov 23:12 UTC, the netwatch
  restarting the app after three failed checks and nudging it when the network returns. The open item "FreeLLMAPI does not start after a reboot"
  (21 Nov) is closed. `studio-mydownloads.service` is enabled.
- The worker already waits up to 180 s for the network after a boot (`worker.wait_for_network`, tested since 21 Nov).

## 4. Defects found and fixed

| # | Defect | Found by | Fix | Test / mutation |
|---|---|---|---|---|
| R7 | `data/worker_state.json` (the last start of every job) was written in place. A cut mid-write left half a file, `load_state()` read `{}`, and on restart **every** job ran at once: the weekly learner on the wrong day, a second trend scan (about 1,100 of 10,000 daily API units), the title test. | reading `worker.py` | `checkpoint.write_json` (renamed into place, `.prev` kept) and `checkpoint.read_json` (falls back to `.prev`) | `test_a_cut_while_the_worker_saves_its_job_times_never_makes_every_job_due`; mutation "job times written in place" |
| R8 | `autopilot.json`, `llm.json`, `agent.json` were written in place. A cut mid-save left a file json cannot read: every Autopilot tick and settings page crashed until the file was mended by hand. (A missing file falls back to defaults, which keep Autopilot off; a broken one crashed.) | reading | `checkpoint.write_text_atomic`; the owner's layout (two-space indent, usual order) and permissions (0600) kept | parametrised test for Autopilot and model settings |
| R9 | `token.json` (the YouTube login) was rewritten in place on every refresh: hourly by the health check, and in any process whose access token had run out (5 writers). A cut in that moment left a login Google's library cannot read: no upload or check until the owner reconnects in a browser. Two processes refreshing at once wrote the same file. | reading `ytlogin.py` | one writer, `upload.save_token`: its own temporary file, mode 0600 before the rename, last whole file wins | cut test; permission test; a test fails if any module writes `TOKEN.write_text(`; mutation "login written in place" |
| R10 | A lost network was reported as a lost login: "The YouTube login check failed ... Reconnect YouTube", the Risks row to **act**, and that alert used the day's only alert slot, so a **real** expiry later the same day would have stayed silent. | offline drill | `ytlogin.offline` (no DNS, no route, refused, timed out, or Google's retryable answer): recorded as offline, no alert, slot not used, `last_ok` kept; the Risks row follows the login's age and says the login was not tested; watch after 26 h without a working check; `run.py health` says "not checked, Google could not be reached" | 5 error kinds; "a real expiry is still reported after an outage"; "a long outage turns the row to watch"; mutation "no network taken for a failed login" |
| R11 | A retryable answer from Google's token server (its own trouble) raises `RefreshError`, which both `ytlogin` and `safety` called "The YouTube login expired". | reading | `RefreshError` is "expired" only with `invalid_grant` or when not retryable | covered by `ytlogin.offline` |
| R12 | During an outage, within three days of a publish, `safety.check` posted "Could not reach YouTube to check published videos" as an alert every hour. | reading `safety.py` after the drill | at most once in 24 hours (`safety._told_since`) | `test_an_outage_tells_the_owner_once_a_day_that_youtube_could_not_be_reached` |

`checkpoint.write_text_atomic` is the shared writer: a temporary file with its own name (two writers never share one), created 0600, written and
flushed, given the old file's permissions (or the one asked for), then renamed; `write_json` now uses it too.

Agenteval: `case_a_cut_or_a_lost_network_never_breaks_a_saved_file_or_asks_the_owner_to_reconnect` (first in `CASES`), with three mutation checks
in `tests/test_agents_training.py`. The case silences the desktop notice and Telegram while it runs.

## 5. Tests that ran

- `tests/test_recovery_restart.py`: 13 tests. Before the fixes all 11 then present **failed** (each for the defect it pins); after: 13 passed.
- New and neighbouring suites (recovery, agent training with the new mutation checks, worker, login, safety, risks, render recovery, Autopilot,
  models, research agent, upload guard and hardening, ytweb): **338 passed**.
- Full suite: see section 7.

## 6. Limits (honest)

- `--network none` makes every name fail at once. A network that drops packets (each request waits for its timeout: 120 s for a free model,
  240 s for a paid one) was not simulated: jobs would be slower, and the code treats a timeout as a timeout, not as a bad model.
- Autopilot had nothing to do in the copy, so the model-call path was not exercised under the outage. It is covered by tests: a connection that
  cannot be made skips that model for 60 s and is never counted against it (`test_refused_connections_to_the_owners_provider_never_bench_its_models_for_six_hours`).
- An upload interrupted by a network loss was not drilled (uploads are paused). Existing guards: `upload_started` is written before the send, a retry
  looks for the earlier copy, a per-video lock.
- The code has about 370 other JSON writes in place. The ones fixed here are the files whose half state stops the studio or loses the login. The
  real power cut of 20 Nov found all 839 JSON files whole.
- A job that was running when the worker died runs again after the restart (its start is recorded only when it ends). Every job today can run
  twice safely; a new job must stay that way.
- A network loss **after** `safety.check` has reached YouTube (in the middle of its loop) still ends the health command with one
  "A command failed: run.py health" per hour. Not changed.
- A real power cut during a render on this PC has still not happened; SIGKILL and the container kill are what such a cut does to the processes, not
  to unflushed disk writes (which are caught by the size and SHA-256 checks and made again).

## 7. Restarts after the fixes, full suite, commit

- **Full suite** (host venv, UI browser tests excluded): run 1 stopped at a pre-existing failure, `test_no_tracked_file_holds_a_private_address`:
  `reports/ULTIMATE_MISSION_CHECKPOINT.md` line 14 (committed 22 Nov, so already on the public GitHub repo) held the dashboard's Tailscale address;
  replaced with words. Run 2: 2,955 passed, 1 failed, my own outage test, which depended on test order (`safety.check` calls `reconcile.run`
  first, and in the full suite it reused another test's state); `reconcile.run` is now stubbed in that test. Run 3: **2,956 passed, 0 failed,
  11 skipped** (302 s).
- **Dashboard restart** (07:30:31 UTC, idle, `docker restart`): `/healthz` 200 after 1 s, `/login` 200; `data/sessions.json` byte-for-byte
  unchanged (10 sessions), so the owner stays signed in.
- **Planned worker restart** (07:30:42 UTC, idle, next job 07:36): healthy after 62 s (the health check runs every 60 s); `worker started` at
  07:30:43; the job times were unchanged by the restart; it runs the new `worker.py` (renamed-into-place job times); its first save at 07:36 left `worker_state.json` whole and the old one as `.prev`.
- The Tailscale address is still in the git history of the public repo. It only answers inside the owner's tailnet; rewriting public history
  is the owner's decision.
