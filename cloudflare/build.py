"""Builds cloudflare/dist: the hub's site files plus a _headers file with the SAME security headers the hub sends with its own pages (taken from hub.server, so they cannot drift).
Usage (from the repo root): python3 cloudflare/build.py"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from hub import server  # noqa: E402


def build(dist: Path | None = None) -> Path:
    dist = dist or ROOT / "cloudflare" / "dist"
    if dist.exists():
        shutil.rmtree(dist)
    shutil.copytree(ROOT / "hub" / "web", dist, ignore=shutil.ignore_patterns("privacy.html"))  # the privacy page is served by the hub (its contact line is set there)
    (dist / "_headers").write_text("/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: no-referrer\n  X-Frame-Options: DENY\n"
                                   f"  Content-Security-Policy: {server.CSP}\n  Strict-Transport-Security: max-age=31536000; includeSubDomains\n"
                                   "/fonts/*\n  Cache-Control: public, max-age=31536000, immutable\n")
    return dist


if __name__ == "__main__":
    print("built", build())
