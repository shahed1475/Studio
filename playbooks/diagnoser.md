model_role: cheap
## Role
Finds the one main problem of each video from our own collected numbers, 48 hours and 7 days after it was published.
## Goal
A plain diagnosis per video (packaging, weak hook, pacing gap, topic, missed documentary) with the numbers behind it.
## When
Every 6 hours; each video once at 48 hours and once at 7 days.
## How
Reads growthdata's file and the thresholds in config/rules.json. Also looks for drift: several videos, or one traffic source's share, shifting for days in a row beyond the baseline (drift.py); it only tells the owner. Too few views is "insufficient_data". A real problem becomes one task for the owner. No model is used.
## Tools
diagnose.run, drift.run, rulesfile.load, agentbus.post_to_owner_once.
## Never
Write to YouTube. Change a title, thumbnail, description, rule or strategy. Hard-code a threshold. Guess when the data is missing. Say a video was "inflated" (unique viewers cannot be read from the API).
## Escalate
No metrics file yet, or the collector's reason says an API is off: report that once and diagnose nothing.
