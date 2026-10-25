---
name: studio-agent-eval
description: "Use when reviewing, evaluating or behaviour-testing a studio agent, or after changing any agent module: agent review checklist, agenteval cases, mutation checks, the Agents row of the Risks card."
---

# Agent review, evaluation and behaviour checks

## Review (before merging a change to an agent)
1. Read its playbook and the diff. Does the code do only what the playbook says? Is every "Never" still true?
2. Can it publish, delete, change a public video or flip an owner switch? (`agenteval.FORBIDDEN` scans the agent modules.)
3. Is every model call capped (role, tokens, count) and charged to the video (`llm.cost_scope`)? Is there a budget gate?
4. Is every outside text cleaned before a prompt? Every file write atomic (`records`, `filelock.write_atomic`)?
5. What happens on a model error, a YouTube error, a corrupt record, a lock held by Autopilot? It must end as a plain message or the owner, never a crash or a loop.

## Evaluation
- `python run.py agent-review` runs `agenteval.run()` (writes `data/agent/eval.json`), the trace triage and the lessons prune. `python run.py agents` shows the result.
- Structural cases: playbooks complete. Behavioural cases: public video never edited; metadata fixed before public; reissue only for a held, unapproved, not-public video; unknown problem ends with the owner; budget respected; a fix that failed twice is not repeated; outside text cleaned; stuck-draft rules.
- A new rule needs a new case AND a mutation check: break the rule in a copy of the module and confirm the case fails (an eval that cannot fail proves nothing).

## Reporting
Say which cases ran and their result. A passing evaluation is evidence the rules hold on the cases, not proof the agent is right.
