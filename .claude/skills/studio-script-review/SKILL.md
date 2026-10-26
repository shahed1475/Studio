---
name: studio-script-review
description: "Use when a script was held before voice and pictures, the same script rule keeps holding scripts, or the script reviewer (scriptreview.py) needs changing: what it checks, what it may fix, how the doctor is told."
---

# Script review agent
1. **What it is**: `scriptreview.py`, playbook `playbooks/scriptreview.md`. It reads a finished script before any voice or picture is paid for. Facts belong to the fact-checker (`scriptgen.verify_and_revise`, the reviewer), not here.
2. **Rules (free)**: `rows()` checks length, narrated labels, speakable text (links, markup, symbols), ending, quotations against the source, openings, stock phrases, certainty words, Short hook, specifics, template overlap. A block row holds the script; a warn row means `revise` (nothing stops).
3. **Safe fixes only**: `safe_fixes()` cuts labels, links and markup. Facts and quotations are never rewritten here: a held script goes back to the writer (`run.py _script_gate` raises, the loop asks again, `data` is cleared so a held script is never produced).
4. **Model read** (`--llm`, off in the gate, costs money): adds warnings only. A script is never held or passed by a model; a model that cannot answer is `unreviewed`.
5. **Run it**: `python run.py script-review <slug> [--llm]`.
6. **Doctor link**: three holds in a row, or a silent model three times, post one `agent_problem` task to the doctor (`agentbus`). The doctor (`doctor.handle_inbox`) reviews the saved held scripts again (`recheck_held`); if a rule fix cured them the task is closed, otherwise a post-mortem is written and the owner is told. The Agents row of the Risks card shows the reviewer's state.
7. **Changing a rule**: add a test in `tests/test_scriptreview.py`, keep the agenteval cases passing, and break the rule on purpose to see a case fail.
## Limits
Rules find mechanical faults; they cannot tell a good story from a flat one. A pass is evidence the script has none of the listed faults, not that it is true or good.
