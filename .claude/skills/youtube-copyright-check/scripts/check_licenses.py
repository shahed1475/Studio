#!/usr/bin/env python3
"""Check picture, text and music licenses: python .../check_licenses.py <slug>"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))  # the project root
import studiochecks
sys.exit(studiochecks.main(["licenses"] + sys.argv[1:]))
