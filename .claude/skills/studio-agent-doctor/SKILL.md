---
name: studio-agent-doctor
description: "Use when an agent stopped running, keeps failing, needs a setup step, or the studio needs a new agent or skill: the doctor (doctor.py), the agent registry (agents.py), post-mortems and quarantined skill drafts."
---

# Agent doctor
Every 6 hours (`python run.py doctor`, `python run.py agents` to read the result).
1. **Scan**: each agent with a worker job is compared with its own cadence (`stale` after 2.5 periods) and with the last results in `logs/worker.log` (`failing` after 2 failed runs in a row). `not_yet` = no run recorded, not a fault.
2. **Fix, safe only** (through `escalate.solve`: lessons, then two model opinions, then the owner): run the registered job again (never `autopilot`, never while a render runs), make secret files private, create missing folders. Nothing else.
3. **Write up**: a post-mortem in `data/agent/proposals/`; for a problem family seen 3 or more times a skill draft in `data/agent/proposals/skills/<name>/` scanned with `vetskill`. A draft is NOT installed: the owner runs the two commands in the task (`python vetskill.py <folder>`, `python extend.py add <folder>`).
4. **Setup requests** (inbox, kind `setup_request`, with exact commands): dashboard not answering, no model key, YouTube edit permission missing in apply mode, no off-server backup.
## Adding an agent
Add it to `agents.py` (job or commands, who it hands work to), a playbook in `playbooks/`, a case in `agenteval.py`; `agents.problems()` must be empty. Model calls made under its command or Autopilot action carry its role and limits automatically (`playbook.acting_as`).
## Limits
It installs nothing, drives no browser (the worker has none; use the browser tools in a Claude session to look at the dashboard), and uses only the model roles the worker has through OpenRouter. MCP servers exist only in Claude Code sessions.
