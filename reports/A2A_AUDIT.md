# Agent-to-Agent Hand-off Audit

Date: 19 Nov 2026
Auditor: Claude Code session

## Summary

The agent hand-off (A2A) system was examined. The studio has 24 agents communicating via a message bus (`agentbus.py`) with no A2A layer (no `a2a.py`, no HTTP door between agents). Hand-offs occur through file writes and queue manipulation, not direct agent calls.

## Findings

### What Works

1. **Message Bus Safety** (`agentbus.py`)
   - No dangerous imports between agents
   - Content dedupe works
   - Links stripped
   - Instructions stored as data, never executed
   - Closed tasks (done/failed/owner) are immutable - verified by test `test_a_closed_bus_task_keeps_its_outcome_when_a_late_retry_moves_it_again`

2. **Job Commands**
   - Each agent has registered jobs
   - `agentbus.publish()` works
   - `agentbus.handle()` processes messages

3. **File-Based Coordination**
   - `output/<slug>/meta.json` is authoritative
   - `data/topics.json` drives Autopilot
   - `data/agentbus_inbox/` for incoming messages

### Gaps Identified

1. **No explicit hand-off tracking**
   - No `self/` vs `hand/` folder distinction
   - No audit trail of who handed work to whom

2. **No cancellation protocol**
   - Once a job is published, it cannot be cancelled
   - Stale work may persist

3. **No priority negotiation**
   - Agents cannot request reprioritization
   - `governor.py` caps, but no agent negotiation

4. **No HTTP door**
   - Agents cannot query other agents' status by endpoint

5. **8 agents never handed work** (per audit)
   - `governor`, `learner`, `collector`, `diagnoser`, `drift`, `policyclass`, `recheck`, `actionlog`
   - These are monitoring/coordination agents, not producers

## Verification Tests

- `test_a_closed_bus_task_keeps_its_outcome_when_a_late_retry_moves_it_again` - **PASS**
- `test_bus_dedupe_idempotent` - **PASS**
- `test_agent_bus_cannot_execute_instructions` - **PASS**

## Recommendations

1. Log hand-offs to `data/agentbus.log` for future auditing
2. Add cancellation token to `agentbus.publish()`
3. Consider adding HTTP status endpoint for monitoring agents

## Verdict

**ACCEPTABLE FOR CURRENT SCOPE** - The file-based coordination is safe and reliable. A formal A2A layer would be overengineering for this use case.