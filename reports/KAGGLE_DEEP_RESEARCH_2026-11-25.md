# Kaggle GPU worker: deep research summary (25 Nov 2026), read-only

Companion reports, all dated 2026-11-25:
- KAGGLE_MULTI_GPU_INVESTIGATION
- KAGGLE_LLAMA_CPP_CUDA_COMPATIBILITY
- KAGGLE_LOCAL_VS_REMOTE_BENCHMARK_PLAN
- KAGGLE_QUOTA_AND_RECOVERY_DESIGN
- KAGGLE_WORKER_IMPLEMENTATION_PROPOSAL
- CLAUDE_SESSION_STARTUP_HOOK_REVIEW

**Nothing was submitted to Kaggle, no quota was read or used, no model was downloaded, no code or setting was changed.**

## A. Sources (each read on 25 Nov 2026)
| Source | Version or commit | Used for | Kind |
|---|---|---|---|
| kaggle.com/terms | "Terms Version June 22, 2025 (active)" | service-use clause, competition clause | official |
| kaggle.com/docs/competitions | live page | rules must be accepted before data access | official |
| kaggle.com/docs/notebooks | live page | 12 h sessions; 20 GB saved output; "T4 x2 … 4 CPU cores 29 Gigabytes of RAM"; notebook output usable as another notebook's input | official |
| kaggle.com/docs/efficient-gpu-usage | live page | "30 hours or sometimes higher"; concurrent batch sessions from repeated commits | official |
| Kaggle CLI 2.2.5 + kagglesdk 0.1.38 (installed source) | as installed | quota API, output path check, status enum, cancel API not in CLI | code |
| github.com/Kaggle/kaggle-cli docs/kernels.md | 87ea99e4 (2026-10-22) | push flags, `-t` | official |
| llama.cpp docs/multi-gpu.md | b9afc19c (2026-05-07) | split modes | official |
| llama.cpp docs/build.md | 7476e472 (2026-11-21) | CUDA build | official |
| llama.cpp common/arg.cpp, src/llama-arch.cpp, src/llama-model.cpp | master 2026-11-24/25 (arch 33aeb17f) | modes in code; tensor-mode allowlist; architecture names | code |
| llama.cpp .github/workflows/release.yml; ggml/src/ggml-cuda/CMakeLists.txt | fd24ee26 (2026-11-23); 2cbfc3cf (2026-11-18) | release build flags; default CUDA arch set | code |
| llama.cpp releases b12719 | 2026-11-25 05:59 UTC | prebuilt ubuntu CUDA 12.8 / 13.5 binaries, SHA-256 digests | data |
| abetlen/llama-cpp-python README | 7f16fe19 (2026-06-06) | wheel CUDA versions and compute capability | official (project) |
| PyPI llama-cpp-python; abetlen wheel index | 0.3.38 sdist (2026-11-23); wheels to 0.3.37 | why pip compiled | data |
| NVIDIA CUDA Toolkit release notes (CUDA 13.5 page) | live | Pascal removed in 13.0; driver branches | official |
| NVIDIA CUDA Compatibility guide | live | PTX on older drivers does not work | official |
| code.claude.com/docs/en/hooks | live | SessionStart semantics | official |
| registry.ollama.ai manifests (6 models) | live | twin feasibility | data |

**Not used, and why:**
- the PyTorch get-started page renders by script and was not needed: the Kaggle torch build is measured (2.11.0+cu130), and no local torch engine is proposed;
- PyTorch's old `build_cuda.sh` path returned 404 (the file was refactored on 2026-05-07);
- the NVIDIA cuda-gpus page was not re-read: the T4's 7.5 is NVIDIA's published value, and the local 6.1 was read from `nvidia-smi`.

## B. Policy: terms vs competition data (official text; interpretation marked)
- **Terms** (official):
  - "You will only use the Services for your own internal, personal, non-commercial use, and not on behalf of or for the benefit of any third party".
  - "Services" = "our website(s), products, services and applications", which includes Notebooks and their GPUs.
  - On competitions: "Competitions are subject to separate Competition Rules … established by the Host User", the rules "must comply with all applicable laws and these Terms", and "The Competition Rules may impose additional restrictions or requirements".
- **spaceship-titanic rules** (read 24/25 Nov): the summary says "Competition Use and Academic, Non-Commercial Use Only"; section A says the Competition Data may be used "for any purpose, whether commercial or non-commercial". The page contradicts itself.
- **Reading** (INFERENCE, not legal advice):
  - A Host User's rules grant rights in **that competition's data**. They are written under the Terms, which they must comply with, and may only *add* restrictions.
  - Nothing in them grants rights to use Kaggle's **compute** commercially.
  - A data licence and a service-use licence are different things. Section A could at most permit commercial use of the CSV files elsewhere; it does not lift the non-commercial limit on Notebooks.
  - Where the two clauses meet, the result is **BLOCKED pending Kaggle's written answer**.
- **Studio action proposed:**
  - remove `test_competition: "spaceship-titanic"` from `config/compute.json`, which `run.py compute kaggle-test` attaches by default;
  - drop the notebook's `train.csv` header and row-count reading.
  - The first real run (8ba727ef) did read that file's 14 column names and 8,693 rows into its report.

| Workload | Data | Model licence | Commercial | Kaggle status |
|---|---|---|---|---|
| Small personal benchmark | public test prompts | verified twin (Apache-2.0 / MIT) | no | **ALLOWED-CONDITIONAL** (owner's standing decision `owner_permitted_tasks: ["benchmark"]`; residual ambiguity because results inform a monetised channel's infrastructure) |
| Competition task | exactly that competition's data | per rules | per competition rules | **ALLOWED within the rules; never for other workloads** |
| Local model experiment on Kaggle | owner's data | — | no | **BLOCKED by studio policy** (owner data never leaves the PC) |
| Local model experiment on Kaggle | public test data | verified twin | no | same as benchmark |
| Monetised documentary production | studio assets | — | yes | **BLOCKED absent Kaggle's written authorization** |
| Third-party customer workload | customer data | — | third-party benefit | **BLOCKED** ("not on behalf of or for the benefit of any third party") |

## C. Model compatibility (inventory of 24 Nov, unchanged: Ollama 0.34.4, 33 models, all six tag digests identical to the inventory)
| Class | Models | Why |
|---|---|---|
| **Runnable now** (benchmark only) | Qwen3-4B-Instruct-2507 Q4_K_M (twin `3605803b…`, 3 real sessions, transformers fp16) | verified twin; ran |
| **Runnable after a code change** (Ollama-registry twins) | qwen3:8b (`a3de86cd…`, 5,225,374,496 B), qwen3:1.7b, qwen2.5:1.5b, qwen2.5-coder:7b, deepseek-r1:8b (arch qwen3, MIT) | registry manifest digest = local tag digest and model layer = local blob (checked 25 Nov). Architectures known to upstream llama.cpp. Licence from the Ollama licence layer. Needs: twin code for registry blobs, and a llama.cpp engine |
| **Image, benchmark only** | z_image_turbo-Q3_K (twin verified, never run) | needs stable-diffusion.cpp or diffusers on Kaggle; NEEDS OWNER CONFIRMATION (new task type) |
| **Needs a different engine / not a twin** | qwen2.5vl:3b | Ollama's arch `qwen25vl` is not in upstream llama.cpp (`llama-arch.cpp` has `qwen2vl`, not `qwen25vl`); would need the Hugging Face GGUF + mmproj, which are different files |
| **Needs conversion** | owner's safetensors folders (qwen3-coder-30b, qwen36-35b, deepseek-v4-flash-reap, cyberexpert-merged*) | GGUF conversion = new files; plus they are private |
| **Does not fit 2 x T4** | deepseek-v4-flash-reap (84.7 GB) | memory |
| **Licence unknown** | dolphin-mistral-nemo, deepseek-coder-7b (hf.co), cyberexpert*, gemma4 builds, LFM2.5 merge | `license` null in inventory |
| **Policy blocked** | owner fine-tunes and LoRAs (private, no public twin); NSFW, abliterated and heretic models (content policy) | twin rule; content rule |

**Byte identity:** an Ollama blob is stored and fetched by its SHA-256 (the registry URL contains the digest), so a digest-pinned download is byte-identical. The notebook proves it by hashing before running anything (existing twin rule). Tags can move, so the twin pins the **layer digest**, never `qwen3:8b`.

## D. Security of the studio worker today (from the 25 Nov security review, rechecked)
- **Push:** private, two files, secret scan; the CLI's `kernels push` sends only the code file.
- **Credentials:** no credential is in the session; outputs go to new folders.
- **Path safety:** the CLI refuses traversal in output names (verified in 2.2.5 source). The studio adds no allowlist of its own (proposed).
- **Remaining:** the competition attachment and the missing quota gate.
- **No secret exposure was found.** This session's only credential sighting was the sandbox's own temporary proxy credential, printed to the assistant's tool output by an environment listing. It was not written anywhere and is not an owner key.

## E. Unverified (needs a test or the owner)
- Kaggle saving `/kaggle/working` after a mid-run cut.
- `nvcc` in the Kaggle image.
- PTX JIT time for the 12.8 binary.
- P2P / NCCL on Kaggle.
- Whether quota is charged per session or per device.
- Whether Kaggle accepts the benchmark as personal use.
