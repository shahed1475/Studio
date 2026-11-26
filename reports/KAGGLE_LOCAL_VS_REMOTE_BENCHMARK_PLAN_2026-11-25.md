# Local vs Kaggle benchmark plan (25 Nov 2026), NOTHING HAS RUN; each test needs its own approval

Supersedes nothing: it refines `KAGGLE_GPU_BENCHMARK_PLAN_2026-11-25.md` with today's engine and GPU findings.

## 1. Fairness rules
- **Same model bytes on both sides:** `Qwen3-4B-Instruct-2507-Q4_K_M.gguf`, sha256 `3605803b…e597` (local copy in `~/tools/sdcpp/models/`, Kaggle copy = the verified Hugging Face twin).
- **Same engine and build on both sides:** llama.cpp b12719, the CUDA 12.8 binary (see the compatibility report).
  - Fallback if that download is not approved: Ollama locally. That is not the same engine and not the same file (the 4B file is not in Ollama), so the comparison would be labelled "not controlled".
- **Same settings everywhere:**
  - the same 5 prompts (`data/compute/inputs/kaggle_benchmark_v1.json`), temperature 0;
  - `-c 4096`, `-n 160`, f16 KV cache;
  - 1 warm-up run (discarded), then 3 measured repeats;
  - cold load timed separately.
- **Speed statistic:** `llama-bench -p 512 -n 128 -r 3` for prompt and generation throughput (it reports mean ± sd), plus `llama-server` `timings` for each prompt (prompt_n, prompt_ms, predicted_n, predicted_ms) to get time to first token.

## 2. Local baseline preconditions (checked live just before the run; abort if any fails)
- **No production work running:** no ffmpeg or Blender process, the studio's Autopilot holds no render lock, and no Kaggle or voice job is running.
- **GPU:** less than 15% busy.
- **Memory:** at least 4 GB RAM available.
- **State recorded before the run:**
  - **VRAM:** at 06:48 UTC on 25 Nov, desktop apps already held 1,234 of 4,096 MiB, so about 2.8 GB was free. The 4B model (2.5 GB) plus KV and overhead will likely need **partial CPU offload**. The `-ngl` value used and the offload are recorded, never hidden.
  - **RAM:** 8 GB available, swap 5 of 7 GB in use.
- **During the run:**
  - throttle reasons, temperature and power are sampled every 2 s;
  - **stop** if a production job starts or GPU temperature exceeds 85 °C.
- **Estimate:** about 10 minutes of this PC's GPU and CPU; no quota; no cost.

## 3. Kaggle tests (quota estimates; one job at a time; `-t` always set)
| Test | What | Quota (estimate) | Stop |
|---|---|---|---|
| A environment | nvidia-smi + `topo -m`, compute capability, P2P check, `which nvcc`, gcc/cmake versions, a 2 s matmul on **each** T4 with per-device memory; no model | 2–3 GPU min, `-t 600` | not started 60 min after push: report, never cancel |
| B single-T4 engine | the 4B twin on llama.cpp 12.8 binary, `-sm none` (download + hash + PTX JIT time recorded), then today's transformers engine for comparison | about 10 min, `-t 1800` | JIT or load > 10 min; GPU utilisation < 20% during generation |
| Multi-GPU | the same twin: (i) `-sm layer` across both, (ii) two processes on devices 0 and 1, 20 items each; per-device memory and utilisation | about 10 min | either device below 1 GB while "used" = FAIL of the claim |
| C 8B | `qwen3:8b` via the Ollama-registry twin (layer `a3de86cd…`, 5,225,374,496 bytes, registry manifest digest = local, verified 25 Nov) on one T4 | about 12 min | hash mismatch: nothing runs |
| E recovery | see the quota and recovery design | about 2 x 4 min | any item answered twice = FAIL |

Total: about 40–50 GPU minutes of the remaining weekly quota (live value to be read by the preflight, never assumed).

## 4. Result table (filled only by measurements; empty cells stay "not run")
| Metric | Local PC | Kaggle single T4 | Kaggle two T4 |
|---|---:|---:|---:|
| Queue wait | n/a | not run | not run |
| Environment setup | not run | not run | not run |
| Model load (cold / warm) | not run | not run | not run |
| Time to first token | not run | not run | not run |
| Generation tok/s (mean ± sd, n=3) | not run | not run | not run |
| Prompt tok/s | not run | not run | not run |
| GPU memory (per device) | not run | not run | not run |
| GPU utilisation (per device) | not run | not run | not run |
| Output retrieval | n/a | not run | not run |
| Total turnaround | not run | not run | not run |
| Quota consumed (from `kaggle quota` before and after) | n/a | not run | not run |

Measured earlier, a different engine, so it is not comparable: Kaggle transformers fp16, 9.7–15.6 tok/s on 3–43-token answers.

## 5. Two separate questions
1. **Raw throughput:** warm tok/s and items per hour.
2. **Verified turnaround:** push → retrieved → verified, against local start → verified.

Kaggle may win (1) and still lose (2) because of the queue (0 to 137 min seen). "Kaggle is faster" is claimed only if (2) wins for the same model and settings. A model that cannot run locally is reported as "Kaggle-only".
