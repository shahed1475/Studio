# Studio Agent Doctor Evaluation

Date: 19 Nov 2026
Auditor: Doctor agent (`doctor.py`)
Executed: `python run.py doctor`

## Live Doctor Status

```
$ python run.py doctor
16 agents checked, unhealthy: none
Fixed: 0
For the owner: 0
Setup items missing: off-server backup
Skill drafts: 0
```

**Status: HEALTHY**

## Agent Health Matrix

| Agent | Status | Notes |
|---|---|---|
| researcher | ok | Active, no issues |
| writer | ok | Active, no issues |
| voicer | ok | Active, no issues |
| illustrator | ok | Active, no issues |
| animator | ok | Active, no issues |
| render | ok | Active, no issues |
| reviewer | ok | Active, no issues |
| fixer | ok | Active, no issues |
| guardian | ok | Active, no issues |
| uploader | ok | Active, no issues |
| governor | ok | Monitoring agent |
| learner | ok | Monitoring agent |
| collector | ok | Monitoring agent |
| diagnoser | ok | Monitoring agent |
| drift | ok | Monitoring agent |
| policyclass | ok | Monitoring agent |

## Missing Setup Items

1. **Off-Server Backup** (HIGH PRIORITY)
   - Current backup strategy: nightly snapshots to `backups/`
   - Missing: off-site replication (cloud storage or remote server)
   - Recommendation: Configure rclone to sync `backups/` to cloud storage

## Pending Recommendations (from Doctor)

None - all systems nominal.

## Doctor's Capabilities

The `doctor.py` script runs every 6 hours and:
- Identifies stale/failing agents
- Fixes safely: registered jobs reappear, file permissions corrected
- Writes post-mortems for persistent issues
- Lists missing setup items
- Installs nothing automatically

## Health Trend

No recurring failures observed in this session. The most recent run shows all 16 agents healthy with no setup issues requiring immediate action beyond the off-server backup recommendation.

## Verdict

**SYSTEM HEALTHY** - All 16 agents operational. Only non-critical setup item missing: off-server backup.