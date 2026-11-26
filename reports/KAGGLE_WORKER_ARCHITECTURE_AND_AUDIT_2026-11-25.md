# Kaggle GPU worker: audit and architecture (25 Nov 2026)

**Scope.** Read-only audit, Category A. No Kaggle job was submitted or cancelled, no file was uploaded, nothing was downloaded to Kaggle, and no Neurons or paid services were used. No production setting or code was changed for this report.

**Environment of this audit.**
- **Commands:** run from `/home/fahad/studio` with `/home/fahad/studio/.venv/bin/python` (sys.prefix `~/studio/.venv`), `VIRTUAL_ENV`, `PYTHONSTARTUP` and `OLDPWD` cleared, and PATH limited to `~/studio/.venv/bin`, `~/.local/bin` and system folders.
- **Docker:** `--context default` → `unix:///var/run/docker.sock`; `studio-worker` mounts `~/studio` as `/app`.
- **Check:** `bash tools/claude-studio.sh --check` passed.
- **Kaggle CLI:** version 2.2.5, in its own environment at `~/.local/share/kaggle-cli/venv`. The `~/.local/bin/kaggle` wrapper reads the token from studio settings and never prints it.

Labels used below: **VERIFIED** (read in records or files today), **CLAIM** (stated by the owner's brief or an earlier report), **INFERENCE**, **RECOMMENDATION**, **UNVERIFIED**, **BLOCKED**, **NEEDS APPROVAL**.

## 1. What actually exists (VERIFIED)
| Part | File | State |
|---|---|---|
| Job store and state machine | `computejobs.py` (143 lines) | States QUEUED, PREPARING, MODEL_LOADING, RUNNING, CHECKPOINTED, COMPLETED, FAILED, INTERRUPTED, BLOCKED, BLOCKED_PENDING_TERMS_REVIEW, RECOVERY_PENDING. Only the moves in `NEXT` are allowed. Each job file is written atomically to `data/compute/jobs/<id>.json`. The id is a hash of model, task, input, params, environment and data class (idempotent). A payload that looks like a secret is refused (`SECRET`). |
| Gate, router, adapter | `computerouter.py` (340) | `kaggle_gate`: only `public-test` data; a private model only through a verified public twin; the task must be listed in `owner_permitted_tasks` (today only `benchmark`); worker switched on. `KaggleAdapter.status` maps CLI text to QUEUED, RUNNING, COMPLETED, INTERRUPTED or UNKNOWN. |
| Kaggle worker | `kaggleworker.py` (444) | `verify_twin` (Hugging Face API, same SHA-256 and size, licence on the production list), `prepare` (private **script** kernel with only `kernel-metadata.json` and `run.py`, secret scan, `is_private: true`), `submit` (`--accelerator NvidiaTeslaT4`, `-t session_cap_s`, never pushes a job already on Kaggle, `MAX_ATTEMPTS`), `fetch` (into a NEW folder each time), `verify` (manifest SHA-256, model-hash proof, engine consistency, notebook finished, no empty answers, no missing items), `poll`, `recover` (skips recovered items; refuses when nothing is left), `check` (CLI version, quota, competitions; prints no credential). |
| Notebook | `kaggleworker.TWIN_SCRIPT` | Writes the environment report; downloads the PUBLIC twin to `/tmp/model` (never into saved output); proves its SHA-256; loads with transformers-gguf (fp16), falling back to llama-cpp-python; appends `results.jsonl` with an fsync per item; writes `report.json` atomically; writes `manifest.json` last. |
| Commands | `run.py compute kaggle-check | kaggle-twin | kaggle-test | kaggle-poll | kaggle-recover` | |
| Config | `config/compute.json` `kaggle_gpu` | enabled true; owner_permitted_tasks ["benchmark"]; commercial_use_permitted **false**; accelerator NvidiaTeslaT4; session_cap_s 3600; test_competition `spaceship-titanic`; never_scan includes the forbidden folder. |
| Tests | `tests/test_kaggleworker.py`, `tests/test_compute_routing.py` | **58 passed** today (17 + 32 test functions; fakes only). |

## 2. Real GPU evidence (VERIFIED from the job records, notebook reports and the live account, 25 Nov)

**Job `8ba727ef5f45c77c`** (kernel `shahedalfahad/studio-job-8ba727ef5f45c77c`, status today `KernelWorkerStatus.COMPLETE`):
- **Request:** task `benchmark`, data class `public-test`, input `data/compute/inputs/kaggle_benchmark_v1.json` (3 public test prompts).
- **Accelerator:** asked for NvidiaTeslaT4; got **2 x Tesla T4, 15.64 GB each**. Driver 580.178.04, 32.87 GB RAM, 4 CPUs, torch 2.11.0+cu130, `cuda_available: true`.
- **Model:** public twin `unsloth/Qwen3-4B-Instruct-2507-GGUF/Qwen3-4B-Instruct-2507-Q4_K_M.gguf`. SHA-256 `3605803b…` matches the owner's file (`matches_owner_file: true`).
- **Engine:** transformers-gguf, **dequantised to float16**, on GPU 0 only (7,833 MiB after load on GPU 0, 3 MiB on GPU 1). The second T4 was idle, and nothing was offloaded to the CPU (`device: Tesla T4`).
- **Stage times (seconds from session start):**
  - environment 19.2;
  - model downloaded and hashed 36.5 (2.5 GB in about 14 s);
  - model loaded (load_s 101.2);
  - answers at 161.0–162.9.
- **Speed:** 3 answers of 43, 11 and 18 new tokens at **10.9, 15.1 and 15.6 tokens/s**. Peak GPU memory allocated 8.12 GB.
- **Wall time:** pushed 17:09:01 UTC, retrieved and verified 17:13:00, under 4 minutes end to end.
- **Recorded defect:** the stage log showed `load_failed` for both loaders even though the model loaded. That was a logging bug (fixed 24 Nov with a test). The llama-cpp-python CUDA wheel **failed to build** on Kaggle.
- **Not measured:** prompt tokens, time to first token, GPU utilisation during inference (only memory was sampled), and an absolute session start time.

**Job `136f1b32068c72a8`** (expiry test, 150 s cap; status today COMPLETE):
- **Correction to the CLAIM in the brief.** The brief said it was stuck QUEUED with no logs or GPU time; that was true on 24 Nov at 18:00, not later. It waited about **2 h 17 min** in Kaggle's queue, then ran:
  - environment 22.2 s, model fetched 35.9 s, loaded 146.7 s (load_s 110.8);
  - **5 answers at 151.1–153.5 s** (9.7–15.2 tok/s).
- **Cap and retrieval:** Kaggle then reported CANCEL_ACKNOWLEDGED at its time cap. The outputs were retrieved (`v1-20261124T193117Z`) and verified.
- **Unneeded recovery session:** the code of that time treated the session as interrupted and pushed a recovery session (`v2`). It queued about 37 minutes (push 19:31:24, Kaggle `lastRunTime` 20:08:09), loaded the model, ran 0 items and was COMPLETED, costing about 2.6 GPU minutes.
- **Fix:** the 24–25 Nov fix (a session cancelled at its cap after finishing counts as COMPLETED; `recover` refuses when nothing is left) has tests.
- **Recovery after a cut in the middle of an item: never tested on hardware.**

**Live account (read today):**
- `kaggle quota`: GPU **11.88 h used of 30.00 h, 18.12 h left**, refresh 2026-11-28 00:00 UTC; TPU 0 of 20 h.
- `kernels list --mine`: the two studio kernels, plus five of the owner's own earlier notebooks (two from 22–23 Nov). For those five, `kernels status` returns 404 (they are probably interactive notebooks, which the CLI cannot read).
- Because GPU use has not changed since 24 Nov evening (11.88 h then and now), **no GPU session has run since then: nothing is running, nothing is orphaned** (INFERENCE from the quota figure). No session was cancelled.

## 3. Tested, untested, failed
| Claim | Status |
|---|---|
| Private package, no credential, T4 requested, time cap | VERIFIED in tests and in 3 real sessions |
| Public twin downloaded and proven by SHA-256 inside Kaggle | VERIFIED (3 sessions) |
| Real GPU inference | VERIFIED (8 answers over 2 sessions, 9.7–15.6 tok/s) |
| Retrieval into new folders, manifest check, COMPLETED only when verified | VERIFIED (real) |
| Session cut at the cap after finishing → COMPLETED | VERIFIED (fix tested with fakes; the real case was seen) |
| Cut in the middle of an item, resumed without repeating items | UNVERIFIED on hardware (fakes only) |
| Studio restart while a job runs on Kaggle | UNVERIFIED on hardware. By design the job file is durable and `poll` is idempotent |
| Queue timeout, quota-aware scheduling, concurrency limit | NOT BUILT |
| llama.cpp CUDA engine on Kaggle | FAILED (wheel build) |
| Using both T4s | NOT DONE (single-device load) |
| GPU utilisation, time to first token, prompt tokens, absolute queue and run times | NOT MEASURED |
| Local baseline for the same model | NOT MEASURED |

## 4. Policy blockers (detail: KAGGLE_POLICY_AND_WORKLOAD_ELIGIBILITY_2026-11-25.md)
- **Production:** Kaggle Terms (Version June 22, 2025, active, read today): "your own internal, personal, non-commercial use". Channel production stays **BLOCKED** until Kaggle's written permission. The draft request (`reports/KAGGLE_COMMERCIAL_USE_PERMISSION_REQUEST.md`) is not sent.
- **Competition data:** the worker attaches the `spaceship-titanic` competition to benchmark kernels and reads only its CSV header. That competition's rules page contradicts itself: the summary says "Competition Use and Academic, Non-Commercial Use Only", while section A says "any purpose, whether commercial or non-commercial". The 24 Nov report quoted only section A. **RECOMMENDATION:** stop attaching competition data to non-competition jobs (least privilege; Category B change).

## 5. Target architecture (RECOMMENDATION; build only after approval, Category B)
```
Studio task queue (computejobs)            durable job file, idempotent id
  -> policy gate (computerouter.kaggle_gate)  data class, task allowlist, licence, twin proof, commercial flag
  -> model + input resolver                 inventory entry -> public twin (Hugging Face OR Ollama registry, by SHA-256); inputs = small public JSON only
  -> quota + queue planner (NEW)            live `kaggle quota`; budget per job; max 1 GPU job at a time; refuse when remaining - reserve < estimate (BLOCKED_QUOTA)
  -> package (kaggleworker.prepare)         private script kernel; only kernel-metadata.json + run.py; secret scan; no competition source unless a competition job
  -> push (-t cap, --accelerator)           SUBMITTED; Kaggle QUEUED until lastRunTime moves
  -> notebook: verify GPU -> fetch twin -> prove hash -> load -> run items -> per-item fsync -> report -> manifest last
  -> retrieval (`kernels output` into a new folder) -> integrity (manifest SHA-256) -> semantic checks -> durable record
```
**State mapping.** The brief's 17 states → the studio's existing 11, plus the additions proposed:

| Brief | Existing | Proposal |
|---|---|---|
| CREATED / VALIDATING | QUEUED (gate on submit) | keep; record the gate verdict in history |
| PREPARING / SUBMITTED | PREPARING (= pushed) | add SUBMITTED (pushed, waiting for Kaggle) and record `queued_at` / `started_at` from `kernels list` `lastRunTime` |
| QUEUED (remote) | PREPARING + adapter status QUEUED | separate state REMOTE_QUEUED with a queue-timeout policy: notify after 60 min; never auto-cancel |
| RUNNING / CHECKPOINTING | MODEL_LOADING / RUNNING / CHECKPOINTED | keep |
| COMPLETED_UNVERIFIED / VALIDATING_OUTPUT | inside `poll` (fetch + verify in one step) | keep as one step, but record `retrieved_at` and the verification result |
| SUCCEEDED | COMPLETED (only after verification) | keep the name |
| FAILED | FAILED | keep |
| EXPIRED | INTERRUPTED | keep; add the reason `expired_at_cap` |
| CANCEL_REQUESTED / CANCELLED | none | the CLI has no cancel command (docs/kernels.md); the SDK `cancel_kernel_session` exists but is unused. Owner-only, NEEDS APPROVAL per job |
| RECOVERY_REQUIRED | RECOVERY_PENDING | keep |
| BLOCKED_POLICY | BLOCKED / BLOCKED_PENDING_TERMS_REVIEW | keep |
| BLOCKED_QUOTA | none | ADD (live quota check before push) |

**Job manifest fields to add** (none secret):
- requested vs actual accelerator (actual is recorded today);
- **input file SHA-256** (today `inputs: []` in the report);
- `pushed_at`, `remote_started_at`, `finished_at` (absolute UTC);
- GPU utilisation samples (nvidia-smi every 2 s in a thread);
- prompt tokens and time to first token per item;
- engine and versions (recorded today);
- GPU-hours consumed (from the `kaggle quota` difference);
- retry count (`attempts` exists);
- validation result (history exists).

**Storage.** Kaggle's saved output (docs: "Up to 20 GBs of output … in /kaggle/working") retrieved only with the authenticated CLI. No external storage, and no key of any kind inside a notebook. A job whose output would exceed about 5 GB is refused at planning time (benchmarks write KB).

**Routing policy** (`computerouter.route` exists; additions):

| Case | Route |
|---|---|
| Task not eligible for Kaggle (any production / private data) | local, or BLOCKED |
| Model fits this PC's 4 GB GPU fully (≤ ~3 GB Q4) and a short job | local (no queue, no 2–3 min start, no 100 s load) |
| Model needs > 4 GB VRAM and the job is a benchmark-class batch ≥ ~15 min of GPU work | Kaggle (if quota, twin, licence) |
| Interactive or latency-sensitive | local (Kaggle queue observed at 0–137 min) |
| Image or video model for channel pictures | local or the free Cloudflare route (Kaggle BLOCKED: commercial) |

## 6. What would make it reliable (all NEEDS APPROVAL, Category B; no quota used)
1. Live quota planner, BLOCKED_QUOTA, and one GPU job at a time.
2. Absolute timestamps, GPU utilisation sampling, prompt tokens and time to first token in the notebook.
3. Remove competition attachment from benchmark jobs.
4. Ollama-registry twin (blob by SHA-256) next to the Hugging Face twin.
5. An engine that uses the T4 properly: a prebuilt llama.cpp CUDA wheel or binary (UNVERIFIED on Kaggle), or vLLM/transformers fp16 with tensor-parallel across both T4s (UNVERIFIED). Measured, not assumed (benchmark plan).
6. Recovery test with a planned mid-item cut (a tiny `-t` on a long item list). That uses about 3–5 GPU minutes, so it is Category C.
7. Studio-restart test (mock).

Not production-ready: success criteria 4 (measured performance vs local), 8 (mid-item recovery) and 10 (quota-aware scheduling) are not met. Criteria 1–3, 5–7, 9, 11 and 12 are met for the `benchmark` task only.
