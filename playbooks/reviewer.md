model_role: review
## Role
Gate before any upload: file checks, claim checks against the source, and an AI reading of the script.
## Goal
No video with an invented fact, a copyright or policy risk or a broken file goes out.
## When
Every new or edited video; again before the slot and after publishing (recheck).
## How
Deterministic checks first, then the model with the source article. A model failure is "unreviewed", never fail and never pass. Before an approval the pictures are read and the narration is listened to (voicecheck: an audio model writes down what it hears WITHOUT the script, our code compares it with the script; a warning only, a name heard differently is a lead, not proof).
## Tools
reviewer.review, studiochecks, compliance, voicecheck (run.py listen <slug>).
## Never
Pass because a model agrees. Fail because a model errored.
## Escalate
Two reviewers that disagree: needs_human.
