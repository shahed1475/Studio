# Kaggle remote GPU worker: inspection, integration and a real T4 run (24 Nov 2026)

Owner's order (24 Nov 2026, ~17:00 UTC): connect the existing Kaggle account as a remote GPU worker for the owner's already-downloaded models, inspect first, stay within Kaggle's terms, do not stop at a design. Times UTC. The Desktop workshop was never read. No credential was printed, stored or uploaded. Nothing committed or pushed; no competition submission made; no video touched.

## Status table
| Stage | Result | Evidence |
|---|---|---|
| A Authentication | **PASS** | `kaggle quota` returned the account's numbers; the `~/.local/bin/kaggle` wrapper reads the token itself (studio Settings > Kaggle API token); `print-access-token` and `config view` never run |
| B Competition access | **PASS** | `kaggle competitions list --group entered`: titanic, house-prices-advanced-regression-techniques, spaceship-titanic (userHasEntered True, ranked) |
| C CSV / data | **PASS** | local copies in ~/kaggle-work/<slug>/data match Kaggle's file list byte for byte; all 9 CSVs read with pandas (rows/columns below) |
| D Notebook create/update | **PASS** | `kaggle kernels push` created private script kernels `shahedalfahad/studio-job-8ba727ef5f45c77c` (and a second, see J) |
| E GPU availability | **PASS** | inside the session: 2 x Tesla T4, 15.64 GB each (torch), driver 580.178.04, 32.87 GB RAM, 4 CPUs, 20.9 GB in /kaggle/working |
| F Input attachment | **PASS (data) / NOT POSSIBLE (model as Kaggle input)** | competition data attached and read in the session: /kaggle/input/competitions/spaceship-titanic/train.csv, 8,693 rows, 14 columns. The exact model file is not hosted on Kaggle Models (`kaggle models list -s "qwen3 4b"`), so it was fetched from its maker inside the session and proven identical (G) |
| G Model loading | **PASS** | the owner's exact file (SHA-256 3605803b..., 2,497,281,120 bytes) loaded by transformers 5.20.2 on the T4 in 101.2 s, float16 dequantised from Q4_K_M, 7,833 MiB on GPU 0, peak 8.12 GB allocated |
| H Real inference | **PASS** | 3 answers, 10.9 to 15.6 tokens/s (below) |
| I Output save/retrieval | **PASS** | `kaggle kernels output` into data/compute/kaggle_outputs/8ba727ef5f45c77c/v1-20261124T171256Z; report.json and results.jsonl match the notebook's manifest (SHA-256 a4a61376..., efdfd045...) |
| J Checkpoint/recovery | see section 7 | |
| K Studio integration tests | **PASS** | tests/test_kaggleworker.py (16), tests/test_compute_routing.py, agenteval case + 3 mutation checks; related suites 228 passed |

## 1. Account and CLI (no credential shown)
- Kaggle CLI 2.2.5 (official `kaggle` package in ~/.local/share/kaggle-cli/venv; commands checked with `-h`, nothing guessed): `kernels push --accelerator NvidiaTeslaT4 -t <s>`, `kernels status`, `kernels logs`, `kernels output -p`, `quota`.
- Quota (`kaggle quota`, 16:59 UTC): GPU 11.74 h used of 30 h, refresh 2026-11-28 00:00 UTC; TPU 0 of 20 h. The two test sessions here used a few minutes.
- Own notebooks before this work: 5 (latest: Avatar lab WanGP H3 InfiniteTalk, 23 Nov).

## 2. Competitions and data (nothing submitted)
| Competition | Files (Kaggle) | Local copy (~/kaggle-work/<slug>/data) | Rules on data use |
|---|---|---|---|
| titanic | train 61,194 B, test 28,629 B, gender_submission 3,258 B | identical sizes; train 891 x 12, test 418 x 11 | "non-commercial purposes only" |
| house-prices-advanced-regression-techniques | train 460,676, test 451,405, sample 31,939, data_description 13,370 | identical; train 1,460 x 81, test 1,459 x 80 | "non-commercial purposes only" |
| spaceship-titanic | train 805,421, test 372,487, sample 59,902 | identical; train 8,693 x 14, test 4,277 x 13 | "any purpose, whether commercial or non-commercial" |
All three: external data must be public and free to all participants; shared code is open-source licensed. Rules read with `kaggle competitions pages list --page-name rules --content <slug>`. Competition work stays in ~/kaggle-work (its own skill: personal, non-commercial; never studio material). The test notebook only attached spaceship-titanic data to prove attachment; it did not model or submit anything.

## 3. Models (summary; full table: reports/DOWNLOADED_MODEL_INVENTORY_2026-11-24.md)
- 118 entries in data/compute/models.json, 411.5 GB. Duplicates proven by SHA-256 (none removed): Qwen3-4B-Instruct-2507 Q4_K_M x2 (~/ai-models/zimage, ~/tools/sdcpp/models), ae.safetensors x3 (+ ~/AI_Video_Studio/ComfyUI), argon-planner Q4_K_M x2 (~/.argon-train/out), and each LoRA run's final adapter equals its last checkpoint (normal). About 4.3 GB of exact duplicates.
- Kaggle fit uses computecompat.need (weights + KV cache at the context + engine overhead), never file size alone; Kaggle numbers now measured: 2 x 15.64 GB T4, 32.87 GB RAM.
- Transfer to Kaggle: only through a **public twin** (the maker's identical file, licence on the production list). Verified today: Qwen3-4B-Instruct-2507-Q4_K_M.gguf = unsloth/Qwen3-4B-Instruct-2507-GGUF (Apache-2.0), Z-Image Turbo Q3_K = leejet/Z-Image-Turbo-GGUF, ae.safetensors = Comfy-Org/Z-Image-Turbo. Not twins: Ollama's qwen2.5:1.5b (986,061,892 B, Ollama's own quantisation) vs Qwen's file (1,117,320,736 B). The owner's fine-tunes (argon, cyberexpert) and every file without a twin are never sent (`private`, `never_send`).

## 4. Terms and use classes (read on Kaggle's own pages today)
- A. Competition computation: allowed under each competition's rules (data limits above).
- B. Personal, non-commercial experiments: allowed ("internal, personal, non-commercial use", Terms 22 Jun 2025) and must be ML data science (AUP). The worker's only permitted task is `benchmark` (measuring an open model with public test prompts).
- C. Commercial YouTube production: **not permitted without Kaggle's written permission**; competition acceptance does not change that. `commercial_use_permitted` stays false; production data never leaves the PC (`kaggle_gate`). Request drafted, NOT sent: reports/KAGGLE_COMMERCIAL_USE_PERMISSION_REQUEST.md.

## 5. What was built (smallest change; existing routing kept)
- `kaggleworker.py` (new): `check` (login via quota, read-only), `verify_twin` (SHA-256 + size + licence vs Hugging Face's published file; data/compute/public_twins.json), `prepare` (private script kernel on NvidiaTeslaT4, internet on for the twin download, competition source optional; refuses an unverified twin, a bad owner name, anything key-like), `submit` (through `computerouter.KaggleAdapter.submit` and its gate; a job already on Kaggle is not pushed twice), `fetch` (a NEW folder per retrieval, never overwritten), `verify` (manifest hashes, model-file proof, `model_loaded` stage, engine consistency, every answer non-empty), `poll` (moves only along computejobs.NEXT; unproven output is FAILED, never COMPLETED), `recover` (INTERRUPTED -> RECOVERY_PENDING -> a package that skips recovered answers; may lengthen the time cap, recorded).
- The notebook (`kaggleworker.TWIN_SCRIPT`): machine report (Python, torch, CUDA, GPUs, RAM, disk, inputs by name and size), twin download outside /kaggle/working + SHA-256 proof (nothing runs on a mismatch), engine 1 transformers GGUF (float16), engine 2 llama-cpp-python CUDA build (fallback), one result line per item with fsync (the checkpoint), report.json written atomically after every stage, manifest.json last.
- `computerouter.py`: the gate admits a private-flagged model only with a verified public twin; `KaggleAdapter.submit` passes `--accelerator` and `-t`.
- `computejobs.job_id` now includes the data class (defect found by a test: a production request with the same inputs was handed an earlier public-test job and its label, which the gate trusts).
- `config/compute.json` (backup .bak-before-kaggle-worker-24nov): kaggle_gpu enabled, owner `shahedalfahad`, `owner_permitted_tasks: ["benchmark"]` with the owner's note, accelerator, 3,600 s cap, evidence updated.
- `run.py compute kaggle-check | kaggle-twin | kaggle-test | kaggle-poll | kaggle-recover`; skill `kaggle-gpu-worker` updated; agenteval case `case_the_kaggle_worker_runs_only_a_verified_twin_for_a_personal_task_and_never_completes_unproven_output` (3 mutation checks).

## 6. The real run (job 8ba727ef5f45c77c, pushed 17:08:58, complete 17:12:30)
- Session timeline (its own report): environment at 20 s, model fetched and proven at 37 s (17.3 s download + hash), loaded by transformers at ~138 s (101.2 s load), three answers by 164 s; total 162.9 s; peak RAM 12.07 GB.
- Answers (personal test prompts, not channel material):
  - q1, 43 tokens, 3.94 s (10.9 tok/s): "The sky looks blue because molecules in the atmosphere scatter blue light more than other colors due to its shorter wavelength. ..."
  - q2, 11 tokens, 0.73 s (15.1 tok/s): "53, 59, 61" (correct)
  - q3, 18 tokens, 1.16 s (15.6 tok/s): French "Bon jour" (should be "Bonjour"), Spanish "Buenos días": a real answer with a small model error, reported as it came.
- Defect found by this run and fixed: the notebook's `stage(name, **kw)` collided with the engine's own `name` key right after the load succeeded, so the report said `load_failed` for transformers while its answers came from that loaded model (results record `engine: transformers-gguf`), and the llama.cpp fallback was tried needlessly (its source build failed in the session). Fixed (`stage(_stage, ...)`, only the loader call can fail a load), `verify` now requires a `model_loaded` stage and matching engines; test + mutation check. The job's COMPLETED state stands on the retrieved, hash-verified files; its stage log carries the defect and is described here.
- Engine notes: transformers 5.20.2 reads the GGUF and dequantises to float16 (8.12 GB on one T4), so the second T4 stayed idle; llama-cpp-python's source build failed in the session (a native CUDA run of the Q4 file would need a working build: future work).

## 7. J: checkpoint and recovery
- Fakes (tests/test_kaggleworker.py, all passing): an expired session (CANCEL_ACKNOWLEDGED) with one finished answer and no manifest becomes INTERRUPTED with that answer kept; `recover` writes a new package whose notebook skips it and pushes it; the first retrieval folder is kept; a tampered output is FAILED, never COMPLETED; a resumed notebook (run here with stand-ins) writes only the missing answer; a session waiting for a GPU stays PREPARING (QUEUED is no longer read as RUNNING).
- Real test on Kaggle: job 136f1b32068c72a8 (5 public prompts, deliberately capped at 150 s so Kaggle ends it mid-run), pushed 17:14:03 UTC, **QUEUED by Kaggle (no GPU assigned) for 26+ minutes** at 17:40 UTC, while the first job got a GPU within a minute. Result below when it runs.

## 8. Commands
```
python run.py compute kaggle-check                       # login (never shown), quota, competitions, notebooks
python run.py compute kaggle-twin <file> <hf repo> <file name>   # prove a public twin (SHA-256 + size + licence)
python run.py compute kaggle-test [twin sha] [competition]       # push the benchmark of a verified twin to a T4 (personal, non-commercial)
python run.py compute kaggle-poll <job>                  # status; when done: retrieve into a new folder, verify, COMPLETED/FAILED/INTERRUPTED
python run.py compute kaggle-recover <job>               # an INTERRUPTED job resumes, skipping recovered answers
```
Power cut during a session: the session keeps running on Kaggle; after restart run `kaggle-poll <job>` (job files in data/compute/jobs/, outputs in data/compute/kaggle_outputs/).

## 9. Tests and files (17:56 UTC)
- Full suite: **3,106 passed, 11 skipped, 0 failed** (298.65 s). New: tests/test_kaggleworker.py (18 tests: twins, gate, package, push arguments and idempotence, the notebook run here end to end with stand-ins, hash mismatch, resume, retrieval, tamper, expiry, QUEUED, the data-class job id, the stage defect); agenteval case with 3 mutation checks; one manual mutation check (old stage() signature -> test fails).
- Files changed: kaggleworker.py (new), computerouter.py (gate, push arguments, QUEUED), computejobs.py (job id), run.py (compute kaggle-*), agenteval.py, tests/test_kaggleworker.py (new), tests/test_agents_training.py, .claude/skills/kaggle-gpu-worker/SKILL.md, config/compute.json (+ backup), data/compute/public_twins.json, data/compute/inputs/kaggle_benchmark_v1.json and v2.json, this report, YOUTUBE-AUTOMATION-MASTER-REPORT.md (appended).
- Real expiry test (job 136f1b32068c72a8): still QUEUED by Kaggle at 18:20 UTC (66 min; watcher ended). NOT TESTED on hardware yet. Next: `python run.py compute kaggle-poll 136f1b32068c72a8` once it has run (expected INTERRUPTED at its 150 s cap, with whatever answers Kaggle kept), then `python run.py compute kaggle-recover 136f1b32068c72a8` (3,600 s cap, recovered answers skipped).

## 10. Remaining blockers and owner decisions
1. Commercial use on Kaggle: send the drafted request (or not); until a written yes, production stays BLOCKED.
2. llama.cpp natively on Kaggle (Q4 file, both T4s): the llama-cpp-python source build failed in the session; a pinned prebuilt CUDA build or a compiled llama.cpp is future work.
3. Kaggle Models: the exact twin is not hosted there; a private Kaggle Dataset upload of an Apache-2.0 twin would avoid the download but is an upload (owner's choice).
4. Duplicates (~4.3 GB, listed in section 3): keep or remove is the owner's decision; nothing was deleted.
5. Commit and push of all this work: waits for the owner.

## 11. Queue investigation (19:04 UTC, read-only; nothing pushed, cancelled or deleted)
- Kaggle status of studio-job-136f1b32068c72a8: `KernelWorkerStatus.QUEUED` at 19:04 UTC, 1 h 50 min after the push (17:14:06, `kernels list` lastRunTime). The CLI prints Kaggle's `failure_message` whenever there is one (kaggle_api_extended.kernels_status_cli): none. `kaggle kernels logs`: empty, so no code has started.
- Quota: GPU 11.79 h used (11.74 h before the two pushes): the +0.05 h is job 8ba727ef's real run; the queued job uses nothing.
- Local record: PREPARING since 17:14:06, attempts 1, no second push. In this studio PREPARING means "pushed, Kaggle has not started it"; the job moves only when a poll sees RUNNING, COMPLETE or an error. No poller is running (`kaggle-poll` is one-shot; the background watchers ended at 18:20).
- Normal or stuck: not decidable from outside. Job 8ba727ef got a T4 within a minute 5 minutes earlier; Kaggle gives no queue position or reason. Unverified possibilities: T4 capacity at that hour, or the unusually short 150 s cap. Kaggle documents no maximum queue time.
- A supported stop exists in the SDK, not in the CLI: `kagglesdk` `kernels_api_client.cancel_kernel_session(ApiCancelKernelSessionRequest(kernel_session_id=<int>))` cancels a run without deleting the notebook. It needs the session's numeric id (not shown by `kernels status`). NOT called: waiting for the owner.
- Recommendation: either leave it queued (no cost; if it starts, the 150 s cap ends it and `kaggle-poll` then `kaggle-recover` finish test J), or, with the owner's yes, cancel that one session through the SDK call above. No duplicate test job is pushed either way.
- Worker status stated precisely: one real GPU execution with model inference has succeeded and was verified (job 8ba727ef5f45c77c); the expiry/recovery path (J) is NOT TESTED on hardware.

## 12. Test J left queued, watched gently (owner's order 24 Nov, ~19:10 UTC)
- Job 136f1b32068c72a8 still `KernelWorkerStatus.QUEUED` at 19:12 and 19:21 UTC (no failure message, empty logs). Not cancelled, not deleted, no duplicate pushed.
- Watcher: user service `kaggle-j-watch2` running data/compute/kaggle_j_watch.sh (log data/compute/kaggle_j_watch.log): one status call every 10 min; when the session ends it runs `kaggle-poll` (retrieval + manifest, model-fingerprint and stage checks), `kaggle-recover` once if INTERRUPTED, then polls the recovery to its end; stops at 03:30 UTC 25 Nov and cancels nothing. Its first start (19:21:00) had no `kaggle` on PATH: one poll failed with FileNotFoundError and changed nothing (job still PREPARING); fixed and restarted at 19:21:10, and an unreadable status is now waited on, never treated as an end.
- If it is still queued when the Seven Sleepers render has finished: report the delay and ask the owner before any cancel (the SDK's cancel_kernel_session, never delete).
- Full recovery support is NOT claimed until this test passes on Kaggle hardware.

## 13. Test J ran on Kaggle hardware (read 25 Nov 2026 00:05 UTC)
- Job 136f1b32068c72a8 left the queue between 19:21 and 19:31 UTC. Capped session (150 s): environment 22 s, model fetched and proven 36 s (SHA-256 3605803b..., matches the owner's file), loaded 146.7 s, 5 answers 151.1-153.5 s, report finished True; Kaggle then reported `KernelWorkerStatus.CANCEL_ACKNOWLEDGED` (the cap fell during Kaggle's own after-run conversion). Retrieved 19:31:17 into v1-20261124T193117Z; report.json and results.jsonl match the manifest (5675a503..., 78cc736f...).
- Watcher actions: poll -> INTERRUPTED with 5 answers kept; `recover` -> new package (cap 3,600 s) with all 5 ids marked done, pushed 19:31:24; queued again; ran ~20:11; loaded the model (104 s) and skipped all 5 (no answer repeated); retrieved 20:13:36 into v2 (empty results.jsonl, manifest-verified); job COMPLETED, checkpoint holds q1-q5.
- Answers (personal test prompts): q1 sky (43 tokens), q2 "53, 59, 61", q3 "Bon jour" / "Buenos días", q4 "Jupiter", q5 "401" for 17 x 23 (wrong: 391). Reported as returned.
- What passed on hardware: expiry detected (CANCEL_ACKNOWLEDGED -> INTERRUPTED), outputs of an expired session retrieved and hash-verified, the model fingerprint re-proven in both sessions, resume without repeating finished items, job state consistent with the task (5 of 5 ids).
- What was NOT exercised: a cut in the middle of an item (the cap fell after the last answer); fetching partial output of a session killed mid-item.
- Defect found and fixed (tests added): a session that had finished and signed every answer before Kaggle's cancel was treated as interrupted, and recovery pushed a session that spent ~2.6 GPU minutes skipping everything. Now such a session is COMPLETED ("Kaggle ended the session at its time cap after the notebook had finished") and `recover` refuses to push when no item is left. GPU used by both test sessions: ~5 min (quota 11.79 h -> 11.88 h).
- Conclusion: recovery support is demonstrated for "session ended after its work" and "resume skips finished items"; a mid-item cut remains untested on hardware.
