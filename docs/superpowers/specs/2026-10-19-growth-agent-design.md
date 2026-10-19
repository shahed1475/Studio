# Growth Agent: design

## What the owner asked for (restated in plain English)
A research agent that works on its own, every day, and that the owner checks from the dashboard. It must:
1. Always study how our channel is growing (subscribers, views, which videos work).
2. Find competitor channels by itself (no pasted IDs), next to the 5 the owner added by hand.
3. Study those competitors and turn the findings into a **growth strategy**: what to make, how to title it, how to edit it, when to publish.
4. Pass the findings to the next steps of the pipeline (queue and edit settings), so the videos get made with them.
5. Have **two modes**: *Automatic* (the agent applies safe changes itself) and *Hand-off* (the agent only proposes; the owner clicks Apply).
6. Show everything it does: an activity feed on the dashboard, an unread badge, and a desktop notification for important events.

## Why
Views are the goal. The owner is not a native English speaker and wants one place to see what the agent learned and decided, without reading code or logs.

## Goals
- One daily run, hands-off, safe to re-run. Records every step in a feed the owner can read in plain English.
- Own-channel snapshot, competitor discovery, competitor study, strategy list with evidence.
- Modes `off`, `handoff` (default), `automatic`, switchable from the dashboard.
- Applied strategies actually change the pipeline: the topic queue and the edit profile (loudness, pause between sentences).

## Non-goals and anti-goals
- Never download, copy or re-upload another creator's video, script or thumbnail (copyright, YouTube reused-content policy). Research reads public metadata only, through the official YouTube Data API.
- Never turn Autopilot on, change upload limits, or publish anything. Every video still passes the reviewer and, where flagged, the owner. Max 5 uploads a day stays.
- Not built now: YouTube Analytics (retention, click-through). It needs a new Google permission; the plan leaves a clear place for it.
- A strategy the agent cannot back with evidence from data must not be shown as fact.

## Constraints
- Python, same style as the repo. No new dependencies. The model router `llm.py` (OpenRouter with local Ollama fallback and daily cap) does all model calls.
- YouTube API quota: at most 6 channel searches (600 units) and about 40 other units per daily run.
- Dashboard text: plain words, no em-dashes.

## Decisions made by the builder (owner can change)
- Default mode is `handoff`. Automatic applies only `edit` strategies (validated numbers within fixed limits) and `topic` strategies (added to the queue; the reviewer and Needs-you gate still apply). Titles, formats, schedule and thumbnails are advice only.
- Discovered competitors live in their own list (max 15), separate from the owner's 5 hand-picked channels.
- Desktop notifications use `notify-send` when it exists; the feed and badge always work.
