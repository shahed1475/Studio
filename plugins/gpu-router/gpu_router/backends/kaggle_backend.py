"""Kaggle backend -- drives the official Kaggle CLI, nothing else.

Deliberately uses only sanctioned mechanisms: `kernels push` queues a committed
notebook run, `kernels status` polls it, `kernels output` pulls the artifacts.
No tunnels, no SSH, no keep-alives, no second account. Kaggle bans all of those.

Inputs are passed in as a Kaggle Dataset (see push_manifest) rather than having
the notebook poll your server, because a polling notebook looks like a worker.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

from .. import config

BACKEND = "kaggle"

# Kaggle reports these and stops changing.
TERMINAL_OK = {"complete"}
TERMINAL_BAD = {"error", "cancelacknowledged", "cancelrequested"}
# Kaggle CLI 2.x prints `<ref> has status "KernelWorkerStatus.COMPLETE"`; older CLIs printed `status "complete"`. The first version of this pattern read
# every 2.x status as "kernelworkerstatus", so wait() could never end (checked against real CLI 2.2.5 output, 25 Nov 2026).
_STATUS_RE = re.compile(r'status\s*:?\s*"?(?:KernelWorkerStatus\.)?([A-Za-z_]+)', re.IGNORECASE)
ACCELERATORS = {"gpu": "NvidiaTeslaT4", "tpu": "TpuV5E8"}  # `kaggle kernels push --accelerator` names (CLI 2.2.5 help; the P100 is retired)


class KaggleError(RuntimeError):
    pass


def _cli() -> str:
    exe = shutil.which("kaggle")
    if not exe:
        raise KaggleError(
            "kaggle CLI not found. Run: pip install kaggle\n"
            "Then put YOUR OWN token at ~/.kaggle/kaggle.json and chmod 600 it. "
            "Download it from kaggle.com -> Settings -> API -> Create New Token."
        )
    return exe


def _run(args: list[str], timeout: int = 600) -> str:
    proc = subprocess.run(
        [_cli(), *args], capture_output=True, text=True, timeout=timeout, check=False
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise KaggleError(f"`kaggle {' '.join(args)}` failed: {detail}")
    return proc.stdout


def kernel_ref(job_dir: Path) -> str:
    """Read the kernel id ("user/slug") out of kernel-metadata.json."""
    meta_path = Path(job_dir) / "kernel-metadata.json"
    if not meta_path.exists():
        raise KaggleError(
            f"{meta_path} missing. Generate one with: kaggle kernels init -p {job_dir}"
        )
    meta = json.loads(meta_path.read_text())
    ref = meta.get("id")
    if not ref or "/" not in ref:
        raise KaggleError(f'kernel-metadata.json needs "id": "<username>/<slug>", got {ref!r}')
    return ref


def check_metadata(job_dir: Path) -> list[str]:
    """Warn about the settings that silently waste a run."""
    meta = json.loads((Path(job_dir) / "kernel-metadata.json").read_text())
    warnings = []
    if not meta.get("enable_gpu") and not meta.get("enable_tpu"):
        warnings.append("no accelerator enabled -- this will run on CPU only")
    if not meta.get("enable_internet"):
        warnings.append("enable_internet is false -- pip install and model downloads will fail")
    if meta.get("enable_gpu") and meta.get("enable_tpu"):
        warnings.append("both GPU and TPU requested -- Kaggle will pick one; set only one")
    return warnings


def push(job_dir: Path, accelerator: Optional[str] = None, timeout_s: Optional[int] = None) -> str:
    """Queue a committed run. Returns the kernel ref to poll. accelerator: "gpu" or "tpu" (the router's choice) is sent as --accelerator, so the run
    gets the card that was budgeted; timeout_s caps the session (-t)."""
    job_dir = Path(job_dir)
    ref = kernel_ref(job_dir)
    for w in check_metadata(job_dir):
        print(f"  warning: {w}")
    args = ["kernels", "push", "-p", str(job_dir)]
    if accelerator in ACCELERATORS:
        args += ["--accelerator", ACCELERATORS[accelerator]]
    if timeout_s:
        args += ["-t", str(int(timeout_s))]
    _run(args)
    return ref


def parse_status(out: str) -> str:
    """'complete', 'running', 'queued', 'error', 'cancelacknowledged'... from the CLI's text; 'unknown' when it cannot be read."""
    match = _STATUS_RE.search(out or "")
    return match.group(1).replace("_", "").lower() if match else "unknown"


def status(ref: str) -> str:
    """Current status, lowercased. Unknown output is reported as 'unknown'."""
    return parse_status(_run(["kernels", "status", ref], timeout=120))


def real_quota() -> Optional[dict]:
    """The account's own remaining hours from `kaggle quota --format json` (CLI 2.2.5): {"gpu": h, "tpu": h, "refresh": iso}. None when the CLI cannot
    say (older CLI, no network). The local ledger only estimates; this is Kaggle's figure."""
    try:
        rows = json.loads(_run(["quota", "--format", "json"], timeout=60))
    except (KaggleError, ValueError, OSError, subprocess.SubprocessError):
        return None
    out = {}
    for r in rows if isinstance(rows, list) else []:
        try:
            out[str(r["resource"]).lower()] = float(str(r["remaining"]).rstrip("h"))
            out["refresh"] = r.get("refreshAt")
        except (KeyError, ValueError):
            continue
    return out if "gpu" in out else None


def wait(
    ref: str,
    poll_seconds: int = 120,
    timeout_hours: float = config.KAGGLE_MAX_GPU_SESSION_HOURS + 0.5,
    on_poll=None,
) -> str:
    """Block until the run reaches a terminal state or we pass the session cap."""
    deadline = time.time() + timeout_hours * 3600
    while time.time() < deadline:
        state = status(ref)
        if on_poll:
            on_poll(state)
        if state in TERMINAL_OK:
            return state
        if state in TERMINAL_BAD:
            raise KaggleError(f"{ref} finished as {state!r}; check the run log on kaggle.com")
        time.sleep(poll_seconds)
    raise TimeoutError(f"{ref} still {status(ref)!r} after {timeout_hours} h")


def output(ref: str, dest: Path) -> Path:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    _run(["kernels", "output", ref, "-p", str(dest)], timeout=1800)
    return dest


def push_manifest(dataset_dir: Path) -> None:
    """Publish a new version of the input manifest Dataset.

    Passing work in as a Dataset input keeps the notebook a notebook. Needs a
    dataset-metadata.json -- create once with: kaggle datasets init -p <dir>
    """
    dataset_dir = Path(dataset_dir)
    if not (dataset_dir / "dataset-metadata.json").exists():
        raise KaggleError(
            f"{dataset_dir}/dataset-metadata.json missing. "
            f"Run: kaggle datasets init -p {dataset_dir}"
        )
    _run(["datasets", "version", "-p", str(dataset_dir), "-m", "manifest update", "-r", "zip"])
