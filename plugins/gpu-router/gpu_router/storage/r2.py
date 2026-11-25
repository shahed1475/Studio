"""Cloudflare R2 artifact store (S3-compatible).

Every finished artifact goes off-box immediately. Kaggle's /kaggle/working only
persists with a notebook version, so a session that dies mid-run can lose hours
of GPU time that you already paid for out of quota. Uploading each stage as it
completes is what makes a crash cost minutes instead.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from .. import config


class R2NotConfigured(RuntimeError):
    pass


def configured() -> bool:
    return all([
        config.R2_ACCOUNT_ID, config.R2_BUCKET,
        config.R2_ACCESS_KEY_ID, config.R2_SECRET_ACCESS_KEY,
    ])


def client():
    if not configured():
        raise R2NotConfigured(
            "Set R2_ACCOUNT_ID, R2_BUCKET, R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY. "
            "Create the token in Cloudflare dash -> R2 -> Manage API tokens."
        )
    try:
        import boto3  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover
        raise R2NotConfigured("pip install boto3") from exc
    return boto3.client(
        "s3",
        endpoint_url=f"https://{config.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=config.R2_ACCESS_KEY_ID,
        aws_secret_access_key=config.R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def upload(local: Path, key: str) -> str:
    client().upload_file(str(local), config.R2_BUCKET, key)
    return f"r2://{config.R2_BUCKET}/{key}"


def download(key: str, local: Path) -> Path:
    local = Path(local)
    local.parent.mkdir(parents=True, exist_ok=True)
    client().download_file(config.R2_BUCKET, key, str(local))
    return local


def exists(key: str) -> bool:
    from botocore.exceptions import ClientError  # noqa: PLC0415
    try:
        client().head_object(Bucket=config.R2_BUCKET, Key=key)
        return True
    except ClientError:
        return False


def latest_checkpoint(prefix: str) -> Optional[str]:
    """Newest key under a prefix -- what a resuming run should start from."""
    resp = client().list_objects_v2(Bucket=config.R2_BUCKET, Prefix=prefix)
    objects = resp.get("Contents", [])
    if not objects:
        return None
    return max(objects, key=lambda o: o["LastModified"])["Key"]
