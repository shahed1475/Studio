---
name: gpu-router
description: Route video render and model-inference jobs across free GPU tiers (Kaggle 2xT4, Modal credits) without running out of quota mid-render. Use this whenever the user is deciding where to run a render, asks how much GPU quota is left, hits a Kaggle session or weekly-quota limit, wants a long render split across sessions, asks why a render is slow on a T4, or mentions Kaggle notebooks, Modal, TPU hours, MiniMax H3, Open-H3-Regenerate, ffmpeg/NVENC encoding, or checkpointing a render. Also use it before writing any new render or batch-inference script, even when the user does not mention quotas, because picking the wrong backend wastes hours that cannot be refunded.
---

# GPU Router

Free GPU is plentiful but non-fungible. Kaggle gives roughly 30 GPU-hours and 20
TPU-hours a week in sessions capped at 12 hours; Modal gives $30 of per-second
credit a month with nothing charged while idle. Those are different *shapes* of
capacity, not one pool. Most wasted time comes from sending a job to the wrong
shape, or from starting a job the remaining quota can't finish.

## Route by job shape first, quota second

| Job | Backend | Why |
|---|---|---|
| One long render, latency-tolerant | Kaggle, committed run | 12-hour sessions; a per-second backend would drain credit |
| Many short inferences | Modal | Per-second billing, scale-to-zero, no idle cost |
| Bulk image generation | per-output API (fal) | Per-output beats per-second at volume |
| No accelerator needed (ffmpeg assemble, audio, concat) | always-on box | Costs nothing from any quota |

Run `gpu-router plan --minutes N` to see the decision and the reason before
committing. `gpu-router quota` shows what's left and when it resets.

## The rules that actually protect the quota

**Quota burns while the accelerator is attached, not while it computes.** Edit
and debug with the GPU off, then commit the run. A typical wasted week spends
five of thirty hours with a GPU idling under a text editor.

**Two T4s cost the same as one.** Kaggle counts wall-clock session hours, so
keeping both cards busy is free throughput. Use GPU0 for the diffusion model and
GPU1 for the text encoder rather than offloading to host RAM — Kaggle sessions
have only ~29 GB of RAM, and sequential CPU offload is the most common way a
10-minute job becomes an hour.

**Never start a shard the session can't finish.** A shard killed at the 12-hour
wall costs its full GPU time and produces nothing, and that time is gone from the
week. `notebook_bootstrap.can_admit()` refuses work inside the last 45 minutes.

**Shard by shot and by stage** (embed → draft → refine → decode → encode), and
persist each stage. Latents are small, so a crash in decode costs minutes
instead of the whole denoise. Resume must be idempotent: skip any shard whose
artifact exists, write to `.tmp` and rename atomically.

**Push every artifact off-box as it finishes.** `/kaggle/working` only persists
with a notebook version, so don't bet a ten-hour run on the final commit.

## Turing (T4) is not Ampere

Most published speed advice doesn't apply to a T4, and trying it wastes a
session. Not available on Turing: FlashAttention-2, official SageAttention, FP8,
NVFP4, and current Triton/torch.compile. What works: FP16 activations (cast BF16
weights — there are no BF16 tensor cores), INT8 W8A8, PyTorch SDPA or a validated
sm75 attention fork.

The big multipliers are not kernel tricks — they are **fewer steps** (a
step-distilled Turbo LoRA at 4–8 steps instead of 20–50) and **fewer pixels**
(draft at 512–576p, finish at 1080p; a vertical Short never needs 2K). Those are
worth 3–10x. Kernel swaps are worth 1.5–2x. Step-skipping caches like TeaCache
only help undistilled 20+-step samplers; on a 3-step refine they have nothing to
skip.

For encoding, keep frames on the GPU: `-hwaccel cuda -hwaccel_output_format cuda`
with `scale_cuda`/`overlay_cuda` and `h264_nvenc`. A single CPU filter such as
`drawtext` forces a PCIe round trip — burn captions as an RGBA overlay instead.
Encode each shot once at final settings, then assemble with the concat demuxer
and `-c copy`. The T4 has no AV1 encoder and no concurrent-session limit.

## Stay inside the terms

Kaggle is for personal, non-commercial ML work (Terms of Use, 22 Jun 2025). Renders or assets for a monetised channel are commercial: they go to
your own hardware unless Kaggle has given written permission (`KAGGLE_COMMERCIAL_PERMISSION_REF`). Mark only genuinely personal jobs `--personal`.
Modal costs money beyond its credit and is off unless `MODAL_ENABLED=1`.

Only official mechanisms: `kaggle kernels push/status/output`, Save & Run All,
and Dataset inputs. Pass work in as a Dataset rather than having the notebook
poll an external queue — a polling notebook looks like a distributed worker.

Kaggle bans multiple accounts, inbound tunnels and SSH, persistent servers, and
scripted keep-alives, and does ban for it. Colab's free tier disallows the same
things, so it stays a manual tool and never a router backend. Stacking *different
providers* (one Kaggle account plus one Modal account) is fine — that is not
circumvention. Stacking accounts on one provider is.

## TPU

Kaggle's free TPU (now v5e-8) is a separate 20-hour pool, but it only runs
TPU-native stacks via JAX — MaxDiffusion supports Wan 2.x and LTX-Video. There is
no JAX port of MiniMax H3 or Open-H3-Regenerate, and the quantized paths are all
CUDA. Treat the TPU quota as a separate B-roll pipeline if it's worth days of
setup, not as extra capacity for the main model.

## Files

- `gpu_router/router.py` — the policy above, as code
- `gpu_router/ledger.py` — SQLite quota accounting; weekly window resets Saturday 00:00 UTC
- `gpu_router/backends/kaggle_backend.py` — official CLI wrapper
- `gpu_router/backends/modal_backend.py` — `modal run` wrapper with cost estimation
- `gpu_router/storage/r2.py` — artifact upload/download/resume
- `gpu_router/notebook_bootstrap.py` — paste into the notebook's first cell
