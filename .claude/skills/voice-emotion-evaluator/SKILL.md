---
name: voice-emotion-evaluator
description: "Use to judge generated narration: objective audio measurements (level, clipping, silence, pitch range, pace, transcript match) kept separate from human listening judgments of naturalness and emotion. Never invents a listening score."
---

# Voice emotion evaluator

## Responsibility
Say whether each narrated line sounds right for its delivery note, with evidence, and list lines to redo.

## Input and output
- Input: the audio lines, their text and delivery notes ([schema](../expressive-voice-director/references/delivery-schema.md)).
- Output: per line `{"line", "objective": {...}, "listening": {...} or null, "verdict": "ok|redo|owner"}` and a short summary.

## Objective (measured, repeatable)
- Peak and loudness (ffmpeg `volumedetect`, `ebur128`): no clipping (peak below -1 dBFS).
- Silence at start and end, and gaps over 1.2 s inside a line.
- Words per minute against the note's pace.
- Pitch range (semitones, from a pitch track): a flat line in an emotional moment is a lead, not proof.
- Transcript match: the studio's listening check (`voicecheck.py`) writes down what it hears without the script; skipped, repeated or cut words show as runs of differences.
- Speaker consistency: compare each line with the approved reference clip (an embedding similarity if available); a drop is a lead.

## Listening (only a person, or clearly labelled as a model's opinion)
Naturalness, emotional fit, overacting, unwanted laughter, robotic rhythm, pronunciation of names. Write `null` when nobody listened. A model's opinion is labelled as such and never counted as a human score.

## Verdict rules
- `redo`: clipping, cut or repeated words, a vocal event in a serious line, silence over 1.2 s.
- `owner`: anything only a person can judge (emotion fit, naturalness), and every first sample of a new voice.
- `ok`: objective checks pass and, for a first sample, the owner approved.

## Never
Claim a voice is human-like, emotional or approved without a person having listened.
