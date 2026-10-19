#!/usr/bin/env python3
"""ffprobe, full decode and caption checks: python .../check_video.py <slug> [--quick]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))  # the project root
import studiochecks
sys.exit(studiochecks.main(["video"] + sys.argv[1:]))
