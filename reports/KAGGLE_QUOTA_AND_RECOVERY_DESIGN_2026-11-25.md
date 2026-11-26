# Kaggle quota preflight, job states and recovery: design (25 Nov 2026), not implemented

## 1. What the platform offers (VERIFIED in installed CLI 2.2.5 / kagglesdk 0.1.38 source, and Kaggle docs read 25 Nov)
- **Quota:**
  - `kaggle quota --format json` calls `get_accelerator_quota_statistics`, which returns `gpu_quota.time_used`, `gpu_quota.total_time_allowed` and `quota_refresh_time` (`kaggle_api_extended.py:6747`). This is a supported API, so no scraping is needed.
  - `kaggleworker.check()` already calls it, but nothing gates on it.
  - **Correction:** the studio skill card `model-resource-monitor` says hours "are not readable by its API". That is out of date; the card is not edited here.
- **Kaggle docs (Efficient GPU usage):**
  - the weekly quota "is 30 hours or sometimes higher depending on demand and resources", so 30 h is never hard-coded;
  - "The same Notebook can have multiple concurrent batch sessions if you press the commit button prior to completing the first commit", so a second push while one is queued or running doubles the spend.
- **Session status:**
  - `get_kernel_session_status` returns only `status` and `failure_message` (no timestamps);
  - the statuses are QUEUED, RUNNING, COMPLETE, ERROR, CANCEL_REQUESTED, CANCEL_ACKNOWLEDGED, NEW_SCRIPT;
  - `kernels list --mine` gives `lastRunTime`;
  - there is no "list running sessions" call: running sessions are found by checking each `studio-job-*` kernel.
- **Cancel:** `cancel_kernel_session` exists in the SDK but not in the CLI. The studio never cancels; it recommends to the owner.
- **Output:** `kernels output` lists files page by page and **refuses names that resolve outside the target directory** (`_is_within_directory`). It raises an error on a failed download. Each name is written under the `-p` folder, and the log goes to `<slug>.log`.
- **Session limits:** 12 h per Notebooks docs, 9 h per GPU tips. Plan with **9 h**.

## 2. Quota preflight (runs before every push; any "no" means no push)
1. **Live quota:** `kaggle quota --format json`; parse GPU used, total and refresh. If unreadable → **BLOCKED_QUOTA ("quota unknown")**.
2. **Running sessions:** status of every studio kernel with a non-final job. If any is QUEUED or RUNNING → **BLOCKED_QUOTA ("a session is already queued or running")**. That is one GPU job at a time, and it also blocks the duplicate-commit case.
3. **Need:** `need_h = estimate(job) x 1.5 + 0.1` (setup), capped by the job's `-t`.
4. **Reservations:** subtract reservations of jobs pushed but not yet reflected in `time_used` (ledger below).
5. **Allow** only if `remaining - reserved - need_h >= safety_margin_h` (proposed 2 h) and `-t <= 9 h`.
6. **Other conditions:**
   - the policy gate passes (`kaggle_gate`, unchanged);
   - the accelerator equals the job's request;
   - the fit check passes (`computecompat.need` against the T4 spec);
   - the job is not already pushed (existing `submit` guard).
7. **Ledger:** `data/compute/kaggle_ledger.json`, one entry per push, with `pushed_at`, `t_cap_s`, `quota_before`, `quota_after` (read at retrieval) and `consumed_h`. Written atomically (tmp + `os.replace`). A reservation is released when the job is final.

## 3. Timeouts
- **Queue timeout:** a job still QUEUED `queue_timeout_s` (proposed 3600 s) after push gets `remote.queue_timed_out = true` and an owner notice: "still waiting for a Kaggle GPU; cancel in the Kaggle UI if you no longer want it". It is **not** cancelled by the studio. An unstarted queued session uses no GPU time (INFERENCE: quota is charged for execution).
- **Submission timeout:** the push command keeps its existing 300 s limit; a timeout leaves the job QUEUED (local) and is retried once.
- **Job deadline:** `-t` (`session_cap_s`) per push; the job's overall `deadline_at` is checked at each poll.
- **Retry policy:** a FAILED push is retried at most `MAX_ATTEMPTS` (5, existing), with backoff of 2, 8 and 30 min. A verification FAILED is never auto-retried.

## 4. States: the requested names mapped onto `computejobs` (no renames; the dashboard and 3123 tests depend on them)
| Requested | Implemented as |
|---|---|
| SUBMITTED | PREPARING + `remote.pushed_at` |
| QUEUED (remote) | PREPARING + `remote.state = "queued"` |
| RUNNING | MODEL_LOADING / RUNNING |
| CHECKPOINTING | CHECKPOINTED |
| COMPLETED_UNVERIFIED | event in history: "retrieved, not yet verified" (transient inside `poll`) |
| VALIDATING_OUTPUT | `verify()` step (transient) |
| SUCCEEDED | COMPLETED (only after `verify().ok`) |
| FAILED | FAILED |
| EXPIRED | INTERRUPTED + `remote.ended = "time cap"` |
| RECOVERY_REQUIRED | INTERRUPTED → RECOVERY_PENDING |
| BLOCKED_POLICY | BLOCKED / BLOCKED_PENDING_TERMS_REVIEW |
| BLOCKED_QUOTA | **new status** `BLOCKED_QUOTA`; `NEXT`: QUEUED→BLOCKED_QUOTA, RECOVERY_PENDING→BLOCKED_QUOTA, BLOCKED_QUOTA→QUEUED |

## 5. Mid-generation recovery: what exists and what is missing
**Exists (VERIFIED in code):**
- results are appended per item with `flush` + `fsync`;
- `verify` drops a cut JSON line ("cut mid-write") and keeps complete items;
- `poll` marks a capped session with missing items INTERRUPTED and keeps the verified answers;
- `recover` pushes a new package that skips them, and never pushes when nothing is left.

**Missing:**
1. **No proof that Kaggle saves `/kaggle/working` when a session is cut mid-run.** Hardware evidence is cap-after-finish only.
2. **The manifest is written only at `finish()`.** A cut session has no manifest, so its partial file cannot be integrity-checked. Fix: a per-item record with its own SHA-256 (`row_sha256` over the canonical row) plus `checkpoint.json` (count, last id, running hash), rewritten atomically after each item.
3. **No per-item integrity check on retrieval.** Fix: accept a recovered row only if its `row_sha256` matches and its id is in the job's item set; reject duplicates.
4. **No end time or reason.** Fix: `started_at_utc` and `last_item_at_utc` in the report.

**Controlled test (Test E, after offline tests pass):**
- 20 short items, `-t` set to roughly half the expected run (a planned cap, not a manual kill);
- expected: INTERRUPTED with k verified items, then `kaggle-recover` pushes 20−k, then COMPLETED with 20 unique ids and no duplicates;
- any duplicate, or any unverified row accepted = FAIL.

**Offline first:** a fake notebook run cut after item k (the existing `STUDIO_TEST_ENGINE=echo` harness), with a truncated last line and a missing manifest.

## 6. Output durability and validity
- **Durability:** outputs live in Kaggle's saved version output only, retrieved with the authenticated CLI into a NEW folder (existing). No external storage and no keys in the session. If Kaggle does not save a cut session's output (Test E), mid-run recovery is **BLOCKED** and jobs are sized to finish well inside `-t`.
- **Validity:**
  - manifest SHA-256 of `report.json` and `results.jsonl`;
  - per-row hash;
  - model-file hash proof;
  - engine consistency;
  - `finished`;
  - a JSON schema per row;
  - an allowlist of retrieved file names (`report.json`, `results.jsonl`, `manifest.json`, `checkpoint.json`, `<slug>.log`; anything else → FAILED, never read);
  - a size cap (50 MB total);
  - a semantic check (known answers: primes, Jupiter, 17 x 23 = 391; a wrong answer is recorded as a model error, not a pass).
