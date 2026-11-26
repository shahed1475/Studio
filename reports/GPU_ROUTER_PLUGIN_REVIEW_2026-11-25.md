# GPU-router plugin: full review, NOT installed (25 Nov 2026)

**Scope (owner's order of 25 Nov):** review only. Branch `feature/gpu-router-plugin` at `7fa9023`, worktree `/home/fahad/studio-worktrees/gpu-router-plugin` (checked: outside the forbidden folder). Code: `plugins/gpu-router/`, about 900 lines of Python and 231 lines of tests.

**Not done, by order:** the plugin was NOT installed, registered, copied into the studio, integrated, merged, pushed or deployed. No pull request was opened, and no model routing was changed. The branch and its earlier review file `plugins/gpu-router/REVIEW_2026-11-25.md` are unchanged; `git status` is clean. This report lives only in the studio's `reports/` folder.

**Conflict of interest:** the 0.1.1 fixes on this branch were written by Claude in the previous session. This review is by the same model, so a second reviewer (the owner, or another model family) should read the critical findings before any decision.

## Evidence
- **Tests:** 27 of 27 passed today (`pytest tests`, ledger pointed at a temporary file; no network; no `~/.gpu_router` written).
- **Coverage:** NOT MEASURED, because `coverage` is not installed in the studio environment and nothing was installed for this review.
- **Security scan:** `vetskill.py` found 0 high findings. The medium findings are all expected: it calls the `kaggle` and `modal` command-line tools, reads R2 keys from the environment, writes its ledger under the home folder, and builds an R2 web address from the account id.
- **Code reading:** every source file was read in full: config, router, ledger, CLI, Kaggle backend, Modal backend, R2 storage, notebook helper and the manifests.
- **Not run:** no live Kaggle, Modal or R2 call. Provider compatibility rests on recorded real Kaggle CLI 2.2.5 output (status strings and the quota JSON) only.

## 1. Architecture: WARNING
- **What it is:** routing is by job *shape* (short or long, GPU or TPU, interactive) and *quota* only.
- **Missing compute routing:** no local GPU, VPS or paid-API route.
- **Missing model routing:** model selection (capability, context, licence) is absent, so "model selection" and "compute selection" are not separated: model selection does not exist.
- **Provider abstraction:** thin. Each backend is a set of module functions with no common interface, and the CLI submits to Kaggle only ("modal submission isn't wired").
- **Dependencies:** small (`kaggle`; optional `boto3`, `modal`).
- **Configuration:** environment variables only. No validation, so a non-numeric value crashes at import (`float(os.environ.get(...))`).
- **Fit with the studio:** it duplicates what the studio already has (`computerouter.py`, `computejobs.py`, `kaggleworker.py`, the model registry `modelcfg.py`/`config/models.json`). It shares none of the studio's gates.

## 2. Security: FAIL for studio use (WARNING as a stand-alone tool)

**Critical findings:**
- **S1 – the whole job folder is uploaded.** `kaggle_backend.push` sends everything in it to Kaggle. There is no file allowlist, no secret scan, and no check that `kernel-metadata.json` keeps `is_private: true`; `check_metadata` warns about accelerators and internet, never about privacy. A misplaced `.env` or a public flag would publish it. The studio's worker builds a clean package and refuses credentials.
- **S2 – R2 keys would go into Kaggle.** The notebook helper's design ("push every finished artifact off-box", R2) needs R2 write keys inside the Kaggle session. That breaks the studio rule "never upload credentials to Kaggle".
- **S3 – the commercial gate is a bare string.** Any non-empty `KAGGLE_COMMERCIAL_PERMISSION_REF` opens Kaggle to *every* commercial job. Nothing is verified, and nothing is recorded per job.

**Other findings:**
- **Modal:** `modal run <entrypoint>` executes whatever the caller names. No shell is involved (argv list), so there is no injection, but there is no allowlist either.
- **Errors:** they include CLI stderr verbatim (no redaction step). The Kaggle CLI did not print the token in the studio's tests, but nothing guarantees it.
- **Tenants:** no tenant isolation. One ledger in the home folder, and no `STUDIO_MODE` check.
- **SSRF:** no web requests other than the R2 endpoint built from the account id, so there is no SSRF surface.
- **Path handling:** paths come from the caller and are not validated (`upload(local, key)`, `output(ref, dest)`).

## 3. Correctness: FAIL on two paths
**Critical findings:**
- **C1 – capped sessions lose their outputs.** `wait()` treats `cancelacknowledged` as a failure, even when Kaggle ended a session at its time cap *after* the work finished. The studio saw exactly this on real hardware (job 136f1b32068c72a8). `submit --wait` then never fetches the outputs, and marks the run "error".
- **C2 – `poll` marks success without outputs.** `poll` records "complete" without fetching or verifying anything, and `output()` downloads without any hash or manifest check. Unproven output can be counted as done (the studio's worker verifies a manifest).

**Other findings:**
- **Transient errors:** one transient CLI error (network, 5xx) aborts `wait()`. There is no retry or backoff, and repeated "unknown" statuses loop until the 12.5-hour deadline.
- **Concurrency gap:** `choose()` and `ledger.start_run()` are two separate steps. Two schedulers can both choose before either reserves, despite the module's claim that it prevents this.
- **No default session cap:** `submit` has no default `-t`, so a job without `--timeout` can use a full 12 hours of quota whatever its estimate.
- **Interrupts:** a `KeyboardInterrupt` during `submit` leaves the run "running" until it is reaped about 13 hours later, holding quota.
- **R2 listing:** `latest_checkpoint` reads only the first 1,000 objects (no pagination), so past that it can pick the wrong "latest".
- **Notebook helper:**
  - its done-markers mismatch for extensions with two dots (`tar.gz`), so finished work is redone;
  - its clock starts at module import, not session start, so it can over-estimate time left.
- **Split runs:** a split count is computed, but nothing executes or resumes the splits.
- **Hardware fit:** there is no VRAM, RAM or model-capability check at all. The review scope's capability, hardware and memory-estimation items are not implemented, so not testable.

## 4. Reliability: WARNING
| Case | Result |
|---|---|
| Provider failure | `real_quota()` returns None and the router falls back to the local estimate (good). Push errors are caught. `wait()` has no retry. |
| GPU unavailable or queued | Polled with no special handling. |
| Model unavailable, or context too long | Not applicable: no models. |
| Queue timeout | 12.5-hour deadline only. |
| Interrupted job | No recovery path; rerun is manual. The notebook skips finished shards. |
| Retries exhausted | Not modelled. |
| Restart | The ledger is durable (SQLite WAL). |
| Idempotency | Only if the caller passes `--job-key` (optional). |

## 5. Test coverage: WARNING
- **What the tests prove:** the ledger arithmetic, the router's decisions (including the non-commercial gate and Modal being off), status parsing on real CLI strings, push arguments, and quota parsing.
- **Mocks that prove nothing about Kaggle:** every Kaggle test fakes `_run`. They do not show that a real push, wait or output works.

**Missing tests:**
- `wait()`: every terminal state, CANCEL_ACKNOWLEDGED after a finished run, repeated unknown statuses, transient errors.
- `output()` verification.
- `push` refusing a public or secret-bearing folder.
- `push_manifest`.
- `cmd_submit` end-to-end with fakes, including an interrupt.
- `cmd_poll` without outputs.
- The concurrency gap between choose and reserve.
- R2 (pagination, missing configuration).
- Modal: no tests at all.
- Notebook helper: done-markers, multi-dot extensions, the session clock.
- Environment parsing errors.

## 6. Performance: PASS (minor notes)
- **Routing cost:** negligible, a few SQLite queries.
- **Kaggle quota:** `real_quota()` calls the CLI on every `plan`/`submit`, about 1 to 3 seconds; acceptable.
- **R2:** a new boto3 client per call (wasteful, harmless).
- **Discovery:** no model or hardware discovery exists, so there is no discovery overhead.

## 7. Compatibility with the studio: FAIL (as an integration), PASS (as an idea source)
- **Duplication and gaps:** it duplicates the studio's Kaggle path without any of its gates:
  - the data-class gate;
  - the public-twin SHA-256 proof;
  - the private-kernel package builder;
  - manifest verification;
  - recovery (tested on hardware 24-25 Nov).
- **Rules it misses:** it uses neither the studio's model registry nor the free-mode rules (`llm.free_only`).
- **Tenant isolation:** it has none (`tenantmode`).

Adopting it as-is would create a second Kaggle path that is weaker than the first.

## 8. Defects ranked
- **Critical:**
  - S1: unfiltered, unchecked push;
  - S2: R2 keys inside Kaggle;
  - C1: outputs lost after a cap-cancel;
  - C2: completion without verified output.
- **Non-critical:**
  - S3: the bare-string gate;
  - no retry in `wait`;
  - the choose/reserve gap;
  - no default `-t`;
  - an interrupt holds quota;
  - R2 pagination;
  - the notebook helper's done-markers and clock;
  - environment parsing that can crash;
  - unexecuted split runs;
  - no tenant isolation.

## 9. Recommended changes (if the owner ever wants its ideas)
Do not integrate the plugin. Port its two useful ideas into the studio's own `computerouter`/`kaggleworker`:
- **Quota ledger:** a local ledger of estimated quota checked against Kaggle's own figure, with a reservation made atomically together with the decision;
- **Stage notebook:** shard and stage skipping in the notebook, with a session clock taken from the kernel's start, and outputs kept in `/kaggle/working`, never pushed to R2 with keys inside Kaggle.

If it ever runs alone, it needs:
- a file allowlist and an `is_private` check on push;
- `wait` treating cap-after-finish as complete and verifying a manifest;
- retries with backoff;
- a default `-t`;
- a gate on a recorded permission per job;
- tests for every path in section 5.

## 10. Verdict
**NOT safe to integrate now.** It is worth keeping only as a source of ideas. Its 27 passing tests cover arithmetic and parsing, not the risky paths. Nothing here changes the standing rule: Kaggle stays BLOCKED for commercial production until Kaggle's written permission exists.
