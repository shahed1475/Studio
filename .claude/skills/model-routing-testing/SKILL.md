---
name: model-routing-testing
description: "Use when testing the model and compute router, the job protocol or the adapters: the mock scenarios and what each test proves; never spend Kaggle GPU hours or API quota on a basic test."
---

# Model routing testing (Story Studio)

Tests: `tests/test_compute_routing.py` (fakes for Ollama, nvidia-smi and the Kaggle CLI; job files in a temp folder).

Covered: no GPU, insufficient VRAM, a model smaller than the GPU that still does not fit, a half-downloaded GGUF, a changed file (hash mismatch), the forbidden folder, duplicate jobs, credentials in a job, an interrupted job resumed from its checkpoint, a power cut mid-job, an empty answer, licences, content policy, Kaggle off, Kaggle terms, production data to Kaggle, a private model to Kaggle, a paid environment, a busy GPU, an expired notebook session, the Cloudflare 4006 limit, the dashboard route and a user studio.
Real runs (`python run.py compute smoke`) are separate and use only this PC.
