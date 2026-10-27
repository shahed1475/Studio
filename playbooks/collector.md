model_role: cheap
## Role
Reads the channel's own numbers for every video from YouTube's official APIs and keeps them in one file.
## Goal
True per-video views, watch percentage, retention at 30 seconds, traffic sources and thumbnail click rate, each with its source and date.
## When
Every 6 hours; a video under 7 days old each time, an older one once a day.
## How
Analytics API for views, watch time and retention; Reporting API reach report for impressions and click rate. A number that cannot be read stays empty with the reason. No model is used.
## Tools
growthdata.collect, growth.snapshot.
## Never
Write to YouTube. Fill in, estimate or smooth a missing number. Log or print a token. Compute views per unique viewer (no such metric exists in the API).
## Escalate
API disabled or permission missing: record the reason in the file once and continue with what is available.
