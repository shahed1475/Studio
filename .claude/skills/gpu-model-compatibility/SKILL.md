---
name: gpu-model-compatibility
description: "Use when deciding whether a model fits a GPU or CPU: VRAM and RAM estimates with the KV cache and engine overhead, CPU offload, quantization and which engine (Ollama, llama.cpp, transformers) can load it."
---

# Gpu model compatibility (Story Studio)

Estimates, never a fit because a file is smaller than the GPU.

- `computecompat.need`: weights + KV cache (2 x layers x KV heads x head size x context x 2 bytes) + overhead (GPU about 0.45 GB + 6% of the weights). Without layer data the KV cache is 15% of the weights and marked as a guess.
- `computecompat.verdict` per environment: `fits`, `fits_with_cpu_offload` (Ollama keeps the rest on the CPU), `too_big`, `needs_import` (a GGUF not in Ollama yet, or safetensors without PyTorch here), `not_runnable` (adapters, VAEs, text encoders), `not_configured`.
- Live numbers only: `computecompat.gpu_status` (nvidia-smi) and `computecompat.ram_status`. Kaggle uses its spec from `config/compute.json`, labelled as spec.
- Measured on 24 Nov 2026 (GTX 1050 Ti, 4 GB): qwen2.5:1.5b whole on the GPU 49 tok/s; on the CPU 26 tok/s; qwen2.5-coder:7b with offload 1.94 of 4.91 GB on the GPU, 10.3 tok/s.
- `python run.py compute matrix` prints the table.
