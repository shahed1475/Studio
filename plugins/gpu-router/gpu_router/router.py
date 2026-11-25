"""Routing policy: pick a backend by job *shape* first, remaining quota second.

The order matters. Matching shape to backend is what buys you extra hours --
a 10-hour render on a per-second backend drains credit fast, and a 30-second job
on Kaggle wastes a session on startup.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from . import config, ledger


@dataclass
class Job:
    kind: str                       # "render" | "upscale" | "infer" | "assemble" ...
    est_minutes: float
    needs_gpu: bool = True
    prefers_tpu: bool = False
    latency_sensitive: bool = False  # someone is waiting on the result
    job_key: Optional[str] = None    # idempotency key; reruns are refused
    commercial: bool = True          # fail closed: only a job marked personal (commercial=False) may use Kaggle without written permission

    @property
    def est_hours(self) -> float:
        return self.est_minutes / 60.0


@dataclass
class Decision:
    backend: str                     # "kaggle" | "modal" | "cpu" | "defer"
    accelerator: str                 # "gpu" | "tpu" | "cpu"
    reason: str
    split_runs: int = 1              # >1 when the job must be checkpoint-split

    @property
    def ok(self) -> bool:
        return self.backend != "defer"


def _kaggle_allowed(job: Job) -> bool:
    return not job.commercial or bool(config.KAGGLE_COMMERCIAL_PERMISSION_REF)


def _kaggle_remaining(accelerator: str, live: Optional[dict]) -> float:
    """The ledger's estimate, never more than Kaggle's own remaining figure when it is known (`kaggle quota`)."""
    est = ledger.kaggle_usage(accelerator).remaining_hours
    return min(est, live[accelerator]) if live and accelerator in live else est


def choose(job: Job, live: Optional[dict] = None) -> Decision:
    """live: kaggle_backend.real_quota() (Kaggle's own remaining hours), or None."""
    if not job.needs_gpu:
        return Decision("cpu", "cpu", "no accelerator required; costs no quota")
    modal_ok = config.MODAL_ENABLED
    kaggle_ok = _kaggle_allowed(job)

    if job.latency_sensitive or job.est_minutes < config.SHORT_JOB_MINUTES:
        if modal_ok and ledger.modal_remaining_usd() >= job.est_hours * config.MODAL_USD_PER_GPU_HOUR:
            return Decision("modal", "gpu", "short or latency-sensitive; per-second billing fits")
        # Out of credit: a waiting caller would rather have a slow answer than none.
        if job.latency_sensitive:
            return Decision("cpu", "cpu", "modal credit exhausted; falling back to CPU")

    if kaggle_ok and job.prefers_tpu:
        tpu_left = _kaggle_remaining("tpu", live)
        if tpu_left - config.SAFETY_MARGIN_HOURS >= job.est_hours:
            return Decision("kaggle", "tpu", f"TPU pool has {tpu_left:.1f} h left",
                            _splits(job.est_hours, config.KAGGLE_MAX_TPU_SESSION_HOURS))

    gpu_left = _kaggle_remaining("gpu", live)
    if kaggle_ok and gpu_left - config.SAFETY_MARGIN_HOURS >= job.est_hours:
        return Decision("kaggle", "gpu", f"long batch job; {gpu_left:.1f} h GPU quota left",
                        _splits(job.est_hours, config.KAGGLE_MAX_GPU_SESSION_HOURS))

    # Kaggle is spent or not allowed for this job. Modal can take it only when switched on and the credit covers it.
    needed = job.est_hours * config.MODAL_USD_PER_GPU_HOUR
    if modal_ok and ledger.modal_remaining_usd() >= needed:
        return Decision("modal", "gpu",
                        f"kaggle quota exhausted; ${needed:.2f} of modal credit covers it")

    if not kaggle_ok:
        return Decision("defer", "gpu", "commercial job: Kaggle's terms allow personal, non-commercial use only and no written permission is recorded "
                                        "(KAGGLE_COMMERCIAL_PERMISSION_REF); run it on your own hardware")
    return Decision("defer", "gpu",
                    "all GPU quotas exhausted; requeue after the next reset")


def _splits(est_hours: float, session_cap: float) -> int:
    """How many checkpointed sessions this job needs to clear the hard session cap."""
    if est_hours <= session_cap:
        return 1
    return int(-(-est_hours // session_cap))  # ceil
