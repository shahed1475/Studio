# A daily plan: how many videos, which topics, what is next

> **For agentic workers:** native execution, tests first, one commit per task, full suite green before each commit.

**Goal:** Autopilot keeps a fixed number of days of videos ready ahead (default 3), prepares only what the plan still lacks, picks the best topic from the research and growth data, finishes each video (repair, review, approve, schedule) before the next, and shows the next videos with their post times.

**Evidence (2026-10-20):**
1. Only 2 videos have a publish time (doc 21 Oct 22:00 UTC, Short 22 Oct 16:30 UTC); four approved Shorts were unscheduled because the tick ended before its scheduling pass; the Short slot of 21 Oct and every later day is empty. Production is driven by "videos waiting", not by empty days.
2. The topic queue holds instructions, not subjects ("Create content around unsolved mysteries", "Focus on…", three Jersey Devil retellings): the growth ideas and `strategy.apply` push text straight into the queue, so videos get made about nothing (Tuckahoe "legend" had none).
3. `run.cmd_doc` takes the first queued topic, so the research and growth data never decide what is made.

## Global Constraints
- Nothing is published or approved by these changes; uploads stay private with a scheduled time. Max 2 uploads a day (config.MAX_UPLOADS_PER_DAY) is unchanged.
- No cache deletion by pattern; no worker restart while a render runs.

## Review Focus
- A queue that is empty or all instructions must not crash production; it asks the research agent for ideas.
- A day already full must not trigger more videos; a day with a repair in progress counts as covered.

### Task 1: Only subjects enter the queue
Files: `topicqueue.py` (`looks_like_topic`, `subject_of`, `clean_queue`), `agent.py` (`queue_ideas` uses `subject_of`), `strategy.py` (`apply` queues a subject or nothing). Tests in `tests/test_topicqueue.py`.
### Task 2: The tick ends with a finishing pass
Files: `autopilot.py` (`tick`): after the repair rounds, run the plan once more with only approve, schedule and upload actions.
### Task 3: The planner
Files: `planner.py` (`upcoming(cfg, now, days)`, `slot_states(cfg, videos, now)`, `needs(cfg, videos, now)`, `sync_ready_folder(videos)`), `autopilot.py` (production driven by `needs`; new config `plan_days_ahead`, default 3), tests `tests/test_planner.py`.
### Task 4: The best topic, not the first
Files: `topicrank.py` (`score(topic, signals)`, `viable(topic, article_text)`, `pop_best(fmt)`), `run.py` (`cmd_doc`, short path use it).
### Task 5: Show it
Files: `dashboard.py` (`/api/autopilot` gains `plan`), `dashboard.html` ("Next videos" section, daily target).
### Task 6: Deploy, clean the queue, run a tick, switch making on, watch the first planned video.
