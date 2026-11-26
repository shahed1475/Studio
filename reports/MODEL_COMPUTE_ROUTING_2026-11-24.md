# Model and compute routing: inventory, hardware, compatibility, Kaggle, architecture, tests (24 Nov 2026)

Owner's mission (24 Nov 2026): make the models already downloaded usable across this PC, a VPS and eligible Kaggle GPUs, with free APIs kept separate.
All code is uncommitted in ~/studio. Nothing was downloaded, uploaded, pushed, deployed or paid. The forbidden workshop folder was never scanned or read.
Two incidents, both harmless: (1) one Playwright page load wrote two snapshot files of kaggle.com/terms into `.playwright-mcp/` of the session's starting
folder (the workshop); the tool was stopped and nothing there was read or changed. (2) Writing this report the first time, an unquoted shell heredoc ran the
backticked names in the text: it re-ran the read-only inventory, `ollama create` with no argument (refused, nothing created: Ollama still lists 33 models)
and opened and closed `view`; the report was then rewritten without a shell.

## 1. Existing downloaded models (read-only inventory)
- `python run.py compute inventory` (modelinventory.py): 118 entries in about 6 s, no read errors: 33 Ollama models (31 distinct blobs) and 85 file models.
  Kinds: 67 text LLMs, 3 vision LLMs, 33 LoRA adapters / training checkpoints, 5 image, 4 video, 4 text encoders, 2 VAEs.
- Sources: Ollama's API (/api/tags, /api/show), GGUF metadata headers, safetensors JSON headers; fingerprint = size + mtime + SHA-256 of the first MB.
  No model was copied. The full list with paths: data/compute/models.json (not in git).
- 16 Ollama models are built from the owner's own GGUF files (argon-planner x5, cyberexpert x7, hom-marketing / qwen-marketing, gemma4-agentic-tau2 x2): private, never uploaded.
- 58 runnable or pipeline entries have no licence recorded (mostly the owner's own files): unknown licences are refused for production.
- Parameter counts read from packed 4-bit tensors (U8/I8 dtype) are about half the true count (qwen36-35b shows 19.1B).

## 2. Hardware
| Environment | Measured 24 Nov 2026 |
|---|---|
| This PC GPU | NVIDIA GeForce GTX 1050 Ti, 4 GB, compute capability 6.1, driver 580.178.04, CUDA 13.0; about 1 GB held by the desktop and an Ollama runner, about 2.9 GB free |
| This PC CPU, RAM, disk | Intel i5-9500, 6 cores; 25 GB RAM, 9 to 12 GB available; 234 GB free on /home |
| Inference services | Ollama 0.34.4 on 127.0.0.1:11434 (33 models) |
| VPS | none: Hostinger deleted it on 17 Nov 2026; Tailscale node vps-ai offline 7 days, port 22 closed; tunnel port 11436 answers nothing; the container ollama-relay restart-loops (366 restarts, cannot bind 172.18.0.1:11434) |
| Kaggle | account authenticated (CLI 2.2.5 listed 5 of the owner's notebooks, no GPU used); 2 x T4 seen in a session on 23 Nov; 30 h a week (account page, 23 Nov); 12 h sessions and RAM: unverified |

## 3. Compatibility matrix
Estimates at 4,096 tokens of context: weights + KV cache + engine overhead, against live free memory (Kaggle: its spec, not live).

| Model | Kind | Size GB | Params | Quant | Licence | PC GPU | PC CPU | VPS | Kaggle GPU (spec) |
|---|---|---|---|---|---|---|---|---|---|
| deepseek-v4-flash-reap | llm | 84.69 | 83.2B | I8 | mit | too big | too big | n/a | too big |
| qwen36-35b | llm | 23.29 | 19.1B | U8 | apache-2.0 | too big | too big | n/a | fits |
| qwen3-coder-30b | llm | 19.62 | 16.5B | U8 | apache-2.0 | too big | too big | n/a | fits |
| Qwen Marketing | llm | 16.39 | ? | BF16 | mit | too big | too big | n/a | fits |
| original | llm | 16.38 | 8.2B | BF16 | mit | too big | too big | n/a | fits |
| qwen_3_4b | llm | 8.04 | 4.0B | BF16 | unknown | import first | too big | n/a | fits |
| gemma4-heretic-32k:latest | llm | 7.38 | 11.9B | Q4_K_M | unknown | offload | too big | n/a | fits |
| gemma4-agentic-tau2-heretic:latest | llm | 7.38 | 11.9B | Q4_K_M | unknown | offload | too big | n/a | fits |
| gemma4-agentic-tau2:latest | llm | 7.38 | 11.9B | Q4_K_M | unknown | offload | too big | n/a | fits |
| Gemma 4 12B Agentic Fable5 Composer2.5 v2 3.5x | llm | 7.38 | ? | Q4_K_M | unknown | import first | too big | n/a | fits |
| cognitivecomputations/dolphin-mistral-nemo:12b | llm | 7.07 | 12.2B | Q4_0 | unknown | offload | fits | n/a | fits |
| deepseek-r1:8b | llm | 5.23 | 8.2B | Q4_K_M | MIT License | offload | fits | n/a | fits |
| qwen3-8b-16k:latest | llm | 5.23 | 8.2B | Q4_K_M | Apache License | offload | fits | n/a | fits |
| qwen3:8b | llm | 5.23 | 8.2B | Q4_K_M | Apache License | offload | fits | n/a | fits |
| hom-marketing:latest | llm | 5.03 | 8.2B | Q4_K_M | Apache License | offload | fits | n/a | fits |
| Qwen Marketing | llm | 5.03 | ? | Q4_K_M | mit | import first | import first | n/a | fits |
| dolphin3:latest | llm | 4.92 | 8.0B | Q4_K_M | LLAMA 3.1 COMMUNITY LICE | offload | fits | n/a | fits |
| huihui_ai/qwen2.5-coder-abliterate:7b | llm | 4.68 | 7.6B | Q4_K_M | Apache License | offload | fits | n/a | fits |
| qwen2.5-coder:7b | llm | 4.68 | 7.6B | Q4_K_M | Apache License | offload | fits | n/a | fits |
| hf.co/mradermacher/deepseek-coder-7b-instruct- | llm | 4.22 | 6.9B | Q4_K_M | unknown | offload | fits | n/a | fits |
| cyberexpert-merged | llm | 3.09 | 1.5B | F16 | unknown | import first | import first | n/a | fits |
| cyberexpert-merged-v2 | llm | 3.09 | 1.5B | F16 | unknown | import first | import first | n/a | fits |
| cyberexpert-merged-v3 | llm | 3.09 | 1.5B | F16 | unknown | import first | import first | n/a | fits |
| cyberexpert-merged-v4 | llm | 3.09 | 1.5B | F16 | unknown | import first | import first | n/a | fits |
| cyberexpert-merged-v5 | llm | 3.09 | 1.5B | F16 | unknown | import first | import first | n/a | fits |
| cyberexpert-merged-v6 | llm | 3.09 | 1.5B | F16 | unknown | import first | import first | n/a | fits |
| cyberexpert-merged-v7 | llm | 3.09 | 1.5B | F16 | unknown | import first | import first | n/a | fits |
| Cyberexpert Merged | llm | 3.09 | ? | F16 | unknown | import first | import first | n/a | fits |
| Cyberexpert Merged v2 | llm | 3.09 | ? | F16 | unknown | import first | import first | n/a | fits |
| Cyberexpert Merged v3 | llm | 3.09 | ? | F16 | unknown | import first | import first | n/a | fits |
| Cyberexpert Merged v4 | llm | 3.09 | ? | F16 | unknown | import first | import first | n/a | fits |
| Cyberexpert Merged v5 | llm | 3.09 | ? | F16 | unknown | import first | import first | n/a | fits |
| Cyberexpert Merged v6 | llm | 3.09 | ? | F16 | unknown | import first | import first | n/a | fits |
| Cyberexpert Merged v7 | llm | 3.09 | ? | F16 | unknown | import first | import first | n/a | fits |
| Merged | llm | 3.09 | ? | F16 | unknown | import first | import first | n/a | fits |
| merged | llm | 3.09 | 1.5B | BF16 | unknown | import first | import first | n/a | fits |
| hf.co/DavidAU/LFM2.5-2.6B-Qwen3.8-Turbo-Brilli | llm | 2.53 | 2.7B | Q6_K | unknown | offload | fits | n/a | fits |
| Qwen3-4B-Instruct-2507 | llm | 2.5 | ? | Q4_K_M | apache-2.0 | import first | import first | n/a | fits |
| Qwen3-4B-Instruct-2507 | llm | 2.5 | ? | Q4_K_M | apache-2.0 | import first | import first | n/a | fits |
| hf.co/UnfilteredAI/NSFW-flash:Q4_K_M | llm | 1.38 | 2.2B | Q4_K_M | unknown | offload | fits | n/a | fits |
| qwen3:1.7b | llm | 1.36 | 2.0B | Q4_K_M | Apache License | fits | fits | n/a | fits |
| argon-planner:latest | llm | 0.99 | 1.5B | Q4_K_M | Apache License | fits | fits | n/a | fits |
| argon-planner-v3:latest | llm | 0.99 | 1.5B | Q4_K_M | Apache License | fits | fits | n/a | fits |
| argon-planner-v2:latest | llm | 0.99 | 1.5B | Q4_K_M | Apache License | fits | fits | n/a | fits |
| argon-planner-v1:latest | llm | 0.99 | 1.5B | Q4_K_M | Apache License | fits | fits | n/a | fits |
| argon-operator:latest | llm | 0.99 | 1.5B | Q4_K_M | Apache License | fits | fits | n/a | fits |
| qwen2.5:1.5b | llm | 0.99 | 1.5B | Q4_K_M | Apache License | fits | fits | n/a | fits |
| cyberexpert-v7:latest | llm | 0.99 | 1.5B | Q4_K_M | unknown | fits | fits | n/a | fits |
| cyberexpert-v6:latest | llm | 0.99 | 1.5B | Q4_K_M | unknown | fits | fits | n/a | fits |
| cyberexpert-v5:latest | llm | 0.99 | 1.5B | Q4_K_M | unknown | fits | fits | n/a | fits |
| cyberexpert-v4:latest | llm | 0.99 | 1.5B | Q4_K_M | unknown | fits | fits | n/a | fits |
| cyberexpert-v3:latest | llm | 0.99 | 1.5B | Q4_K_M | unknown | fits | fits | n/a | fits |
| cyberexpert-v2:latest | llm | 0.99 | 1.5B | Q4_K_M | unknown | fits | fits | n/a | fits |
| cyberexpert:latest | llm | 0.99 | 1.5B | Q4_K_M | unknown | fits | fits | n/a | fits |
| Cyberexpert Merged | llm | 0.99 | ? | Q4_K_M | unknown | import first | import first | n/a | fits |
| Cyberexpert Merged v2 | llm | 0.99 | ? | Q4_K_M | unknown | import first | import first | n/a | fits |
| Cyberexpert Merged v3 | llm | 0.99 | ? | Q4_K_M | unknown | import first | import first | n/a | fits |
| Cyberexpert Merged v4 | llm | 0.99 | ? | Q4_K_M | unknown | import first | import first | n/a | fits |
| Cyberexpert Merged v5 | llm | 0.99 | ? | Q4_K_M | unknown | import first | import first | n/a | fits |
| Cyberexpert Merged v6 | llm | 0.99 | ? | Q4_K_M | unknown | import first | import first | n/a | fits |
| Cyberexpert Merged v7 | llm | 0.99 | ? | Q4_K_M | unknown | import first | import first | n/a | fits |
| Merged | llm | 0.99 | ? | Q4_K_M | unknown | import first | import first | n/a | fits |
| ae (1) | llm | 0.34 | 0.1B | F32 | unknown | import first | import first | n/a | fits |
| ae | llm | 0.34 | 0.1B | F32 | unknown | import first | import first | n/a | fits |
| ae | llm | 0.34 | 0.1B | F32 | unknown | import first | import first | n/a | fits |
| qwen2.5vl-3b-cpu:latest | vision-llm | 3.2 | 3.8B | Q4_K_M | Apache License | offload | fits | n/a | fits |
| qwen2.5vl-3b-16k:latest | vision-llm | 3.2 | 3.8B | Q4_K_M | Apache License | offload | fits | n/a | fits |
| qwen2.5vl:3b | vision-llm | 3.2 | 3.8B | Q4_K_M | Apache License | offload | fits | n/a | fits |
| transformer | image | 14.23 | 7.1B | BF16 | unknown | not alone | not alone | n/a | not alone |
| flux1-schnell-Q2_K | image | 4.01 | ? | Q2_K | unknown | not alone | not alone | n/a | not alone |
| z_image_turbo-Q4_K | image | 3.86 | ? | ? | unknown | not alone | not alone | n/a | not alone |
| z_image_turbo-Q3_K | image | 3.14 | ? | ? | unknown | not alone | not alone | n/a | not alone |
| Realistic_Vision_V6.0_NV_B1_fp16 | image | 2.13 | 1.1B | F16 | unknown | not alone | not alone | n/a | not alone |
| text_encoder | text-encoder | 17.53 | 8.8B | BF16 | unknown | not alone | not alone | n/a | not alone |
| t5xxl_fp8_e4m3fn_scaled | text-encoder | 5.16 | 4.9B | F8_E4M3 | unknown | not alone | not alone | n/a | not alone |
| T5 V1_1 Xxl | text-encoder | 2.9 | ? | Q4_K_M | unknown | not alone | not alone | n/a | not alone |
| clip_l | text-encoder | 0.25 | 0.1B | F16 | unknown | not alone | not alone | n/a | not alone |
| vae | vae | 1.35 | 0.3B | F32 | unknown | not alone | not alone | n/a | not alone |
| ae | vae | 0.34 | 0.1B | F32 | unknown | not alone | not alone | n/a | not alone |
| ltxv-2b-0.9.8-distilled-fp8 | video | 4.46 | 3.2B | F8_E4M3 | unknown | not alone | not alone | n/a | not alone |
| Umt5 Xxl | video | 3.66 | ? | Q4_K_M | unknown | not alone | not alone | n/a | not alone |
| Wan2.2-TI2V-5B-Q4_K_M | video | 3.43 | ? | Q4_K_M | unknown | not alone | not alone | n/a | not alone |
| Wan2.2_VAE | video | 1.41 | 0.7B | F16 | unknown | not alone | not alone | n/a | not alone |

33 LoRA adapters and training checkpoints are listed in data/compute/models.json and never run alone.

Legend: fits; offload = runs on the GPU with the rest on the CPU (slower); import first = a GGUF file not yet in Ollama (`ollama create` from it, nothing downloaded) or safetensors that need PyTorch, which this PC's studio lacks; not alone = part of another pipeline; n/a = no such environment.

## 4. Kaggle research and eligibility
- Terms of Use (version 22 Jun 2025, read in the browser on 23 Nov 2026): "You will only use the Services for your own internal, personal, non-commercial use, and not on behalf of or for the benefit of any third party." Not re-read today: the pages render by JavaScript (a plain fetch returned only titles) and the browser tool was stopped (see top).
- In code: every Kaggle job is BLOCKED_PENDING_TERMS_REVIEW until the owner lists a permitted task (`owner_permitted_tasks` in config/compute.json); production data, voice, unpublished video and private models are BLOCKED for Kaggle whatever the list says; the Kaggle worker is switched off (`enabled: false`).
- Worker design: finite sessions (no keep-alive, no second account); a private kernel package that loads a PUBLIC Hugging Face model by id (nothing uploaded from this PC, no credential inside); results.jsonl is the checkpoint; an expired or cancelled session becomes INTERRUPTED, then RECOVERY_PENDING, then a new package that skips the finished ids.

## 5. Compute routing architecture
modelinventory.py (what exists) -> computecompat.py (what fits where: `need` and `verdict` against nvidia-smi and /proc/meminfo) -> `computerouter.route` (which model: capability, content policy, licence, unchanged file, minimum size; where: paid compute refused, memory fit, busy GPU skipped, Kaggle gate, session start against the latency limit; ranked by preference, parameters and measured speed class) -> computejobs.py (job id = hash of model, task, input, parameters and environment; statuses QUEUED to RECOVERY_PENDING with only allowed moves; atomic files; credentials refused) -> adapters (Ollama on this PC GPU and CPU: real; Kaggle: prepare, submit, status; VPS: none) -> data/compute/outputs (hashed).
Commands: `python run.py compute inventory`, `compute matrix`, `compute route production`, `compute smoke`, `compute recover`, `compute view`. Dashboard: /compute and /api/compute (owner's studio only; a user studio gets 404); live after a dashboard restart.

## 6. Provider routing architecture (separate from compute)
API providers stay in llm.py and judges.py (not rewritten). Judges: Google direct, the owner's FreeLLMAPI, OpenRouter free models, then the judges that share the Cloudflare picture account (GLM, Qwen) last, and never while Cloudflare says the account's day is spent (its 429 answer, code 4006, recorded in data/cloudflare_account_spent.json). Paid models only when switched on in Settings. `computerouter.providers_view` reports this without keys. Not done: Groq and Cerebras (no keys configured; their free tiers not verified; nothing added).

## 7. Skills created
.claude/skills/: model-inventory-manager, gpu-model-compatibility, intelligent-compute-routing, remote-model-execution, model-checkpoint-recovery, kaggle-gpu-worker, free-api-provider-routing, model-resource-monitor, model-routing-testing, model-license-and-data-policy. Each is tested for the skill format (tests/test_skills.py) and that every file and function it names exists (tests/test_compute_routing.py). The runtime is the code above; the skills tell a session how to use it.

## 8. Tests
tests/test_compute_routing.py (fakes only: no Kaggle hour, no API request): no GPU, insufficient VRAM, a model smaller than the GPU that still does not fit, a half-downloaded GGUF, a changed file (hash mismatch), the forbidden folder, duplicate jobs, credentials in a job, a job resumed from its checkpoint without repeating items, a power cut mid-job, an empty answer, licences (whole-word matching), content policy, Kaggle off, Kaggle terms, production data and private models never to Kaggle, a paid environment, a busy GPU, an expired notebook session, the Cloudflare 4006 limit, the dashboard route and a user studio. agenteval case `case_the_compute_router_never_sends_production_or_private_work_to_kaggle_and_never_pays` with 3 mutation checks. Full suite after the review fixes: 3,084 passed, 11 skipped, 0 failed (308 s).

## 9. Real smoke tests (24 Nov 2026, this PC only)
| Environment | Model | Result | Evidence (Ollama's /api/ps) |
|---|---|---|---|
| This PC GPU | qwen2.5:1.5b | COMPLETED "Paris.", 49 to 51 tokens/s, load 3.4 s | 1.06 of 1.06 GB in VRAM |
| This PC CPU | qwen2.5:1.5b | COMPLETED "Paris.", 26.3 tokens/s | 0 GB in VRAM |
| This PC GPU with CPU offload | qwen2.5-coder:7b | COMPLETED "ready", 10.3 tokens/s, load 8 s | 1.94 of 4.91 GB in VRAM |
| VPS | none | NOT RUN: no VPS exists | |
| Kaggle GPU | none | NOT RUN: BLOCKED_PENDING_TERMS_REVIEW (no GPU hour spent) | |

## 10. Remaining blockers and owner decisions
1. Kaggle: decide whether any task is permitted under its non-commercial terms (recommendation: none for the channel); only then add it to owner_permitted_tasks and switch the worker on.
2. VPS: none. The ollama-relay container restart-loops on a dead address, and the ollama-vps and story-studio-rw MCP entries point to the deleted VPS (owner's cleanup).
3. 32 models need `ollama create` (GGUF files) or PyTorch (safetensors) before they run here: the owner chooses which.
4. Licences: unknown for 58 entries, mostly the owner's own fine-tunes (they inherit their base model's licence): check before production use.
5. The dashboard page is live only after a dashboard restart (owner's yes).
6. Two Playwright snapshot files in the workshop's .playwright-mcp/ (kaggle.com/terms): the owner may delete them.

## 11. Independent review (read-only subagent) and fixes
Found: research and non-commercial licences passing (e.g. "Qwen RESEARCH LICENSE"), the Kaggle gate letting an unmarked data class through, submit trusting a caller's request, an input path escape (a sibling folder, settings.json), Ollama models public by default, header readers crashing the inventory, recovery able to take over a live job, the Kaggle fit measured on the local Q4 file instead of fp16, INTERRUPTED vs FAILED chosen by message text, the browser receiving prompts, answers and paths. All fixed with tests (tests/test_compute_routing.py, review section). Not fixed: per-GPU parsing beyond the first card; ranking prefers size over speed; fetching a Kaggle session's partial results back (not built: Kaggle stays blocked).
