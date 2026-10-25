---
name: studio-trace-triage
description: "Use when the activity feed is noisy, a problem keeps coming back, or an agent seems stuck: group events into problem families, find what is new or recurring, and decide who handles each."
---

# Trace triage
1. `python run.py agent-review` (or `tracetriage.triage()`): families from the last 7 days in `data/agent/triage.json`, each `known`, `recurring` (3 or more) or `new`.
2. For a recurring or new family read three real events (`data/agent/events.jsonl`), the video's `meta.json` (`review.checks`, `fix_attempts`, `ladder`) and `logs/`. Name the cause from evidence, not from the title.
3. Decide the owner of the fix: a rule the code lacks (a developer change plus a test), a fix the ladder can try (add it to `unstick.fixes_for`), a knowledge gap (a playbook or lesson), or the owner (a choice or an account action).
4. Record the outcome with `lessons.record` so the next case starts from it. Close the inbox task.
5. Silent agents: a job that has logged nothing for its whole period is a finding too (`python run.py agents`, worker log).
Limit: a family is a guess from event titles; confirm with the underlying record before acting.
