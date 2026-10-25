# Agent training plan (26 Oct 2026)

Owner's goal: agents that handle new problems without waiting for the owner, an SEO agent that researches for views and subscribers, and a channel guardian that watches YouTube security and policy, holds a risky video, sends it to Autopilot for repair and has it uploaded again, without losing views or likes.

## What "training" means here (honest)
A language model is not trained by us. Its behaviour is shaped by five things we control, so each agent gets all five:
1. **Playbook** (`playbooks/<agent>.md`): role, goal, when, how, tools, never, escalate. Injected into the agent's prompts (`playbook.brief`).
2. **Lessons** (`lessons.py`): what was tried on which problem and whether it worked. The best matching lessons go into the next prompt (self-training).
3. **Escalation ladder** (`escalate.py`): known fix, then a diagnosis by one model, then a second opinion from another model, each limited to a fixed list of safe fixes. Only then the owner, with what was tried.
4. **Trace triage** (`tracetriage.py`) turns the activity feed and failed videos into ranked, de-duplicated problem families; recurring ones become tasks and lessons.
5. **Evaluation** (`agenteval.py`): structural and behavioural checks (an agent never publishes, deletes, goes over budget or edits a public video) run daily and in the test suite.
Agents talk through one inbox (`agentbus.py`): who asked whom to do what, status, outcome.

## New agent: Channel Guardian (`guardian.py`, hourly after recheck)
Reads: policy page changes (`newswatch.policy_watch` result), safety check, YouTube login/Risks rows at "act", the deterministic audits of every waiting or scheduled video (metadata limits, search phrase, thumbnail text).
Acts (only these): fix title/description/tags/thumbnail of a video that is NOT public yet; hold a scheduled video with a content problem (private on YouTube, existing `controls.hold`); **reissue** it (back to a draft so Autopilot repairs, re-checks, schedules and uploads a new private copy; the old private copy stays for the owner to delete); post a task or tell the owner.
Never: make anything public, delete anything, edit a public video's content, change channel settings. A public video is only watched; its title may change only through the title test (owner's mode switch, before/after views, automatic revert). That is how views and likes stay as they were.

## Steps
A playbooks + loader; B lessons; C bus; D escalation; E guardian + reissue; F trace triage; G evaluation; H wiring (SEO prompt, worker jobs, CLI, Risks row); I skills for Claude sessions (trainer, review+eval, triage, guardian); J full suite, commit, deploy.

## Plan review (second research pass)
- *Models from MCP servers*: those servers exist only in Claude Code sessions; the always-on worker cannot call them. The ladder uses the OpenRouter roles the worker already has (review, script, cheap), so a second opinion comes from a different model.
- *A video file cannot be replaced on YouTube*: a content fix means a new upload. Reissue keeps the old id as `superseded_video_id`, clears the upload marks (so the duplicate guard does not mistake the old copy for an interrupted upload) and never deletes.
- *Money*: one ladder case per run, at most 2 model calls per case, charged to the video (`llm.cost_scope`), skipped when the day's cap or credit is low.
- *Loops*: a problem family gets 2 ladder attempts, then waits for the owner; a video gets 1 reissue.
- *Untrusted text*: lessons, rival titles, page diffs and feed text are cleaned with `seo.plain`/`seo.linky` and capped before any prompt; they are data.
- *Owner switches stay owner's*: `titletest` mode (apply), `human_approval`, public/private. The code never flips them.
- *Concurrent session*: `fixer.py` is not edited; the guardian and the ladder call its public functions.
- Limits: a ladder fix is a try, not a proof; a model can diagnose wrongly; evaluation proves the rules hold on test cases, not that every future problem is solved.

## Stage 2: every agent, and the doctor (26 Oct 2026)
- **Every agent trained**: `agents.py` registers 23 agents (autopilot, research, growth, news, creator, clipper, seo, qa, compliance, reviewer, fixer, publisher, recheck, titletest, guardian, health, reporter, monetization, backup, triage, trainer, evaluator, doctor). Each has a playbook; `llm.chat` puts the acting agent's role and limits (650 characters) in front of every model call made under its command or Autopilot action.
- **Doctor** (`doctor.py`, every 6 hours): the "agent that fixes agents". Researched against the request: what is built is the safe part of it.
  - Finds problems: stale (no run for 2.5 periods) or failing (2 failed runs in a row) agents; dashboard not answering; missing setup.
  - Fixes: only the registered job again (never autopilot, never during a render), file permissions, missing folders, through the escalation ladder with two model opinions (OpenRouter roles; MCP servers exist only in Claude sessions).
  - Learns: every attempt is a lesson; post-mortems and skill drafts are written to `data/agent/proposals/`.
  - Not built, on purpose: installing software (supply-chain rule, and the container has no rights), putting a skill into service by itself (`vetskill.py` then `extend.py add` stay the owner's), a browser on the worker (none installed; browser checks are done in a Claude session), changing playbooks or code by itself.
- **Checks**: 14 behaviour cases in `agenteval.py` (the doctor never restarts the main loop or runs a job during a render, writes only proposals, drafts skills only in quarantine with a safe name; the registry lines up; the scope injection is capped and once), each mutation-checked.
