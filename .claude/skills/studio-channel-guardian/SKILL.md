---
name: studio-channel-guardian
description: "Use when YouTube changes a rule or security setting, a video may be at risk, or the guardian (guardian.py) needs changing: what it may do, how a held video is repaired and uploaded again, how views and likes are protected."
---

# Channel Guardian
Runs hourly (`python run.py guardian`, no model, no cost). Rules in code and in `playbooks/guardian.md`.

## What it does
- Public video: only watched; a problem becomes one owner task. Never edited. The title test (owner mode `apply`, before/after views, automatic revert) is the only path that changes a live title.
- Not public (draft or private/scheduled): repairs metadata (`seo.enforce` through `compliance.sanitize`), rewrites thumbnail text that repeats the title, pushes both to YouTube when titletest mode is `apply` and the login can write.
- Held video with a content problem: `reissue` returns it to a draft (old id kept in `superseded`), Autopilot repairs, re-checks, schedules and uploads a NEW private copy. The old private copy is not deleted; the owner is told to remove it in Studio.
- Policy page changed (`newswatch.policy_watch`): an owner task to re-verify the rule; the guardian cannot mark a rule verified.
## Never
Make public, delete, edit a public video's content, change channel settings, flip a switch (`titletest` mode, `human_approval`).
## When a new kind of problem appears
`unstick.run` (every 3 hours) gives a stuck draft to `escalate.solve`; unresolved cases become `needs_owner` tasks with what was tried. Add a safe fix to `unstick.fixes_for` and a case to `agenteval.py`.
