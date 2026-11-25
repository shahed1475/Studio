"""Modal backend -- per-second serverless GPU, for short jobs.

Modal is the right home for many short jobs because it bills per second and
charges nothing while idle. Cost here is *estimated* from wall-clock duration
times a configured rate, then written to the ledger. That estimate is what the
router budgets against -- it is not Modal's billing figure. Check your real
balance in Modal's dashboard periodically and correct MODAL_USD_PER_GPU_HOUR.
"""
from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from .. import config

BACKEND = "modal"


class ModalError(RuntimeError):
    pass


def _cli() -> str:
    exe = shutil.which("modal")
    if not exe:
        raise ModalError("modal CLI not found. Run: pip install modal && modal setup")
    return exe


def run(entrypoint: str, args: list[str] | None = None, timeout: int = 3600) -> dict:
    """Run a Modal function synchronously. Returns duration and estimated cost.

    entrypoint is what you'd pass to `modal run`, e.g. "render.py::upscale".
    """
    started = time.time()
    proc = subprocess.run(
        [_cli(), "run", entrypoint, *(args or [])],
        capture_output=True, text=True, timeout=timeout, check=False,
    )
    duration_h = (time.time() - started) / 3600.0
    if proc.returncode != 0:
        raise ModalError((proc.stderr or proc.stdout).strip())
    return {
        "duration_hours": duration_h,
        "estimated_cost_usd": duration_h * config.MODAL_USD_PER_GPU_HOUR,
        "stdout": proc.stdout,
    }


def region_warning() -> str | None:
    """Modal's non-US regions carry a price multiplier -- worth saying out loud."""
    return (
        "Modal non-US regions can cost up to 2.5x. Pin US regions in your Modal "
        "function config, or the $30 monthly credit disappears much faster."
    )
