# Kaggle multi-GPU investigation (25 Nov 2026), read-only; no Kaggle job, no quota used

## 1. Why the second T4 was idle (VERIFIED from code and the three real reports)
- **Cause, in our own code:** `kaggleworker.py:379` loads the model with `.to("cuda:0")`, and `:382` sends every prompt to `cuda:0`. One process, one device, by design. Nothing in the notebook ever addresses device 1.
- **Evidence it was truly idle (not a sampling artefact):** each report's `engine.gpu_used_after_load_mib` reads `"7833\n3"`, which is nvidia-smi memory used on GPU 0 and GPU 1: 7,833 MiB against 3 MiB. After the run it reads `"7895\n3"`. 3 MiB is less than a CUDA context, so no process even opened device 1. This is an allocation reading, not a utilisation sample. Files: `data/compute/kaggle_outputs/{8ba727ef5f45c77c,136f1b32068c72a8}/v*/report.json`.
- **Also:** `peak_gpu_allocated_gb` (8.12) is `torch.cuda.max_memory_allocated()` for the current device only, so it could never show a second GPU.
- **The environment did expose both:** the reports list `gpus = [Tesla T4 15.64 GB, Tesla T4 15.64 GB]` (torch 2.11.0+cu130, CUDA 13.0, driver 580.178.04, Python 3.13.16, 4 CPUs, 32.9 GB RAM).
- **Not yet known (Test A):**
  - whether peer-to-peer access between the two T4s works (`torch.cuda.can_device_access_peer`, `nvidia-smi topo -m`);
  - the PCIe link between them (T4s have no NVLink);
  - whether NCCL is usable.

## 2. Can the current worker use both GPUs?
**No.** Neither of its engines can:
- **transformers:** single device by design (`.to("cuda:0")`).
- **llama.cpp:** never loaded, because its build failed.

Using both needs a code change and a real test. Multi-GPU support is **not claimed**.

## 3. Three approaches (llama.cpp `docs/multi-gpu.md`, commit b9afc19c, 2026-05-07; `common/arg.cpp` and `src/llama-arch.cpp` on master, 2026-11-24/25)
| Approach | How | What it buys | What it costs | Qwen3-4B (2.5 GB Q4) | 8B Q4 (5.2 GB) | 12–14B Q4 (~7–9 GB) | 30B MoE Q4 (~18–19 GB) |
|---|---|---|---|---|---|---|---|
| **A. One GPU** | `--split-mode none` / `-dev CUDA0`, or `CUDA_VISIBLE_DEVICES=0` | lowest latency for one request; simplest | the other T4 idle | **best for one stream** | fits one T4 | fits one T4 at moderate context | does not fit one T4 |
| **B. Split one model** | `--split-mode layer` (the default, pipeline) or `tensor` (EXPERIMENTAL) | capacity: a model larger than 15 GB; `layer` helps prefill or batch throughput | `layer`: "requires many tokens to scale well", with no single-request speed-up; `tensor`: cross-GPU reductions over PCIe, needs flash-attn and an f16/bf16 KV cache, no auto-fit, and NCCL for good speed | no benefit (INFERENCE) | no benefit | optional, only for long context | **required**: `layer` across both |
| **C. Two independent jobs** | two processes, `CUDA_VISIBLE_DEVICES=0` and `=1`, each takes half the items | about 2x items per hour for batches (INFERENCE: limited by 4 shared CPUs and 29 GB RAM) | two model loads (RAM), two logs; Kaggle accounts GPU time per session, not per device (UNVERIFIED) | **best for batches** | best for batches | best for batches | not possible (needs both GPUs) |

- **Tensor mode** is allowed for `qwen3`, `qwen3moe`, `qwen2`, `llama` and `gemma4`: none is on the exclusion list in `llm_arch_supports_sm_tensor` (llama-arch.cpp:1562). It stays **experimental** and is not a default.
- **Official llama.cpp release binaries** are built with `-DGGML_CUDA_NCCL=OFF` (release.yml, commit fd24ee26, 2026-11-23). Tensor mode with them prints the "NCCL is unavailable" warning, so it is slower (official doc statement).
- **Memory limits:**
  - a T4 is 15.64 GB as torch reports it, 15,360 MiB per nvidia-smi;
  - the studio's `computecompat.need` estimates weights, plus KV cache, plus about 0.45 GB, plus 6%;
  - Qwen3-4B in today's fp16 engine took 8.1 GB, because it was dequantised. In llama.cpp it would stay Q4, at about 2.5 GB plus KV.

## 4. Recommendation (INFERENCE until benchmarked)
- **4B and 8B:** approach A for one request; approach C for batches of 20 or more items.
- **12–14B:** approach A at moderate context; B (`layer`) only when the context does not fit.
- **30B MoE:** B (`layer`) across both T4s, and only with a verified public twin.
- **Never** make `tensor` the production default.

## 5. Code changes needed (proposal; see KAGGLE_WORKER_IMPLEMENTATION_PROPOSAL)
- **Engine:** llama.cpp from the pinned official prebuilt binary (no compiling).
- **Placement:** a `placement` parameter per job: `single` (`-sm none -mg 0`), `split-layer`, or `parallel-2` (two processes).
- **Measurement:** per-device memory and utilisation every 2 s (nvidia-smi `-i 0,1`), recorded per stage.
- **Verification:** the report must show more than 1 GB used on **both** devices before any claim that "both GPUs are used".

## 6. Provable without quota
- the code cause above;
- the flags, modes and architecture support (source code);
- the memory arithmetic;
- the fake-backed tests of the new placement code (that commands are built correctly and the parser reads per-device memory).

Throughput, P2P and stability need a real session: Test A (environment) and the multi-GPU test.
