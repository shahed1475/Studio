import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(not shutil.which("node"), reason="Node is not installed here")
def test_the_worker_forwards_only_the_api_with_the_secret_and_drops_spoofed_headers():
    r = subprocess.run(["node", "--test", str(ROOT / "cloudflare" / "worker.test.mjs")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-500:]


def test_the_built_site_carries_the_hubs_own_security_headers_and_leaves_the_privacy_page_to_the_hub(tmp_path):
    import sys
    sys.path.insert(0, str(ROOT / "cloudflare"))
    import build

    dist = build.build(tmp_path / "dist")
    h = (dist / "_headers").read_text()
    from hub import server
    assert server.CSP in h and "X-Frame-Options: DENY" in h and "challenges.cloudflare.com" in h
    assert (dist / "index.html").exists() and (dist / "signin.html").exists() and not (dist / "privacy.html").exists()
