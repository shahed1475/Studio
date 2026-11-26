# Downloaded model inventory (24 Nov 2026)

Read-only. Source: the studio's model registry `data/compute/models.json` (written by `modelinventory.py`, `python run.py compute inventory`, on 24 Nov 2026 04:31 UTC: Ollama through its API, GGUF and safetensors files by their headers only, never opened beyond the header, never copied). The forbidden Desktop workshop is in `never_scan` and was not read. Fit verdicts are the live `python run.py compute matrix` of 24 Nov 2026 ~16:45 UTC, **measured while Z-Image was using the GPU** (so even 1 GB models show `fits_with_cpu_offload` on the GPU; with the GPU idle, models under ~3 GB fit whole: qwen2.5:1.5b ran fully in VRAM at 49 tokens/s this morning).

## Summary
- 118 entries, 411.5 GB on disk (duplicates counted once). By kind: {'llm': 67, 'vision-llm': 3, 'text-encoder': 4, 'image': 5, 'vae': 2, 'lora-adapter': 33, 'video': 4}.
- Licence known for 27, unknown for 91 (mostly the owner's own fine-tunes and LoRA adapters, which inherit their base model's licence: check before any production use).
- Hardware (this PC): NVIDIA GTX 1050 Ti 4 GB (CUDA via Ollama and stable-diffusion.cpp), 23 GB RAM, 6 cores. No VPS exists (Hostinger deleted it on 17 Nov 2026). Kaggle: spec only (2 x T4 16 GB each), BLOCKED for this studio (see reports/SEVEN_SLEEPERS_COMPLETION_MISSION_2026-11-24.md).

## Verified today for channel use (licence proven by file fingerprint)
| File (~/tools/sdcpp/models) | SHA-256 (first 16) | Matches | Licence |
|---|---|---|---|
| z_image_turbo-Q3_K.gguf (3.14 GB) | 4b44bdaa7814f20d | leejet/Z-Image-Turbo-GGUF (base Tongyi-MAI/Z-Image-Turbo) | Apache-2.0 (both repos' Hugging Face cards) |
| Qwen3-4B-Instruct-2507-Q4_K_M.gguf (2.50 GB) | 3605803b982cb64a | unsloth/Qwen3-4B-Instruct-2507-GGUF (base Qwen/Qwen3-4B-Instruct-2507) | Apache-2.0 |
| ae.safetensors (0.34 GB, FLUX VAE) | afc8e28272cd15db | Comfy-Org/Z-Image-Turbo split_files/vae and second-state/FLUX.1-schnell-GGUF | Apache-2.0 |

These three run together as the studio's existing local picture route (`tools/zimage_batch.py`, stable-diffusion.cpp in ~/tools/sdcpp, `--offload-to-cpu`): measured earlier at about 312-340 s a 768x448 picture on this GPU.

## Full table
Columns: name, kind, format, architecture, parameters, quantization, size GB, context, licence (as recorded), engines, fit on this PC's GPU / CPU / Kaggle T4x2 (estimate from `computecompat.need`, never a promise), private (the owner's own file: never uploaded), location.

| Name | Kind | Format | Arch | Params | Quant | GB | Context | Licence | Engines | PC GPU | PC CPU | Kaggle (spec) | Private | Location |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| transformer | image | safetensors (Hugging Face folder) | ? | ? | BF16 | 14.23 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/colibri-models/qwen-image-2.1/transformer` |
| flux1-schnell-Q2_K | image | gguf | flux | ? | Q2_K | 4.01 | - | unknown | stable-diffusion.cpp, comfyui | not_runnable | not_runnable | not_runnable | yes | `~/tools/sdcpp/flux/flux1-schnell-Q2_K.gguf` |
| z_image_turbo-Q4_K | image | gguf | ? | ? | ? | 3.86 | - | unknown | stable-diffusion.cpp, comfyui | not_runnable | not_runnable | not_runnable | yes | `~/ai-models/zimage/z_image_turbo-Q4_K.gguf` |
| z_image_turbo-Q3_K | image | gguf | ? | ? | ? | 3.14 | - | unknown | stable-diffusion.cpp, comfyui | not_runnable | not_runnable | not_runnable | yes | `~/tools/sdcpp/models/z_image_turbo-Q3_K.gguf` |
| Realistic_Vision_V6.0_NV_B1_fp16 | image | safetensors | ? | ? | F16 | 2.13 | - | unknown | comfyui | not_runnable | not_runnable | not_runnable | yes | `~/ComfyUI/models/checkpoints/Realistic_Vision_V6.0_NV_B1_fp16.safetensors` |
| deepseek-v4-flash-reap | llm | safetensors (Hugging Face folder) | DeepseekV4ForCausalLM | ? | I8 | 84.69 | 1048576 | mit | transformers | too_big | too_big | too_big | yes | `~/colibri-models/deepseek-v4-flash-reap` |
| qwen36-35b | llm | safetensors (Hugging Face folder) | qwen3_5_moe_text | ? | U8 | 23.29 | 262144 | apache-2.0 | transformers | too_big | too_big | too_big | yes | `~/colibri-models/qwen36-35b` |
| qwen3-coder-30b | llm | safetensors (Hugging Face folder) | Qwen3MoeForCausalLM | ? | U8 | 19.62 | 262144 | apache-2.0 | transformers | too_big | too_big | too_big | yes | `~/colibri-models/qwen3-coder-30b` |
| Qwen Marketing | llm | gguf | qwen3 | ? | BF16 | 16.39 | 40960 | mit | ollama, llama.cpp | needs_import | needs_import | fits | yes | `~/gguf-work/qwen-marketing-bf16.gguf` |
| original | llm | safetensors (Hugging Face folder) | Qwen3ForCausalLM | ? | BF16 | 16.38 | 40960 | mit | transformers | too_big | too_big | fits | yes | `~/DevAI-models/Qwen-Marketing/original` |
| qwen_3_4b | llm | safetensors | ? | ? | BF16 | 8.04 | - | unknown | transformers | too_big | too_big | fits | yes | `~/Downloads/qwen_3_4b.safetensors` |
| gemma4-heretic-32k:latest | llm | gguf | gemma4 | 11.9B | Q4_K_M | 7.38 | 262144 | unknown | ollama | too_big | too_big | too_big | yes | `ollama store` |
| gemma4-agentic-tau2-heretic:latest | llm | gguf | gemma4 | 11.9B | Q4_K_M | 7.38 | 262144 | unknown | ollama | too_big | too_big | too_big | yes | `ollama store` |
| Gemma 4 12B Agentic Fable5 Composer2.5 v2 3.5x Tau2 Uncensored Heretic | llm | gguf | gemma4 | ? | Q4_K_M | 7.38 | 262144 | unknown | ollama, llama.cpp | ? | ? | ? | yes | `~/gemma4-model/gemma4-agentic-tau2-heretic.gguf` |
| gemma4-agentic-tau2:latest | llm | gguf | gemma4 | 11.9B | Q4_K_M | 7.38 | 262144 | unknown | ollama | too_big | too_big | too_big | yes | `ollama store` |
| cognitivecomputations/dolphin-mistral-nemo:12b | llm | gguf | llama | 12.2B | Q4_0 | 7.07 | 1024000 | unknown | ollama | ? | ? | ? | yes | `ollama store` |
| qwen3:8b | llm | gguf | qwen3 | 8.2B | Q4_K_M | 5.23 | 40960 | Apache License | ollama | fits_with_cpu_offload | fits | fits | yes | `ollama store` |
| qwen3-8b-16k:latest | llm | gguf | qwen3 | 8.2B | Q4_K_M | 5.23 | 40960 | Apache License | ollama | fits_with_cpu_offload | fits | fits | yes | `ollama store` |
| deepseek-r1:8b | llm | gguf | qwen3 | 8.2B | Q4_K_M | 5.23 | 131072 | MIT License | ollama | fits_with_cpu_offload | fits | fits | yes | `ollama store` |
| hom-marketing:latest | llm | gguf | qwen3 | 8.2B | Q4_K_M | 5.03 | 40960 | Apache License | ollama | fits_with_cpu_offload | fits | fits | yes | `ollama store` |
| qwen-marketing:latest | llm | gguf | qwen3 | 8.2B | Q4_K_M | 5.03 | 40960 | Apache License | ollama | ? | ? | ? | yes | `ollama store` |
| Qwen Marketing | llm | gguf | qwen3 | ? | Q4_K_M | 5.03 | 40960 | mit | ollama, llama.cpp | needs_import | needs_import | fits | yes | `~/gguf-work/qwen-marketing-Q4_K_M.gguf` |
| dolphin3:latest | llm | gguf | llama | 8.0B | Q4_K_M | 4.92 | 131072 | LLAMA 3.1 COMMUNITY LICENSE AGREEMENT | ollama | fits_with_cpu_offload | fits | fits | yes | `ollama store` |
| huihui_ai/qwen2.5-coder-abliterate:7b | llm | gguf | qwen2 | 7.6B | Q4_K_M | 4.68 | 32768 | Apache License | ollama | fits_with_cpu_offload | fits | fits | yes | `ollama store` |
| qwen2.5-coder:7b | llm | gguf | qwen2 | 7.6B | Q4_K_M | 4.68 | 32768 | Apache License | ollama | fits_with_cpu_offload | fits | fits | yes | `ollama store` |
| hf.co/mradermacher/deepseek-coder-7b-instruct-v1.5-GGUF:Q4_K_M | llm | gguf | llama | 6.91B | Q4_K_M | 4.22 | 4096 | unknown | ollama | ? | ? | ? | yes | `ollama store` |
| Cyberexpert Merged v2 | llm | gguf | qwen2 | ? | F16 | 3.09 | 32768 | unknown | ollama, llama.cpp | needs_import | needs_import | fits | yes | `~/cyberexpert-gguf/cyberexpert-v2-f16.gguf` |
| Cyberexpert Merged v3 | llm | gguf | qwen2 | ? | F16 | 3.09 | 32768 | unknown | ollama, llama.cpp | needs_import | needs_import | fits | yes | `~/cyberexpert-gguf/cyberexpert-v3-f16.gguf` |
| Cyberexpert Merged v4 | llm | gguf | qwen2 | ? | F16 | 3.09 | 32768 | unknown | ollama, llama.cpp | needs_import | needs_import | fits | yes | `~/cyberexpert-gguf/cyberexpert-v4-f16.gguf` |
| Cyberexpert Merged v5 | llm | gguf | qwen2 | ? | F16 | 3.09 | 32768 | unknown | ollama, llama.cpp | needs_import | needs_import | fits | yes | `~/cyberexpert-gguf/cyberexpert-v5-f16.gguf` |
| Cyberexpert Merged v6 | llm | gguf | qwen2 | ? | F16 | 3.09 | 32768 | unknown | ollama, llama.cpp | needs_import | needs_import | fits | yes | `~/cyberexpert-gguf/cyberexpert-v6-f16.gguf` |
| Cyberexpert Merged v7 | llm | gguf | qwen2 | ? | F16 | 3.09 | 32768 | unknown | ollama, llama.cpp | needs_import | needs_import | fits | yes | `~/cyberexpert-gguf/cyberexpert-v7-f16.gguf` |
| Cyberexpert Merged | llm | gguf | qwen2 | ? | F16 | 3.09 | 32768 | unknown | ollama, llama.cpp | needs_import | needs_import | fits | yes | `~/cyberexpert-gguf/cyberexpert-f16.gguf` |
| Merged | llm | gguf | qwen2 | ? | F16 | 3.09 | 32768 | unknown | ollama, llama.cpp | not_runnable | not_runnable | not_runnable | yes | `~/.argon-train/out/argon-planner-f16.gguf` |
| merged | llm | safetensors (Hugging Face folder) | Qwen2ForCausalLM | ? | BF16 | 3.09 | 32768 | unknown | transformers | needs_import | needs_import | fits | yes | `~/.argon-train/out/merged` |
| cyberexpert-merged | llm | safetensors (Hugging Face folder) | Qwen2ForCausalLM | ? | F16 | 3.09 | 32768 | unknown | transformers | needs_import | needs_import | fits | yes | `~/Downloads/Local model fine tune data/1part of data set/cyberexpert-merged` |
| cyberexpert-merged-v2 | llm | safetensors (Hugging Face folder) | Qwen2ForCausalLM | ? | F16 | 3.09 | 32768 | unknown | transformers | needs_import | needs_import | fits | yes | `~/Downloads/Local model fine tune data/1part of data set/cyberexpert-merged-v2` |
| cyberexpert-merged-v3 | llm | safetensors (Hugging Face folder) | Qwen2ForCausalLM | ? | F16 | 3.09 | 32768 | unknown | transformers | needs_import | needs_import | fits | yes | `~/Downloads/Local model fine tune data/1part of data set/cyberexpert-merged-v3` |
| cyberexpert-merged-v4 | llm | safetensors (Hugging Face folder) | Qwen2ForCausalLM | ? | F16 | 3.09 | 32768 | unknown | transformers | needs_import | needs_import | fits | yes | `~/Downloads/Local model fine tune data/1part of data set/cyberexpert-merged-v4` |
| cyberexpert-merged-v5 | llm | safetensors (Hugging Face folder) | Qwen2ForCausalLM | ? | F16 | 3.09 | 32768 | unknown | transformers | needs_import | needs_import | fits | yes | `~/Downloads/Local model fine tune data/1part of data set/cyberexpert-merged-v5` |
| cyberexpert-merged-v6 | llm | safetensors (Hugging Face folder) | Qwen2ForCausalLM | ? | F16 | 3.09 | 32768 | unknown | transformers | needs_import | needs_import | fits | yes | `~/Downloads/Local model fine tune data/1part of data set/cyberexpert-merged-v6` |
| cyberexpert-merged-v7 | llm | safetensors (Hugging Face folder) | Qwen2ForCausalLM | ? | F16 | 3.09 | 32768 | unknown | transformers | needs_import | needs_import | fits | yes | `~/Downloads/Local model fine tune data/1part of data set/cyberexpert-merged-v7` |
| hf.co/DavidAU/LFM2.5-2.6B-Qwen3.8-Turbo-Brilliance-Power-X12-NEO-MAX-GGUF:Q6_K | llm | gguf | lfm2 | 2.7B | Q6_K | 2.53 | 131072 | unknown | ollama | ? | ? | ? | yes | `ollama store` |
| Qwen3-4B-Instruct-2507 | llm | gguf | qwen3 | ? | Q4_K_M | 2.50 | 262144 | apache-2.0 | ollama, llama.cpp | needs_import | needs_import | fits | yes | `~/ai-models/zimage/Qwen3-4B-Instruct-2507-Q4_K_M.gguf` |
| Qwen3-4B-Instruct-2507 | llm | gguf | qwen3 | ? | Q4_K_M | 2.50 | 262144 | apache-2.0 | ollama, llama.cpp | needs_import | needs_import | fits | yes | `~/tools/sdcpp/models/Qwen3-4B-Instruct-2507-Q4_K_M.gguf` |
| hf.co/UnfilteredAI/NSFW-flash:Q4_K_M | llm | gguf | stablelm | 2.24B | Q4_K_M | 1.38 | 4096 | unknown | ollama | fits_with_cpu_offload | fits | fits | yes | `ollama store` |
| qwen3:1.7b | llm | gguf | qwen3 | 2.0B | Q4_K_M | 1.36 | 40960 | Apache License | ollama | fits_with_cpu_offload | fits | fits | yes | `ollama store` |
| argon-operator:latest | llm | gguf | qwen2 | 1.5B | Q4_K_M | 0.99 | 32768 | Apache License | ollama | fits_with_cpu_offload | fits | fits | yes | `ollama store` |
| qwen2.5:1.5b | llm | gguf | qwen2 | 1.5B | Q4_K_M | 0.99 | 32768 | Apache License | ollama | fits_with_cpu_offload | fits | fits | yes | `ollama store` |
| argon-planner:latest | llm | gguf | qwen2 | 1.5B | Q4_K_M | 0.99 | 32768 | Apache License | ollama | fits_with_cpu_offload | fits | fits | yes | `ollama store` |
| argon-planner-v3:latest | llm | gguf | qwen2 | 1.5B | Q4_K_M | 0.99 | 32768 | Apache License | ollama | fits_with_cpu_offload | fits | fits | yes | `ollama store` |
| argon-planner-next:latest | llm | gguf | qwen2 | 1.5B | Q4_K_M | 0.99 | 32768 | Apache License | ollama | ? | ? | ? | yes | `ollama store` |
| argon-planner-v2:latest | llm | gguf | qwen2 | 1.5B | Q4_K_M | 0.99 | 32768 | Apache License | ollama | fits_with_cpu_offload | fits | fits | yes | `ollama store` |
| argon-planner-v1:latest | llm | gguf | qwen2 | 1.5B | Q4_K_M | 0.99 | 32768 | Apache License | ollama | fits_with_cpu_offload | fits | fits | yes | `ollama store` |
| cyberexpert-v7:latest | llm | gguf | qwen2 | 1.5B | Q4_K_M | 0.99 | 32768 | unknown | ollama | fits_with_cpu_offload | fits | fits | yes | `ollama store` |
| cyberexpert-v6:latest | llm | gguf | qwen2 | 1.5B | Q4_K_M | 0.99 | 32768 | unknown | ollama | fits_with_cpu_offload | fits | fits | yes | `ollama store` |
| cyberexpert-v5:latest | llm | gguf | qwen2 | 1.5B | Q4_K_M | 0.99 | 32768 | unknown | ollama | fits_with_cpu_offload | fits | fits | yes | `ollama store` |
| cyberexpert-v4:latest | llm | gguf | qwen2 | 1.5B | Q4_K_M | 0.99 | 32768 | unknown | ollama | fits_with_cpu_offload | fits | fits | yes | `ollama store` |
| cyberexpert-v3:latest | llm | gguf | qwen2 | 1.5B | Q4_K_M | 0.99 | 32768 | unknown | ollama | fits_with_cpu_offload | fits | fits | yes | `ollama store` |
| cyberexpert-v2:latest | llm | gguf | qwen2 | 1.5B | Q4_K_M | 0.99 | 32768 | unknown | ollama | fits_with_cpu_offload | fits | fits | yes | `ollama store` |
| cyberexpert:latest | llm | gguf | qwen2 | 1.5B | Q4_K_M | 0.99 | 32768 | unknown | ollama | fits_with_cpu_offload | fits | fits | yes | `ollama store` |
| Cyberexpert Merged v2 | llm | gguf | qwen2 | ? | Q4_K_M | 0.99 | 32768 | unknown | ollama, llama.cpp | needs_import | needs_import | fits | yes | `~/cyberexpert-gguf/cyberexpert-v2-q4.gguf` |
| Cyberexpert Merged v3 | llm | gguf | qwen2 | ? | Q4_K_M | 0.99 | 32768 | unknown | ollama, llama.cpp | needs_import | needs_import | fits | yes | `~/cyberexpert-gguf/cyberexpert-v3-q4.gguf` |
| Cyberexpert Merged v4 | llm | gguf | qwen2 | ? | Q4_K_M | 0.99 | 32768 | unknown | ollama, llama.cpp | needs_import | needs_import | fits | yes | `~/cyberexpert-gguf/cyberexpert-v4-q4.gguf` |
| Cyberexpert Merged v5 | llm | gguf | qwen2 | ? | Q4_K_M | 0.99 | 32768 | unknown | ollama, llama.cpp | needs_import | needs_import | fits | yes | `~/cyberexpert-gguf/cyberexpert-v5-q4.gguf` |
| Cyberexpert Merged v6 | llm | gguf | qwen2 | ? | Q4_K_M | 0.99 | 32768 | unknown | ollama, llama.cpp | needs_import | needs_import | fits | yes | `~/cyberexpert-gguf/cyberexpert-v6-q4.gguf` |
| Cyberexpert Merged v7 | llm | gguf | qwen2 | ? | Q4_K_M | 0.99 | 32768 | unknown | ollama, llama.cpp | needs_import | needs_import | fits | yes | `~/cyberexpert-gguf/cyberexpert-v7-q4.gguf` |
| Cyberexpert Merged | llm | gguf | qwen2 | ? | Q4_K_M | 0.99 | 32768 | unknown | ollama, llama.cpp | needs_import | needs_import | fits | yes | `~/cyberexpert-gguf/cyberexpert-q4.gguf` |
| Merged | llm | gguf | qwen2 | ? | Q4_K_M | 0.99 | 32768 | unknown | ollama, llama.cpp | not_runnable | not_runnable | not_runnable | yes | `~/.argon-train/out/argon-planner-q4km.gguf` |
| ae (1) | llm | safetensors | ? | ? | F32 | 0.34 | - | unknown | transformers | needs_import | needs_import | fits | yes | `~/Downloads/ae (1).safetensors` |
| ae | llm | safetensors | ? | ? | F32 | 0.34 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/ai-models/zimage/ae.safetensors` |
| ae | llm | safetensors | ? | ? | F32 | 0.34 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/tools/sdcpp/models/ae.safetensors` |
| Merged | lora-adapter | gguf | qwen2 | ? | Q4_K_M | 0.99 | 32768 | unknown | stable-diffusion.cpp, comfyui | not_runnable | not_runnable | not_runnable | yes | `~/.argon-train/out/hf_stage/argon-planner-q4_k_m.gguf` |
| adapter_model | lora-adapter | safetensors | ? | ? | F32 | 0.07 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/Downloads/Local model fine tune data/1part of data set/lora-cyberexpert/adapter_model.safetensors` |
| adapter_model | lora-adapter | safetensors | ? | ? | F32 | 0.07 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/Downloads/Local model fine tune data/1part of data set/lora-cyberexpert/checkpoint-9/adapter_model.safetensors` |
| adapter_model | lora-adapter | safetensors | ? | ? | F32 | 0.07 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/Downloads/Local model fine tune data/1part of data set/lora-cyberexpert/checkpoint-18/adapter_model.safetensors` |
| adapter_model | lora-adapter | safetensors | ? | ? | F32 | 0.07 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/Downloads/Local model fine tune data/1part of data set/lora-cyberexpert/checkpoint-27/adapter_model.safetensors` |
| adapter_model | lora-adapter | safetensors | ? | ? | F32 | 0.07 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/Downloads/Local model fine tune data/1part of data set/lora-cyberexpert-v2/adapter_model.safetensors` |
| adapter_model | lora-adapter | safetensors | ? | ? | F32 | 0.07 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/Downloads/Local model fine tune data/1part of data set/lora-cyberexpert-v2/checkpoint-44/adapter_model.safetensors` |
| adapter_model | lora-adapter | safetensors | ? | ? | F32 | 0.07 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/Downloads/Local model fine tune data/1part of data set/lora-cyberexpert-v2/checkpoint-88/adapter_model.safetensors` |
| adapter_model | lora-adapter | safetensors | ? | ? | F32 | 0.07 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/Downloads/Local model fine tune data/1part of data set/lora-cyberexpert-v2/checkpoint-132/adapter_model.safetensors` |
| adapter_model | lora-adapter | safetensors | ? | ? | F32 | 0.07 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/Downloads/Local model fine tune data/1part of data set/lora-cyberexpert-v3/adapter_model.safetensors` |
| adapter_model | lora-adapter | safetensors | ? | ? | F32 | 0.07 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/Downloads/Local model fine tune data/1part of data set/lora-cyberexpert-v3/checkpoint-83/adapter_model.safetensors` |
| adapter_model | lora-adapter | safetensors | ? | ? | F32 | 0.07 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/Downloads/Local model fine tune data/1part of data set/lora-cyberexpert-v3/checkpoint-166/adapter_model.safetensors` |
| adapter_model | lora-adapter | safetensors | ? | ? | F32 | 0.07 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/Downloads/Local model fine tune data/1part of data set/lora-cyberexpert-v3/checkpoint-249/adapter_model.safetensors` |
| adapter_model | lora-adapter | safetensors | ? | ? | F32 | 0.07 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/Downloads/Local model fine tune data/1part of data set/lora-cyberexpert-v4/adapter_model.safetensors` |
| adapter_model | lora-adapter | safetensors | ? | ? | F32 | 0.07 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/Downloads/Local model fine tune data/1part of data set/lora-cyberexpert-v4/checkpoint-120/adapter_model.safetensors` |
| adapter_model | lora-adapter | safetensors | ? | ? | F32 | 0.07 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/Downloads/Local model fine tune data/1part of data set/lora-cyberexpert-v4/checkpoint-240/adapter_model.safetensors` |
| adapter_model | lora-adapter | safetensors | ? | ? | F32 | 0.07 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/Downloads/Local model fine tune data/1part of data set/lora-cyberexpert-v4/checkpoint-360/adapter_model.safetensors` |
| adapter_model | lora-adapter | safetensors | ? | ? | F32 | 0.07 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/Downloads/Local model fine tune data/1part of data set/lora-cyberexpert-v5/adapter_model.safetensors` |
| adapter_model | lora-adapter | safetensors | ? | ? | F32 | 0.07 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/Downloads/Local model fine tune data/1part of data set/lora-cyberexpert-v5/checkpoint-196/adapter_model.safetensors` |
| adapter_model | lora-adapter | safetensors | ? | ? | F32 | 0.07 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/Downloads/Local model fine tune data/1part of data set/lora-cyberexpert-v5/checkpoint-392/adapter_model.safetensors` |
| adapter_model | lora-adapter | safetensors | ? | ? | F32 | 0.07 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/Downloads/Local model fine tune data/1part of data set/lora-cyberexpert-v5/checkpoint-588/adapter_model.safetensors` |
| adapter_model | lora-adapter | safetensors | ? | ? | F32 | 0.07 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/Downloads/Local model fine tune data/1part of data set/lora-cyberexpert-v6/adapter_model.safetensors` |
| adapter_model | lora-adapter | safetensors | ? | ? | F32 | 0.07 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/Downloads/Local model fine tune data/1part of data set/lora-cyberexpert-v6/checkpoint-216/adapter_model.safetensors` |
| adapter_model | lora-adapter | safetensors | ? | ? | F32 | 0.07 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/Downloads/Local model fine tune data/1part of data set/lora-cyberexpert-v6/checkpoint-432/adapter_model.safetensors` |
| adapter_model | lora-adapter | safetensors | ? | ? | F32 | 0.07 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/Downloads/Local model fine tune data/1part of data set/lora-cyberexpert-v6/checkpoint-648/adapter_model.safetensors` |
| adapter_model | lora-adapter | safetensors | ? | ? | F32 | 0.07 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/Downloads/Local model fine tune data/1part of data set/lora-cyberexpert-v7/adapter_model.safetensors` |
| adapter_model | lora-adapter | safetensors | ? | ? | F32 | 0.07 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/Downloads/Local model fine tune data/1part of data set/lora-cyberexpert-v7/checkpoint-226/adapter_model.safetensors` |
| adapter_model | lora-adapter | safetensors | ? | ? | F32 | 0.07 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/Downloads/Local model fine tune data/1part of data set/lora-cyberexpert-v7/checkpoint-452/adapter_model.safetensors` |
| adapter_model | lora-adapter | safetensors | ? | ? | F32 | 0.07 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/Downloads/Local model fine tune data/1part of data set/lora-cyberexpert-v7/checkpoint-678/adapter_model.safetensors` |
| adapter_model | lora-adapter | safetensors | ? | ? | F32 | 0.07 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/.argon-train/out/planner-lora/adapter_model.safetensors` |
| adapter_model | lora-adapter | safetensors | ? | ? | F32 | 0.07 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/.argon-train/out/planner-lora-v2/adapter_model.safetensors` |
| adapter_model | lora-adapter | safetensors | ? | ? | F32 | 0.07 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/.argon-train/out/planner-lora-v3/adapter_model.safetensors` |
| adapter_model | lora-adapter | safetensors | ? | ? | F32 | 0.07 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/.argon-train/out/hf_stage/adapter_model.safetensors` |
| text_encoder | text-encoder | safetensors (Hugging Face folder) | Qwen3VLForConditionalGeneration | ? | BF16 | 17.53 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/colibri-models/qwen-image-2.1/text_encoder` |
| t5xxl_fp8_e4m3fn_scaled | text-encoder | safetensors | ? | ? | F8_E4M3 | 5.16 | - | unknown | comfyui | not_runnable | not_runnable | not_runnable | yes | `~/AI_Video_Studio/ComfyUI/models/text_encoders/t5xxl_fp8_e4m3fn_scaled.safetensors` |
| T5 V1_1 Xxl | text-encoder | gguf | t5encoder | ? | Q4_K_M | 2.90 | 512 | unknown | stable-diffusion.cpp, comfyui | not_runnable | not_runnable | not_runnable | yes | `~/tools/sdcpp/flux/t5-v1_1-xxl-encoder-Q4_K_M.gguf` |
| clip_l | text-encoder | safetensors | ? | ? | F16 | 0.25 | - | unknown | comfyui | not_runnable | not_runnable | not_runnable | yes | `~/tools/sdcpp/flux/clip_l.safetensors` |
| vae | vae | safetensors (Hugging Face folder) | ? | ? | F32 | 1.35 | - | unknown | transformers | not_runnable | not_runnable | not_runnable | yes | `~/colibri-models/qwen-image-2.1/vae` |
| ae | vae | safetensors | ? | ? | F32 | 0.34 | - | unknown | comfyui | not_runnable | not_runnable | not_runnable | yes | `~/AI_Video_Studio/ComfyUI/models/vae/ae.safetensors` |
| ltxv-2b-0.9.8-distilled-fp8 | video | safetensors | ? | ? | F8_E4M3 | 4.46 | - | unknown | comfyui | not_runnable | not_runnable | not_runnable | yes | `~/AI_Video_Studio/ComfyUI/models/checkpoints/ltxv-2b-0.9.8-distilled-fp8.safetensors` |
| Umt5 Xxl | video | gguf | t5encoder | ? | Q4_K_M | 3.66 | 512 | unknown | stable-diffusion.cpp, comfyui | not_runnable | not_runnable | not_runnable | yes | `~/ai-models/wan22/umt5-xxl-encoder-Q4_K_M.gguf` |
| Wan2.2-TI2V-5B-Q4_K_M | video | gguf | wan | ? | Q4_K_M | 3.43 | - | unknown | stable-diffusion.cpp, comfyui | not_runnable | not_runnable | not_runnable | yes | `~/ai-models/wan22/Wan2.2-TI2V-5B-Q4_K_M.gguf` |
| Wan2.2_VAE | video | safetensors | ? | ? | F16 | 1.41 | - | unknown | comfyui | not_runnable | not_runnable | not_runnable | yes | `~/ai-models/wan22/Wan2.2_VAE.safetensors` |
| qwen2.5vl:3b | vision-llm | gguf | qwen25vl | 3.8B | Q4_K_M | 3.20 | 128000 | Apache License | ollama | fits_with_cpu_offload | fits | fits | yes | `ollama store` |
| qwen2.5vl-3b-cpu:latest | vision-llm | gguf | qwen25vl | 3.8B | Q4_K_M | 3.20 | 128000 | Apache License | ollama | fits_with_cpu_offload | fits | fits | yes | `ollama store` |
| qwen2.5vl-3b-16k:latest | vision-llm | gguf | qwen25vl | 3.8B | Q4_K_M | 3.20 | 128000 | Apache License | ollama | fits_with_cpu_offload | fits | fits | yes | `ollama store` |

## Notes
- `needs_import`: a GGUF not yet in Ollama (`ollama create` from the file, nothing downloaded) or safetensors that need PyTorch, which this PC's studio does not have.
- `not_runnable`: adapters, VAEs and text encoders never run alone; they are parts of a pipeline (the Z-Image route above uses one of each).
- Kaggle column is arithmetic against Kaggle's published T4x2 spec, not a test, and Kaggle stays blocked for channel work.
- Content policy: uncensored, abliterated or NSFW models in this list are never used for channel work (`computerouter`), whatever their fit.
