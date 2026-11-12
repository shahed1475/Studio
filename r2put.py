"""Upload the newest nightly backups to a Cloudflare R2 bucket (a second off-server copy next to deploy/backup_push.sh).

No new dependency: R2 speaks the S3 protocol, so each PUT is signed with AWS Signature V4 using only the standard library and `requests`.
Settings are read by name from the server's .env (never sourced, never printed, never in git): R2_ACCOUNT_ID, R2_BUCKET, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY.
The access key should be an R2 token limited to this one bucket (Object Read & Write). Only files named backup-YYYYMMDD.tar.gz are sent, and only when valid gzip and under 30 hours old.
Run on the server after the 03:30 backup:  python r2put.py   (python r2put.py --dry shows what would be sent and sends nothing)."""
import datetime as dt
import gzip
import hashlib
import hmac
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
NAME = re.compile(r"backup-\d{8}\.tar\.gz$")
KEYS = ("R2_ACCOUNT_ID", "R2_BUCKET", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")
MARKER = "last_r2.txt"
MAX_AGE_H = 30


def _hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


def signing_key(secret: str, date: str, region: str, service: str) -> bytes:
    k = _hmac(("AWS4" + secret).encode(), date)
    for part in (region, service, "aws4_request"):
        k = _hmac(k, part)
    return k


def sign_put(account: str, bucket: str, key: str, body: bytes, access: str, secret: str, now: dt.datetime) -> tuple[str, dict]:
    """(url, headers) for a SigV4-signed PUT of `body` to R2 (region 'auto', service 's3')."""
    host = f"{account}.r2.cloudflarestorage.com"
    path = f"/{bucket}/{key}"
    stamp, date = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
    payload = hashlib.sha256(body).hexdigest()
    signed = "host;x-amz-content-sha256;x-amz-date"
    canon = f"PUT\n{path}\n\nhost:{host}\nx-amz-content-sha256:{payload}\nx-amz-date:{stamp}\n\n{signed}\n{payload}"
    scope = f"{date}/auto/s3/aws4_request"
    to_sign = f"AWS4-HMAC-SHA256\n{stamp}\n{scope}\n{hashlib.sha256(canon.encode()).hexdigest()}"
    sig = hmac.new(signing_key(secret, date, "auto", "s3"), to_sign.encode(), hashlib.sha256).hexdigest()
    auth = f"AWS4-HMAC-SHA256 Credential={access}/{scope}, SignedHeaders={signed}, Signature={sig}"
    return f"https://{host}{path}", {"x-amz-date": stamp, "x-amz-content-sha256": payload, "Authorization": auth}


def settings(env_file: Path) -> dict:
    out = {}
    try:
        for line in env_file.read_text().splitlines():
            k, _, v = line.partition("=")
            if k in KEYS and v.strip():
                out[k] = v.strip().strip("'\"")
    except OSError:
        pass
    missing = [k for k in KEYS if k not in out]
    if missing:
        raise SystemExit(f"r2put: missing in .env: {', '.join(missing)}")
    return out


def newest(backups: Path, count: int = 2) -> list[Path]:
    files = [p for p in backups.iterdir() if p.is_file() and not p.is_symlink() and NAME.match(p.name)]  # a link planted in backups/ is never followed
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[:count]


def valid(path: Path) -> bool:
    try:
        with gzip.open(path) as f:
            while f.read(1 << 20):
                pass
        return True
    except (OSError, EOFError):
        return False


def run(src: Path, dry: bool = False, now: dt.datetime | None = None, put=requests.put) -> list[str]:
    now = now or dt.datetime.now(dt.timezone.utc)
    files = newest(src / "backups")
    if not files:
        raise SystemExit("r2put: no backup archive found")
    age_h = (now.timestamp() - files[0].stat().st_mtime) / 3600
    if age_h >= MAX_AGE_H:
        raise SystemExit(f"r2put: the newest backup is {age_h:.0f} hours old: not sending a stale copy as if it were fresh")
    bad = [p.name for p in files if not valid(p)]
    if bad:
        raise SystemExit(f"r2put: not a valid gzip file: {', '.join(bad)}")
    if dry:
        return [p.name for p in files]
    cfg = settings(src / ".env")
    sent = []
    for p in files:
        body = p.read_bytes()
        url, headers = sign_put(cfg["R2_ACCOUNT_ID"], cfg["R2_BUCKET"], p.name, body, cfg["R2_ACCESS_KEY_ID"], cfg["R2_SECRET_ACCESS_KEY"], now)
        r = put(url, data=body, headers=headers, timeout=120)
        if r.status_code not in (200, 201):
            raise SystemExit(f"r2put: R2 refused {p.name}: HTTP {r.status_code}")  # the body can echo request details, so only the status is shown
        sent.append(p.name)
    (src / "backups" / MARKER).write_text(f"{now:%Y-%m-%dT%H:%M:%SZ} {sent[0]}\n")
    return sent


if __name__ == "__main__":
    names = run(ROOT, dry="--dry" in sys.argv)
    print(("would send: " if "--dry" in sys.argv else "sent: ") + ", ".join(names))
