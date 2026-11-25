"""All tunables in one place. Override any of these with environment variables."""
from __future__ import annotations

import os
from pathlib import Path


def _f(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


# Where the ledger lives.
DB_PATH = Path(os.environ.get("ROUTER_DB", Path.home() / ".gpu_router" / "ledger.db"))

# Published free allowances. Kaggle states "30 hours or sometimes higher", so this
# is a floor, not a promise -- check your own figure in Kaggle account settings.
KAGGLE_GPU_WEEKLY_HOURS = _f("KAGGLE_GPU_WEEKLY_HOURS", 30.0)
KAGGLE_TPU_WEEKLY_HOURS = _f("KAGGLE_TPU_WEEKLY_HOURS", 20.0)
MODAL_MONTHLY_CREDIT_USD = _f("MODAL_MONTHLY_CREDIT_USD", 30.0)

# Hard platform limits. Do not raise these -- the platform enforces them.
KAGGLE_MAX_GPU_SESSION_HOURS = 12.0
KAGGLE_MAX_TPU_SESSION_HOURS = 9.0

# Leave this much quota unspent so a mis-estimated job can't strand you at zero.
SAFETY_MARGIN_HOURS = _f("ROUTER_SAFETY_MARGIN_HOURS", 1.0)

# Jobs shorter than this are a poor fit for Kaggle (session startup dominates)
# and belong on a per-second backend instead.
SHORT_JOB_MINUTES = _f("ROUTER_SHORT_JOB_MINUTES", 20.0)

# Rough Modal cost per GPU-hour, used only to decide whether credit remains.
MODAL_USD_PER_GPU_HOUR = _f("MODAL_USD_PER_GPU_HOUR", 0.60)

KAGGLE_USERNAME = os.environ.get("KAGGLE_USERNAME", "")

# Kaggle's Terms of Use (22 Jun 2025) allow "internal, personal, non-commercial use". Commercial work (for example renders for a monetised channel) is
# never sent to Kaggle unless the owner records the reference of Kaggle's WRITTEN permission here. Empty = refused.
KAGGLE_COMMERCIAL_PERMISSION_REF = os.environ.get("KAGGLE_COMMERCIAL_PERMISSION_REF", "")

# Modal is a paid service with free credit; the cost here is only an estimate. It is used only when switched on (MODAL_ENABLED=1).
MODAL_ENABLED = os.environ.get("MODAL_ENABLED", "") == "1"

# Cloudflare R2 (optional). Anything unset disables the R2 helpers.
R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID", "")
R2_BUCKET = os.environ.get("R2_BUCKET", "")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "")
