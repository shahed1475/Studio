#!/usr/bin/env python3
"""Is this video safe to hand to the uploader: python .../check_publish.py <slug>"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))  # the project root
import studiochecks
sys.exit(studiochecks.main(["publish"] + sys.argv[1:]))
