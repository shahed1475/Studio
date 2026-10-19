import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


import pytest


@pytest.fixture(autouse=True)
def _isolate_autopilot_log(tmp_path, monkeypatch):
    import autopilot

    monkeypatch.setattr(autopilot, "LOG", tmp_path / "autopilot.log")
