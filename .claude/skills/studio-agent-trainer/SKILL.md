---
name: studio-agent-trainer
description: "Use when adding or improving a studio agent: writing its playbook, its prompts, a new skill, or teaching it from past cases (self-training). Covers playbooks/, lessons.py, escalate.py and prompt rules for this repo."
---

# Training a studio agent (no model is retrained; its rules, memory and checks are)

Every agent has five things. Add all five for a new agent.
1. **Playbook** `playbooks/<agent>.md` with `model_role:` (script, review or cheap) and the sections Role, Goal, When, How, Tools, Never, Escalate. Short: it is pasted into prompts (`playbook.brief`, 1300 to 1500 characters). Write only what the agent really does with code that exists. `playbook.problems(agent)` must be empty.
2. **Lessons** `lessons.record(agent, problem, tried, worked)` after every attempt; `lessons.brief(agent, problem)` in the next prompt. Same problem shape, a fix that worked goes first, one that failed twice is skipped.
3. **Ladder** `escalate.solve(agent, problem, evidence, fixes)`: lessons, a diagnosis by the agent's role, a second opinion from another role, then the owner. `fixes` is a fixed dict of safe functions returning `(ok, detail)`; the model only picks names.
4. **Inbox** `agentbus.post(kind, source, target, slug, ...)` to ask another agent; close it when done.
5. **Evaluation** a case in `agenteval.py` for each rule the agent must never break, plus a mutation check that the case fails when the rule is broken.

## Prompt rules for this repo
- Untrusted text (web pages, rival titles, lessons, events) is labelled as data and cleaned with `seo.plain` / `seo.linky`, capped in length.
- Ask for JSON with a named schema; the code validates every field and ignores names it did not offer.
- Playbook first, then lessons, then the task; no secrets, no keys, no personal data.
- Cheapest role that does the job; cap the output; one retry; never loop on a failure.

## Creating a skill
A skill is a folder with `SKILL.md` (name, description that says WHEN to use it, then short steps). First-party studio skills are named `studio-*`. A third-party skill goes in only through `python extend.py add <folder>` after `vetskill.py`.

## Limits
A playbook and lessons guide a model; they do not make it right. Evaluation proves the rules hold on test cases, not that a new problem is solved.
