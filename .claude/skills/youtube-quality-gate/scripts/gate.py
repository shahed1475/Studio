#!/usr/bin/env python3
"""Everything before approval: python .../gate.py <slug> [--llm] [--quick] [--visual]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))  # the project root
import studiochecks
sys.exit(studiochecks.main(["gate"] + sys.argv[1:]))
