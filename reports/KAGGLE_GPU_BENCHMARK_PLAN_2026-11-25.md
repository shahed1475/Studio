# Kaggle GPU benchmark plan (25 Nov 2026), awaiting approval

**Nothing in this plan has run.** No benchmark, local or remote, was started in this session.

## What is already measured (VERIFIED, 24 Nov 2026)
| | Kaggle 2 x T4 (one used) | This PC, GTX 1050 Ti 4 GB |
|---|---|---|
| Qwen3-4B-Instruct-2507 Q4_K_M | transformers-gguf dequantised to fp16: 9.7–15.6 tok/s on 3–43-token answers; load 101–111 s; model download + hash 13–14 s; environment 19–40 s | **not measured** |
| qwen2.5:1.5b Q4_K_M (Ollama) | not run | 49 tok/s fully on GPU; 26 tok/s on CPU |
| qwen2.5-coder:7b Q4_K_M (Ollama) | not run | 10.3 tok/s with CPU offload (1.94 of 4.91 GB on the GPU) |
| Z-Image Turbo picture | not run | 768x448: 312–340 s; 704x1248: about 14 min (stable-diffusion.cpp, CPU offload) |
| Queue wait before a session starts | 0–4 min, 2 h 17 min, about 37 min (3 sessions) | 0 |

**Assessment (INFERENCE, to be tested).**
- **Small models:** a 4B model that fits in 4 GB is very likely *faster locally*. Kaggle adds the queue (0 to more than 2 h), about 20–40 s of environment and about 100 s of loading in the current engine. The current engine also dequantises to fp16 and uses one of two T4s.
- **Where Kaggle could win:**
  - models that do not fit locally (8B Q4 needs about 7 GB; 30B MoE needs both T4s);
  - batches long enough to amortise about 3 minutes of fixed cost;
  - image models, as an engine-measured benchmark only (production pictures are BLOCKED).

## Instruments needed first (Category B code, no quota)
- **Absolute times:** `pushed_at`, plus `remote_started_at` from `kaggle kernels list` `lastRunTime` (checked today: 20:08:09 for the v2 session pushed at 19:31:24).
- **Inside the notebook:**
  - GPU utilisation and memory every 2 s (nvidia-smi in a thread);
  - prompt tokens and time to first token (streamer callback);
  - peak RAM;
  - per-device placement.
- **Local harness:** the same 5 prompts through Ollama (`/api/generate` reports `eval_count`, `eval_duration`, `prompt_eval_count`, `load_duration`), fixed `num_ctx 4096`, temperature 0, warm and cold runs recorded separately.
- **Ledger:** GPU hours per job, from the `kaggle quota` difference before and after.

## Tests (each NEEDS APPROVAL before it spends quota)
| Test | Task id (proposed) | What | Expected result | Resource estimate | Stop condition |
|---|---|---|---|---|---|
| **0 Local baseline** | `bench-local-qwen3-4b-v1` | Qwen3-4B Q4_K_M and qwen3:8b on this PC (Ollama), 5 prompts, 3 cold + 3 warm runs | tok/s, time to first token, load time, VRAM/offload | this PC about 10 min; no quota; run when no render or Autopilot job is active | GPU busy > 85% or a production job starts |
| **A Environment** | `bench-env-t4-v1` | push a 30-line notebook: nvidia-smi, torch/CUDA versions, GPU memory, a 2 s matmul on each T4, utilisation sample; **no model** | 2 x T4, CUDA OK, both devices compute | about 2–3 GPU min; `-t 600` | session not started 60 min after push: report, do not cancel |
| **B Small model, engine comparison** | `bench-qwen3-4b-engines-v1` | the verified Qwen3-4B twin, 5 prompts, temperature 0, (1) transformers-gguf fp16 (today's engine), (2) llama.cpp CUDA from a **prebuilt** wheel or binary, if one exists for Python 3.13 / CUDA 12–13 (UNVERIFIED) | same answers as before (q5 may stay wrong: 401), tok/s per engine, GPU utilisation > 50% during generation | about 10 GPU min; `-t 1800` | engine install > 8 min, or GPU utilisation < 20% (CPU-bound: investigate) |
| **C Medium model** | `bench-qwen3-8b-v1` | qwen3:8b Q4_K_M via an **Ollama-registry twin** (blob `a3de86cd…`, 5,225,374,496 bytes, publicly served; needs the twin code) on the best engine from B | fits on one T4 (estimate ~7.2 GB at ctx 8192), tok/s vs local offload | about 12 GPU min | twin hash mismatch (nothing runs) |
| **D Larger model** | `bench-qwen3-coder-30b-v1` | only if B and C pass and a public twin of the owner's `qwen3-coder-30b` (or an official public GGUF of the same model, recorded as a public model, not the owner's file) is proven; split across both T4s | ~22 GB needed: both T4s | about 25 GPU min; download about 19 GB inside the session | does not fit or loads > 10 min |
| **E Recovery (mid-item)** | `bench-recovery-cut-v1` | 20 short items with `-t` set to end the session mid-run (a planned cap, not a manual kill); then `kaggle-recover` | the finished items are kept, the rest run once, no duplicates | about 2 x 4 GPU min | anything repeated twice = FAIL |
| **F Artifact integrity** | part of every test | manifest SHA-256, schema, non-empty answers, model-hash proof, plus a semantic check: known-answer prompts (q2 primes, q4 Jupiter, q5 = 391) | all pass; q5 recorded as a model error if still 401 | — | any mismatch = FAILED, never COMPLETED |

- **Total if all run:** about 1.0–1.5 GPU h of the 18.12 h left this week (refresh 28 Nov).
- **Order:** 0 → A → B, then decide; C only after B, D only after C, E any time after A.
- **Session plan:** one GPU job at a time, in at most a 9-hour session.

## What would count as "Kaggle is faster"
Kaggle is faster only when the **end-to-end** time (queue + start + load + run + retrieval) beats the local end-to-end time for the same model, prompts and settings. A model that cannot run locally at all is reported as "Kaggle-only", not "faster".
