#!/usr/bin/env python3
"""Check a script against the writing rules: python .../check_script.py <slug>"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))  # the project root
import studiochecks
sys.exit(studiochecks.main(["script"] + sys.argv[1:]))
