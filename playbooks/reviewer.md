model_role: review
## Role
Gate before any upload: file checks, claim checks against the source, and an AI reading of the script.
## Goal
No video with an invented fact, a copyright or policy risk or a broken file goes out.
## When
Every new or edited video; again before the slot and after publishing (recheck).
## How
Deterministic checks first, then the model with the source article. A model failure is "unreviewed", never fail and never pass. In the owner's free-only mode (`free_review`) the judge cascade (judges.py, config/judges.json, 22 Nov 2026) reads it: slot A Gemini with the full source, then FreeLLMAPI Qwen and GLM; slot B a different model family with a compact rubric, one OpenRouter try (25 s, no retry, busy or used up: OpenRouter skipped for an hour) on source excerpts that keep every name, date and number, then FreeLLMAPI. The stricter answer counts; fewer than two answers is "unreviewed". Before an approval the pictures are read and the narration is listened to (voicecheck: a warning only; a name heard differently is a lead, not proof).
## Tools
reviewer.review, judges.plan (run.py judges <slug>), studiochecks, compliance, voicecheck (run.py listen <slug>).
## Never
Pass because a model agrees. Fail because a model errored. Let a writer or a router judge. Read a judge's reasoning as its verdict. Count two models of one family as two judges, in the script fact-check too (24 Nov 2026): without a second family the check is blocked.
## Escalate
Two reviewers that disagree: needs_human.

## Scene sources (25 Nov 2026)
Code, not the model: `scene_sources` (warn) reads the scene manifest (scenemanifest.py, scenes.json in the video folder) and names scenes filled from the subject's general reserve, repeats after a failed drawing, files shown twice, and unchanged lines whose picture moved since the last render. "Different on-topic images" alone never means each picture fits its line.
