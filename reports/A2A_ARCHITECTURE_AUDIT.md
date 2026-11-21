# A2A architecture audit (2026-11-20)

## What existed before today (inspected)
- **Registry:** `agents.py`, 27 agents, each with its job, commands and hand-over list (`hands_to`). Every agent has a playbook (`playbooks/<agent>.md`, `playbook.load`). `playbook.acting_as` puts the acting agent's role and limits into every model call it makes.
- **Message bus:** `agentbus.py` (`data/agent/tasks.json`):
  - `post`, `claim`, `finish`, `to_owner`, with states open, working, done, failed and owner.
  - One live task per kind, target and video, so a repeat is a duplicate and not posted again.
  - A file lock, history per task, the last 400 kept.
  - A closed task keeps its outcome (the live edit of 20 Nov).
- **Escalation and repair:** `escalate.py` (whitelisted safe fixes), `fixer.py`, `unstick.py`, `doctor.py` (inbox handling, post-mortems).
- **Planned, never built:** `a2a.py` (plan `docs/superpowers/plans/2026-11-17-free-quality-pipeline.md`, Task 7). The unmerged `hub/a2a.py` is on branch `feature/hub` and was not used (that plan requires a security review first).

**Mapping of the roles the owner listed** to the existing agents (no duplicates created):

| Role asked for | Existing agent or stage |
|---|---|
| Research Agent | `research` |
| Script Agent | `creator` (`scriptgen`) |
| Fact-Check Agent | `scriptreview`, `scriptgen.verify_and_revise`, `reviewer` claim ledger |
| Voice, Visual and Render | **stages of `creator`** (`run._produce_doc`), not separate agents |
| Review Agent | `reviewer`, `qa`, `compliance` |
| Packaging Agent | `seo` (plus `thumbnail`, `compliance.final_description`) |
| Doctor Agent | `doctor` |
| Orchestrator | `autopilot` |

## What was added (`a2a.py`, about 300 lines, on `agentbus`)
| Requirement | How |
|---|---|
| Discovery and registry | `card(agent)` and `cards()`: an A2A Agent Card per agent (name, Role line, skills from its commands, capabilities, input and output modes, `handsTo`, `acceptsFrom`) |
| Contract per message | `send()` stores `a2a`: expected answer schema (`answer`, `verdict`, `diagnosis`), question, context id (the video), inputs, deadline, timeout and retries left. The bus task id is the A2A task id. |
| Who may talk to whom | `may_message`: never itself; only along `hands_to`; the doctor and autopilot may ask anyone |
| Acknowledgement | `acknowledge()`: only the target, moves the task to working |
| Result delivery and validation | `deliver()`: only the target; the answer is checked against the schema; a wrong answer is asked again while retries are left, then fails with the reason |
| Duplicate message | Same question, target and video gives the same task (a hash of the question in the kind) |
| Duplicate completion | A closed task refuses any later answer ("its outcome stays") |
| Timeout and retry | `expire(now)`: past the deadline, asked again with a new deadline, then failed |
| Cancellation | `cancel()`: only the sender or the doctor |
| Audit log | Every step appended to the task's history in `tasks.json` |
| Untrusted text | `clean()`: links and control characters removed, capped at 1,200 characters, stored as data |
| No owner-only power | No path imports upload, autopilot or safety, and none writes settings. The only kinds are questions, checks and diagnoses (pinned by a test). |
| **Orchestrator checks hand-overs between stages** | `handoff(data, stage)` in `run._produce_doc`, in this order: **script** (lines, chapter starts fit), **voice** (a narration file, one timing per line, all positive), **visuals** (a real file for every line), **render** (the video exists, ffprobe reads it, its length is within 3 s or 5 % of the narration). It raises on a broken result before the next stage. Every hand-over is recorded in the video's record (`handoffs`) with what was measured, and the render check runs **before** the video is registered (`records.save`). |

## Not done, and why
- **Rewriting the pipeline as message-passing agents.** The stages run in one process for one video, in order. Turning each into a separate agent that waits on the bus would rebuild working code, against the owner's "preserve the existing architecture". The checks between stages give the property that matters: the orchestrator verifies real files instead of taking a stage's word.
- **Capped model consults** (`consult()` in the plan: 4 agents, 2 rounds, 8 calls). They need free model calls, and free text generation is rate-limited upstream today (`FREE_MODEL_OPTIMIZATION.md`). The task layer they would use is in place.
- **An HTTP A2A door:** not built. The plan has it off by default; nothing needs it inside one machine.
- **Wiring the fixer, guardian and doctor to `a2a.send`:** they still use `agentbus.post` directly, which `a2a` builds on. Switching them is a small, separate step for each agent (playbook plus an eval case each, per CLAUDE.md).
