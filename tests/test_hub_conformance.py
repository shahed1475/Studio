"""Runs tools/hub_a2a_conformance.py with the official a2a-sdk client when an interpreter that has the SDK is named in HUB_A2A_SDK_PYTHON (the studio does not install the SDK)."""
import os
import subprocess
from pathlib import Path

import pytest

PY = os.getenv("HUB_A2A_SDK_PYTHON", "")


@pytest.mark.skipif(not PY, reason="set HUB_A2A_SDK_PYTHON to a Python with a2a-sdk installed to run the official-client check")
def test_the_official_a2a_client_can_use_the_hub():
    r = subprocess.run([PY, "-W", "ignore", str(Path(__file__).parent.parent / "tools" / "hub_a2a_conformance.py")], capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-1000:]
    assert "0 failed" in r.stdout
