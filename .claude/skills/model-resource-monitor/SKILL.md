---
name: model-resource-monitor
description: "Use when checking VRAM, RAM, GPU load, disk, running model jobs, Kaggle session time or quota before starting or while watching model work."
---

# Model resource monitor (Story Studio)

- Live: `computecompat.gpu_status` (name, total, used, free, load, which processes hold VRAM) and `computecompat.ram_status`.
- Ollama placement after a run: the job records Ollama's own `/api/ps` numbers (size and how much is in VRAM).
- Dashboard: the Compute page (`/compute`, `/api/compute`, `computerouter.view`), owner's studio only.
- Kaggle hours used are not readable by its API: never shown as a number; only the weekly quota from the account page.
- The router skips a GPU over 85% busy (in code). Not in code: waiting for a render to finish before a CPU job; check the worker before `python run.py compute smoke`.
