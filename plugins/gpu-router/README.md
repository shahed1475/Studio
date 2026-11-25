# gpu-router

A quota-aware router that spreads GPU work across free tiers you already own —
one Kaggle account, one Modal account — and refuses to start a job the remaining
quota can't finish.

It exists because free GPU is **non-fungible**. Kaggle gives ~30 GPU-hours and
20 TPU-hours a week in 12-hour sessions; Modal gives $30/month of per-second
credit with nothing charged while idle. Sending a 10-hour render to a per-second
backend drains the credit; sending 2,000 half-minute jobs to Kaggle wastes the
week on session startup. The router matches shape to backend, and the ledger
stops you finding out you were out of quota nine hours into a render.

## Install

```bash
pip install -e .            # add [r2] and [modal] extras if you want those
cp .env.example .env        # then fill it in
```

Your Kaggle token is yours — this package never asks for it. Get it from
kaggle.com → Settings → API → Create New Token, save as `~/.kaggle/kaggle.json`,
then `chmod 600 ~/.kaggle/kaggle.json`. GPU access needs a phone-verified
account.

## Use

```bash
gpu-router quota                                  # what's left, and when it resets
gpu-router plan --minutes 300                     # where would this go, and why
gpu-router submit ./h3job --minutes 300 --wait    # route it, push it, fetch output
```

Inside the Kaggle notebook, first cell:

```python
from gpu_router import notebook_bootstrap as nb
shots = nb.load_manifest()
for shot in shots:
    nb.run_stage(shot["id"], "draft", lambda p: render_draft(shot, p),
                 expected_hours=0.2, ext="safetensors")
print(nb.summary(shots, ["draft", "refine", "decode", "encode"]))
```

`run_stage` skips finished shards, refuses work inside the last 45 minutes of the
session, writes atomically, and can push each artifact to R2 as it lands.

## What's inside

| File | Does |
|---|---|
| `gpu_router/router.py` | Picks a backend by job shape, then by remaining quota |
| `gpu_router/ledger.py` | SQLite accounting; weekly window resets Saturday 00:00 UTC |
| `gpu_router/backends/kaggle_backend.py` | `kernels push/status/output` via the official CLI |
| `gpu_router/backends/modal_backend.py` | `modal run` with duration-based cost estimate |
| `gpu_router/storage/r2.py` | Artifact upload/download, latest-checkpoint lookup |
| `gpu_router/notebook_bootstrap.py` | Resume, time-budget guard, atomic writes |
| `skills/gpu-router/SKILL.md` | The operating knowledge, as a Claude Code skill |
| `commands/` | `/gpu-quota` and `/gpu-plan` |

## Honest limits

- **Modal and R2 not run against a live account.** The 27 unit tests (17 original, 10 from the 25 Nov 2026 review) cover the
  quota window, reservation accounting and routing decisions; the CLI wrappers
  are untested end-to-end because that needs your credentials. The status parser was fixed against real
  Kaggle CLI 2.2.5 output (`KernelWorkerStatus.COMPLETE`); see REVIEW_2026-11-25.md.
- **Modal cost is estimated**, not read from Modal's billing. It's duration ×
  `MODAL_USD_PER_GPU_HOUR`. Check the real balance in Modal's dashboard and
  correct the rate.
- **Verify `kernel-metadata.json` fields** against your own `kaggle kernels init`
  output — the schema has changed over time, especially around accelerator names.
- **Colab is deliberately not a backend.** Automating its free tier breaks its
  terms; it stays a manual tool.
- Quota figures are defaults, not guarantees. Kaggle publishes "30 hours or
  sometimes higher"; put your real number in `.env`.

## Terms of service

**Kaggle is personal and non-commercial.** Kaggle's Terms of Use (version 22 Jun 2025) allow "internal, personal, non-commercial use", and its
Acceptable Use Policy bars "activity unrelated to ML data science" and "server farming". Renders for a monetised channel are commercial work.
Since 0.1.1 every job is treated as commercial unless marked `--personal`, and a commercial job never goes to Kaggle unless
`KAGGLE_COMMERCIAL_PERMISSION_REF` records Kaggle's written permission. Modal is a paid service: it is used only with `MODAL_ENABLED=1`.


Only official mechanisms are used: the Kaggle CLI, committed runs, Dataset
inputs. No tunnels, no SSH, no keep-alives, no second accounts — Kaggle bans all
of those, and a ban would cost more than the hours are worth. Stacking different
providers is fine; stacking accounts on one provider is not.
