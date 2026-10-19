#!/usr/bin/env python3
"""Ask YouTube what it stored for an uploaded video and compare it with the plan: python .../verify_upload.py <slug>"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))  # the project root
import json

import config
import upload

folder = config.OUT / sys.argv[1]
if not (folder / "meta.json").exists():
    print(f"no video named {sys.argv[1]}")
    sys.exit(2)
meta = json.loads((folder / "meta.json").read_text())
if not meta.get("video_id"):
    print("not uploaded yet: there is no video id to check")
    sys.exit(2)
result = upload.verify_upload(upload._service(), meta["video_id"], {"title": meta["title"], "privacy": "private" if meta.get("publish_at") else "private", "publish_at": meta.get("publish_at")})
print(json.dumps(result, indent=2))
sys.exit(0 if result["ok"] else 1)
