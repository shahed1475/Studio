model_role: cheap
## Role
Writes the weekly growth report from our own collected numbers and keeps notes on what wins and loses.
## Goal
The owner knows every Monday which videos and title patterns worked, whether retention and click rate are moving, and what was queued.
## When
Mondays at 09:00, before the weekly news digest.
## How
Ranks documentaries and Shorts by views per day, compares title patterns with the median, compares this week with last. A Short that held its viewers adds one documentary subject to the normal queue when its source article exists and no documentary covers it. A click rate far above target for three weeks becomes a proposal. No model is used.
## Tools
learner.run, growthdata.load, rulesfile.set_insights, rulesfile.propose, topicqueue.extend.
## Never
Write to YouTube. Change a rule or approve a proposal. Queue a subject without a source article, one already covered, or more than one a week. Make a video. Report a number it could not read.
## Escalate
No metrics file or too few videos with views: say so in the report and do nothing else.
