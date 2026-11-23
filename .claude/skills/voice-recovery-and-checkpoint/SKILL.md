---
name: voice-recovery-and-checkpoint
description: "Use when voice generation is interrupted (power cut, killed job, provider stall) or resumed: keep every valid line, redo only missing or broken ones, never run two jobs, never overwrite approved narration. Follows the studio's existing line records and checkpoint rules."
---

# Voice recovery and checkpoint

The studio already does this for its current voice: each line is kept as `lineNN.mp3` with a `lineNN.json` record of its text hash and word timings, a half-written line stays `.part` and is never used, and stage markers with process and boot ids are in `work/checkpoint.json` (`checkpoint.py`, `tts.py`). A new voice engine must keep the same rules.

## After an interruption
1. Is a job still running? Check the worker's processes (`docker --context default top studio-worker -o pid,args`; the `-o args` form alone fails). Never start a second job while one runs.
2. Fingerprint what exists before resuming: `sha256sum` of every finished line and its record, saved outside the work folder.
3. Resume with the same command; afterwards compare the fingerprints: every earlier finished line must be unchanged, and any `.part` file must have been replaced, not used.
4. A cut is not a failed try (the studio counts it as an interruption).

## Rules
- Redo a line only when its record's text hash differs from the script, or the evaluator marked it `redo`.
- A new voice or a changed script means a NEW set of lines; the old ones are copied aside (for example `output_old/<video>-<reason>/`), never deleted.
- Approved narration is never overwritten without the owner's yes.
- Record per line: text hash, model, model version, speaker id, settings, duration, evaluation verdict.

## Example (23 Nov 2026)
The Mary Celeste film resumed after the 12:44 UTC power cut: 143 of 143 fingerprints matched after the resume, `line71.part.mp3` was replaced by a complete line, and the try counter stayed at 0.
