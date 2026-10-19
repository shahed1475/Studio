#!/usr/bin/env python3
"""Research a topic or inspect a video: python .claude/skills/youtube-research/scripts/inspect.py <topic | slug | file | YouTube link> [--question Q] [--frames N]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))  # the project root
import videoinspect
sys.exit(videoinspect.main(sys.argv[1:]))
