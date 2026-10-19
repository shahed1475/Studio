---
name: youtube-quality-gate
description: "Use as the final check before any video is approved: runs the reviewer, script rules, sources, licenses, ffprobe and caption checks, and optionally the AI review and a frame-based visual review, then reports PASS or FAIL with every row."
---

# Quality gate

`.venv/bin/python .claude/skills/youtube-quality-gate/scripts/gate.py <slug> [--llm] [--quick] [--visual]`

- Always runs: the reviewer's rule checks (and writes `claims.json`), script rules, source evidence, licenses, ffprobe facts, full decode, captions against the script.
- `--llm` adds the AI fact and policy review (costs a few cents). `--visual` adds a vision model's reading of sampled frames (warnings only). `--quick` skips the full decode.
- Exit code 0 is PASS (no blocking row failed), 1 is FAIL, 2 means the video or a file is missing.

## Report to the owner
1. The verdict and every failing row, quoted from the output.
2. The claim ledger summary and any `UNVERIFIED` or `CONFLICTING` claims.
3. What the visual review could not see (it is a sample, not a viewing).
4. Licensing or platform-policy risks.
5. What needs the owner's decision.

A PASS is evidence about what was measured. It is not a promise that the video is free of errors, and it never replaces the owner's right to veto during the 24-hour window.
