# Kaggle worker: implementation proposal (25 Nov 2026), NOT IMPLEMENTED; each step needs the owner's yes

Method:
- **superpowers `writing-plans`:** small steps, each with its own test and rollback.
- **`systematic-debugging`:** root cause first; the idle GPU and the build failure both have one.
- **`verification-before-completion`:** only what ran is claimed.
- **`grilling`:** applied to the plan itself in section 4.

Production code and settings are unchanged: the SHA-256 of `kaggleworker.py` (`44daceaa…`) and `config/compute.json` (`bf6ff894…`) was checked after the work.

## 1. Step K1a: exact diff, ready (`reports/KAGGLE_WORKER_PROPOSED_DIFF_2026-11-25.patch`)
**What it changes:**

| File | Now | Proposed | Why |
|---|---|---|---|
| `config/compute.json` | `test_competition: "spaceship-titanic"` | `""` | stop attaching competition data to benchmarks (unclear terms; not needed) |
| `config/compute.json` | `session_hours: 12` | `9` | the stricter official figure (GPU tips) |
| `config/compute.json` | — | `quota_safety_margin_h: 2.0`, `queue_timeout_s: 3600` | preflight settings |
| `kaggleworker.py` | no quota gate | `quota_preflight(job, env_cfg, run)`: live `kaggle quota`; one studio Kaggle job at a time; cap ≤ session limit; remaining ≥ cap + margin; unknown = no | quota awareness; blocks the duplicate-commit case |
| notebook template | relative times only | `started_at_utc` in `report.json` | queue wait = start − push |

**Verified, without applying it:**
- `patch -p1 --dry-run` succeeds against the real files.
- Applied to a scratch copy, the module compiles and the JSON parses.
- Called with fake CLI output, `quota_preflight` gave the expected answer in five cases: unreadable quota → no; 18.12 h → yes; 2.50 h → no; a 10 h cap → no; another job queued → no.

**Not yet done in K1a:**
- `submit` does not call the preflight yet: wiring it in and the `BLOCKED_QUOTA` status are step K1b.
- The real JSON field names of `kaggle quota --format json` are taken from the CLI source's field list (`resource, used, remaining, total, refreshAt`). Confirming them needs one real account query, which needs approval.
- The full test suite has not been run against it.

**Self-review** (the independent reviewer agent could not be dispatched; see the hook review report):
- **One nit to fix in K1b:** the busy check reads `computejobs.all_jobs(200)`. An unfinished Kaggle job older than the 200 newest jobs would be missed, so it should scan every job that has a `kaggle_ref`.
- No case was found where the gate wrongly allows a push: every parse error returns "no".

- **Security impact:** less data sent (no competition attachment); no new network path.
- **Compatibility:**
  - `kaggle-test` without a competition argument attaches nothing;
  - 136f-style runs are unchanged;
  - an explicit competition argument still works for a genuine competition job.
- **Rollback:** `patch -p1 -R`.
- **Quota / production:** none.

## 2. Further steps (designs; code written only after approval)
| # | Change | Files | Tests (fakes, no quota) | Quota | Changes production behaviour? |
|---|---|---|---|---|---|
| K1b | `submit` calls `quota_preflight`; new status `BLOCKED_QUOTA` in `STATUSES`, `FINAL` excluded, `NEXT` edges (QUEUED→, RECOVERY_PENDING→, →QUEUED); ledger `data/compute/kaggle_ledger.json` (atomic) | kaggleworker.py, computejobs.py, computerouter.py (status map), dashboard view if it lists statuses | unknown quota blocks; low quota blocks; second push refused; ledger written atomically; mutation check: removing the gate fails a test; existing 58 Kaggle and routing tests stay green | 0 | Kaggle path only (benchmark task) |
| K1c | Queue tracking: `remote.pushed_at`, first-seen RUNNING, `queue_timed_out` notice after `queue_timeout_s` (never cancels) | kaggleworker.py | timeout sets the flag and posts a notice; never calls cancel | 0 | no |
| K1d | Notebook telemetry: nvidia-smi sampler thread every 2 s (`-i 0,1`: util, mem, power, clocks, throttle) → `gpu_samples` in the report; per-device peak; time to first token; prompt tokens; peak RAM per stage | kaggleworker.py (TWIN_SCRIPT) | echo engine run writes samples; parser reads two devices; "both GPUs used" needs > 1 GB on each | 0 | no |
| K1e | Output hardening: allowlist of retrieved names, 50 MB cap, per-row `row_sha256`, `checkpoint.json` after each item (atomic), JSON schema per row, semantic known-answer check | kaggleworker.py | traversal-style and unknown file → FAILED; oversize → FAILED; tampered row rejected; truncated last line kept out; missing manifest + valid checkpoint → INTERRUPTED with verified rows only | 0 | no |
| K1f | Build log capture: any pip/cmake step runs with full output to `build.log` in outputs (size-capped) | kaggleworker.py | echo harness | 0 | no |
| K2 | llama.cpp engine from the pinned prebuilt binary (b12719, CUDA 12.8 + cudart, SHA-256 pinned), `llama-server` on 127.0.0.1, `placement` = single, split-layer or parallel-2 | kaggleworker.py | command lines built correctly; hash mismatch → nothing runs; server bound to 127.0.0.1; stopped in `finish` | 0 to write | no |
| K3 | Ollama-registry twin: `verify_twin_ollama(name)` reads the local layer digest (`/api/show`), the registry manifest, sizes; one local SHA-256 re-hash of the blob; licence from the licence layer; notebook downloads `registry.ollama.ai/v2/library/<repo>/blobs/sha256:<digest>` and hashes before use | kaggleworker.py, data/compute/public_twins.json | manifest mismatch refused; tag moved → pinned digest still used; vision arch `qwen25vl` refused for llama.cpp | 0 (local re-hash: 5.2 GB disk read) | no |
| K4 | Local benchmark harness `run.py compute bench-local` (llama.cpp binary or Ollama; preconditions from the benchmark plan; result JSON in `data/compute/bench/`) | new `computebench.py`, run.py | refuses when a render, voice job or Kaggle job is active; records offload | 0 | no |
| K5 | Skill card corrections (`model-resource-monitor`: quota is readable; `kaggle-gpu-worker`: 9 h, no competition) | .claude/skills/… | `extend.py verify` | 0 | no |

## 3. Approvals are separate (see the final message)
Code (K1a–K5, one by one); local engine download (about 815 MB); local benchmark; Kaggle Test A; Test B; multi-GPU; Test C; recovery Test E; plugin change; documentary changes.

## 4. Grill of this plan (questions answered from evidence; open ones go to the owner)
1. **Does the preflight itself use quota?**
   - No: a quota read is an API call.
   - It is an **account query**, and running it live needs the owner's yes once.
2. **Could blocking on "another job not finished" freeze forever?**
   - Yes, if an old job stays PREPARING.
   - K1c's poll moves it on. A stuck job becomes visible on the Compute page, and the owner can mark it FAILED.
3. **Is the 12.8 binary truly OK for a T4 on driver 580?**
   - By NVIDIA's rules, yes: the driver is newer than the 12.8 PTX.
   - JIT time is unknown, so Test B has a 10-minute stop.
4. **Is a localhost `llama-server` inside a notebook a "server" Kaggle forbids?**
   - It listens on 127.0.0.1 only, lives only during the job, and is not reachable from outside.
   - The Acceptable Use Policy's concern is "server farming" (INFERENCE). It is marked for the owner's awareness.
5. **Does Test E risk outputs?**
   - Only that test's own outputs. The planned cap is set by `-t`, never a manual kill.
6. **Open, owner's call:**
   - whether "benchmark" stays classed as personal use, or Kaggle is asked first (the draft request exists, not sent);
   - whether the image benchmark is a permitted task.
