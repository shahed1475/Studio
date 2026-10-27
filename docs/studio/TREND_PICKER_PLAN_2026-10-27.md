# Trend picker: choose a trending video, get our own script (plan, 27 Oct 2026)

Owner's request: in the dashboard's Trends view, see trending videos, pick one, and have a script written "how I want". Long videos must not be so long that people get bored. Research the length question and make a plan.

Status: the daily trend scan, reference-channel hits, Studio inbox and the dashboard list are BUILT (see PROGRESS.md, 27 Oct). The pick-a-video form and `trendpick.py` (section 3, items 2 to 4) are NOT built yet and wait for the owner's yes.

## 1. What exists today (checked in the code, 27 Oct)
- Dashboard "Niche trends" panel (`dashboard.html` ~line 614): median views, Shorts share, average long-video length, 8 popular titles with links, "topic ideas to review". Read-only: no button to make a video from a row.
- `trendwatch.search_fresh` (YouTube Data API, public numbers): videos from the last 14 days scored by views per day against the channel's size, docs and Shorts separately. It had never run on the server until 27 Oct; the result (12 docs, 12 Shorts) is in the weekly digest under `fresh` but is not shown in the dashboard.
- `topicrank.signals` already gives such videos up to double weight when a queued topic matches them (Lost Army of Cambyses scored 9.08).
- The YouTube Studio "Trends" tab has no API and is not read by Autopilot (decision in TREND_AND_TRAINING_2026-10-27.md, section 1). This plan uses the public API list instead. If the owner means that Studio tab, an assistant session can read it and queue topics by hand.
- Length rules already in code: documentary planned as 6 to 8 minutes (`scriptgen` prompt), capped by `MAX_DOC_LINES` at about 8 minutes at 140 words a minute (set after La Llorona ran 9:44 and lost viewers and picture quality); Short 10 to 12 lines, 110 to 135 words, about a minute.

## 2. Research: how long should a long video be?
- No official answer. YouTube Help describes the audience retention report and "average percentage viewed" and compares each video with the channel's last 10 videos of similar length; it gives no ideal runtime. Its advice for early drop-off is a title and thumbnail that match the content.
- Published guides (VidIQ, Teleprompter, Stack Influence, 2026) say the same: no single best length, match the goal, check your own retention; common ranges quoted are 7 to 15 minutes for explainers; videos of 8 minutes or more can carry mid-roll ads. These are blog guidance, not YouTube policy, and none gave documentary-specific retention numbers.
- Our own numbers (Studio, 28 days to 25 Oct): Shorts keep 50 to 68% of viewers (Skinwalker 21%); documentaries get 25 to 591 impressions at 1.5 to 2.8% click rate. Too few views per documentary to read a retention curve.
- Fresh trend digest (27 Oct): typical length of what is taking off is 14.7 minutes for documentaries, but the list is dominated by multi-hour "history for sleep" compilations and a few 12 to 17 minute mystery videos; that hint mixes two different products and is not a target for us.
- Conclusion (our judgement): keep 6 to 8 minutes as the default, hard ceiling 10 minutes. This channel has 6 subscribers and no retention data that supports longer. A video ends when its story ends; a thin story is made a Short, not stretched. Revisit when a documentary has about 1,000 views: if its average percentage viewed is above 50% at 8 minutes, test 10 to 12 on the next one.

## 3. Design
1. Show the fresh list in the Trends panel: title, channel, subscribers, age, length, views per day, outlier score (docs and Shorts tabs), with a plain note that it is public numbers only.
2. A "Make from this" button on each row opens a small form (all owner-controlled):
   - format: Short or documentary (default by the source video's length),
   - your angle, free text ("explain it as what is documented versus legend", "calm bedtime tone"),
   - length: Short about 1 minute; documentary 6, 8 or 10 minutes (default 7, ceiling 10),
   - a cost line before anything is spent (Short about $0.3, documentary about $1 to $1.3) and the credit left.
3. `trendpick.py` (new, small): from the row it takes only the public title, channel and numbers. It never downloads the video, never reads its transcript and never copies its wording or structure. It reduces the title to a subject (`topicqueue.subject_of`), then requires the same gates as any topic: a real Wikipedia source article, the premise screen, `duplicates.topic_conflict`, the pace governor, and credit at least the Autopilot floor ($1.50). If no source article exists it says so and makes nothing (no invented facts).
4. The pick is stored as a brief `{topic, format, angle, minutes, picked_from_url}` in a new queue file and pinned for that format. `scriptgen` receives the angle as the owner's instruction (trusted) and the sources as data; the length goes into the prompt and into the existing `MAX_DOC_LINES` cap.
5. The script then goes through the normal chain: fact-check and rewrite before voice or pictures, script review, reviewer, picture check, review window, private scheduled upload. Nothing is made public by this feature.
6. Length guard: the script reviewer warns above the chosen minutes; above the ceiling the script is cut by chapter or the story is turned into a Short.
7. Retention feedback: after a documentary has views, record its average percentage viewed beside its length (owner reads it from Studio until the API scope exists) so the next length decision uses data.

## 4. Safety and platform risk
- Originality: our video retells a story from open sources in our own words and structure. It must not copy the picked video's script, title wording, thumbnail or order of points. The picked video's URL is kept only as the reason we chose the topic.
- Reused-content / inauthentic-content policy: same story as another channel is normal; same wording is not. The copied-wording check (`compliance.py`) already runs on every video.
- Sameness: the pace governor and "one story, one video per format" still apply, so many picks cannot flood the channel.
- Money: a pick never bypasses the daily cap, the per-video limit ($2.50 documentary, $0.70 Short) or the credit floor.
- Untrusted input: titles and channel names from YouTube are shown as data and never followed as instructions.

## 5. Work list
1. `trendpick.py` plus tests (gates refuse: no article, duplicate story, low credit, over-long request).
2. Dashboard: fresh list and the form; endpoint behind the login; job runs through the existing worker queue.
3. `scriptgen`: accept `angle` and `minutes` (default unchanged for Autopilot, so existing output does not change).
4. Playbook line for the scriptwriter and the script reviewer, a new `agenteval` case with a mutation check (rules in CLAUDE.md).
5. Full test run, deploy with `deploy/deploy.sh dry-run-first`, never while a render runs, then one real Short as proof and one look at its frames.

## 6. What stays unverified
- Whether trend-led topics raise views for a 6-subscriber channel (the 14-day outlier list is a lead, not proof).
- The right documentary length for this audience until retention data exists.
- Competitor view counts are as the API reported on 27 Oct.

## Owner decisions
- Yes to build section 5.
- Confirm "Trends" means our dashboard's Niche trends panel (public API list) and not the YouTube Studio Trends tab.
- Documentary default 7 minutes and ceiling 10, or shorter?
