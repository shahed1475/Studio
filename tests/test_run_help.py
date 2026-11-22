"""run.py's help names every command it handles (22 Nov 2026: 35 of 67 were missing, so skills and agents told to use `run.py agents`,
`run.py doctor` or `run.py judges` could not find them in the help)."""
import re
from pathlib import Path

import run

SRC = (Path(__file__).resolve().parent.parent / "run.py").read_text()


def test_every_command_run_py_handles_is_in_its_help():
    handled = set()
    for cond in re.findall(r"a\[0\] (?:==|in) ([^:]*)", SRC):
        handled |= set(re.findall(r'"([a-z][a-z0-9-]*)"', cond))
    shown = set(re.findall(r"python run\.py ([a-z][a-z0-9-]*)", run.__doc__))
    assert len(handled) > 60
    assert handled <= shown, sorted(handled - shown)
