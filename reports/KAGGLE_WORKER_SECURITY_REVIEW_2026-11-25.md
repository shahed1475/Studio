# Kaggle worker security review (25 Nov 2026)

Read-only review of the studio's Kaggle worker (`kaggleworker.py`, `computerouter.py`, `computejobs.py`, the `~/.local/bin/kaggle` wrapper). The GPU-router plugin is reviewed separately below and was not changed. No secret was printed or written while preparing this report.

## A. Studio worker (in production code, used only for the `benchmark` task)
| Risk | Finding | Status |
|---|---|---|
| Credential in a notebook | `prepare` writes only `kernel-metadata.json` and `run.py`, and refuses to write if either matches `computejobs.SECRET` (key, token, password and bearer patterns). The notebook downloads only a PUBLIC model, with no token. | PASS (tests: `test_the_package_is_private_on_a_t4_with_the_twins_hash_and_no_credential`) |
| Whole-folder upload | **VERIFIED in the installed CLI source** (`kaggle_api_extended.py`, `kernels_push`): push reads `kernel-metadata.json` and the one `code_file` it names, and sends that file's text. Nothing else in the folder is uploaded. The studio's folder holds only those two files. | PASS |
| Private kernel | `is_private: true`, set by `prepare` and tested. | PASS |
| Owner's files leaving the PC | Never: only a public twin with the same SHA-256 runs. A different hash means the notebook runs nothing (tested). | PASS |
| Production or private data to Kaggle | `kaggle_gate` lets only `public-test` data through; an unmarked class counts as production. | PASS |
| Token handling on this PC | The wrapper reads `kaggle_api_token` from `~/studio/settings.json` into one environment variable for the CLI process only, and never prints it. `kaggleworker.check` prints no credential (tested). Never `kaggle auth print-access-token`, never `config view`. | PASS |
| Logs and outputs | `_fetch.txt` keeps the CLI's last 2,000 characters of stdout and stderr, and `report.json` keeps library versions and nvidia-smi output. No secret was seen in the 3 retrievals (checked by reading them today with a key-name filter). | PASS (UNVERIFIED for future CLI versions) |
| Paths | Retrieval goes into a new folder under `data/compute/kaggle_outputs/<job>/`. The job id is a hex hash, and owner and competition slugs are regex-checked. | PASS |
| Integrity | `verify`: manifest SHA-256 of `report.json` and `results.jsonl`, model-hash proof, engine consistency, finished flag, non-empty answers, no missing items. COMPLETED only if all hold (tested, including tampering). | PASS |
| Remote storage | None used; no storage key exists anywhere in the worker. | PASS |
| Competition data | `spaceship-titanic` is attached to benchmark kernels (its CSV header is read). Unnecessary, and its terms are unclear. | WARNING (remove; Category B) |
| Quota abuse | No live quota check before a push; no concurrency limit. | WARNING (add BLOCKED_QUOTA; Category B) |
| Cancelling sessions | No cancel in code. The CLI has none; the SDK call exists but is unused. | PASS (owner-only) |

## B. GPU-router plugin (review only; NOT installed, integrated, merged, pushed or deployed)
- **Branch state, verified today:** `feature/gpu-router-plugin` at `7fa9023` in `/home/fahad/studio-worktrees/gpu-router-plugin` (outside the forbidden folder). Local and remote are identical, and the working tree is clean (0 changed files).
- **The four reported issues, checked against the code** (see `reports/GPU_ROUTER_PLUGIN_REVIEW_2026-11-25.md` for line-level detail):
  1. **Whole job folder uploaded without checks:** partly true.
     - **Correction from today's CLI-source reading:** `kernels push` sends only the metadata and code file, so the plugin's push does not upload every file.
     - Its `push_manifest` (`datasets version -p <dir> -r zip`) **does** upload a whole folder as a dataset version, with no allowlist and no privacy check. The plugin's `check_metadata` never checks `is_private`, so a public kernel would publish its code.
     - Verdict: FAIL for datasets; WARNING for kernels.
  2. **Storage keys inside Kaggle:** true by design (the notebook helper pushes artifacts to R2 from inside the session). FAIL.
  3. **Outputs lost after a capped session:** true (`wait()` treats `cancelacknowledged` as failure, so `submit --wait` never fetches). FAIL.
  4. **Complete without verified results:** true (`poll` marks complete without fetching; `output()` has no hash check). FAIL.
- **Also:**
  - no retry or backoff in `wait()`;
  - a gap between choosing and reserving quota;
  - no default `-t`;
  - an interrupt holds the ledger until it is reaped about 13 h later;
  - R2 listing reads only the first page;
  - a gate on any non-empty string;
  - no tenant isolation;
  - 27 tests cover arithmetic and parsing only.
- **Remediation design** (if the owner ever wants it; implementation needs separate approval):
  - **Path:** do not integrate the plugin. Port two ideas into the studio worker instead: the quota ledger, checked against `kaggle quota` and reserved atomically with the decision; and stage skipping inside a notebook.
  - **Push and datasets:** keep the studio's push (two files, private, secret-scanned). Never `datasets version` a folder: if inputs are ever needed, build a private dataset from an explicit allowlist of public-test files, each hashed, size-capped and secret-scanned.
  - **Outputs:** stay in Kaggle's saved output, retrieved with the authenticated CLI. No keys in sessions.
  - **Completion:** only after manifest verification, as `kaggleworker.verify` does today.

## C. Tests the brief asks for, mapped to what exists
| Required test | Exists? |
|---|---|
| Unit; mocked Kaggle integration | yes (58 tests, fakes) |
| Duplicate submission / idempotency | yes (`a push … is not pushed twice`; job id hash; `a production request is never handed an earlier public-test job`) |
| Checkpoint / recovery; session expiry | yes, with fakes (`an expired session keeps what it finished…`, `cancelled at its cap after finishing…`, `recovery never pushes…`); hardware: cap-after-finish only |
| Missing output; corrupted artifact; hash mismatch | partly (`a tampered output is never completed`; missing manifest handled in `verify`); a dedicated missing-output test is a gap |
| Invalid schema | gap (a non-JSON line is flagged; there is no schema test) |
| Secret leak | yes (package scan; `the account check prints no credential`) |
| Path traversal | gap (slug regexes exist; no traversal test on retrieved file names) |
| Policy block | yes (`only as a verified twin for a permitted personal task`; production class) |
| GPU not available; model does not fit; CPU fallback detection | routing tests cover no GPU and insufficient VRAM locally; **gap** for Kaggle (detect `device` not CUDA and the second-GPU idle case) |
| Quota exhaustion | gap (no BLOCKED_QUOTA) |
| Queue timeout | gap (QUEUED is reported; no timeout policy) |
| Studio restart | gap (by design durable; no test) |
| Real Kaggle tests | 3 sessions on 24 Nov; any new one NEEDS APPROVAL |

Layers reported separately, as the brief asks: a mocked test does not prove Kaggle works; the real inference does not prove recovery; a completed session does not prove retrieval; a retrieved output does not prove its meaning. The q5 answer "401" for 17 x 23 is a real model error that passed the integrity checks. Semantic checks are the next layer (benchmark plan, test F).
