# Free growth tools: search demand, what viewers ask, click rate (21 Nov 2026)

Owner's order: build the vidIQ features the studio lacked, free, in the order 1, 6, 9; research, plan, build, test in a browser. Plan and research: `docs/superpowers/plans/2026-11-21-search-demand-comments-click-rate.md`.

## What was built
| # | Feature | Where | State |
|---|---|---|---|
| 1 | Search demand: YouTube autocomplete, Wikipedia pageviews, top YouTube results (best 5 a day), the studio's own 0-100 score | `searchdemand.py`, `topicrank.pop_best`, daily in `trendwatch.run`, `run.py demand`, Autopilot > Research "Search demand" | working on live data (37 topics) |
| 6 | What viewers ask: questions from public comments (ours, top video of 6 reference channels), no names, 30 days at most, never replies | `commentinsights.py`, daily in `channelwatch.run`, `run.py comments`, Autopilot > Research "What viewers ask", Settings "YouTube Data API key" | built; reading waits for the owner's free API key |
| 9 | Click rate: last 28 days vs the 28 before, documentaries and Shorts, best and weakest, before/after a title change | `growthpage.ctr_summary`, `title_effects`, Growth > Overview "Click rate" | working on live data |

## Evidence (real data, 21 Nov 2026)
- Demand: Roanoke 89, Banshee 88, Cú Chulainn 84, Mohenjo-daro 84 (Wikipedia: Roanoke Colony about 2,541 views a day). YouTube searches: 5 a refresh, 500 units.
- Comments: Google answered "Request had insufficient authentication scopes" (`insufficientPermissions`) for the studio's login (scopes: youtube, youtube.readonly, youtube.upload, yt-analytics.readonly). The panel shows the setup step.
- Click rate: 2.9% over the last 28 days on 7,602 impressions (+0.7 points), documentaries 3.4%, Shorts 2.4%; 11 of 15 judged videos under the 3% retest line; best Mami Wata 7.1%, weakest Kitsune 1.5%.

## Research sources
- Wikimedia API access policy and pageviews API: https://www.mediawiki.org/wiki/Wikimedia_APIs/Access_policy
- Google Trends API (alpha, application only): https://developers.google.com/search/blog/2025/07/trends-api ; trends.google.com/robots.txt disallows /explore? and /trends/explore?
- YouTube API Services Developer Policies (III.E.4, 30 calendar days): https://developers.google.com/youtube/terms/developer-policies
- Reporting API reach reports (channel_reach_basic_a1): https://developers.google.com/youtube/reporting/v1/reports/channel_reports
- suggestqueries.google.com/robots.txt: HTTP 404 (no rule); the endpoint is unofficial and can stop working.

## Tests
- `tests/test_searchdemand.py` (19), `tests/test_commentinsights.py` (13), `tests/test_ctr_summary.py` (10), `tests/test_research_panels.py` (5, real Chrome).
- Agent evaluation: 72 of 72, with new cases for search demand and comment insights, three mutation checks each.
- Full suite: 2,859 passed, 0 failed, 11 skipped (the same 11 as before).
- Button audit on a secret-free copy (`tools/dashboard_button_audit.py`): 199 controls work, 0 errors, no sideways scroll at 360 and 412 px; screenshots looked at for all three panels.

## Fixed on the way (found by tests or live data)
- A demand reading kept a new date when a part was added (a week-old reading could live longer).
- A long title with no autocomplete suggestion was treated as "source down"; now it is 0 hits after a retry with its key words.
- Off-topic suggestions (a film, game or song of the same name) no longer count; a year in the subject itself is kept.
- One malformed video record could take the Growth page down.
- The daily behaviour evaluation would have used a key the owner saves; it now passes its own fake reader.

## Limits
- Autocomplete counts any use of a name ("The Banshees of Inisherin" counts for Banshee); a filter catches film, game and song words only.
- The score is the studio's estimate, not a YouTube or Google number, and is advice, not proof of views.
- The before/after view for title changes is empty: the real action log was lost with the VPS, and its 97 "V2" rows are test leftovers of 29 Oct.
- Comment reading is not proven end to end until the owner saves a key.

## Waiting for the owner
1. Create a free YouTube Data API key (Google Cloud Console > APIs & Services > Credentials > Create credentials > API key, restrict to YouTube Data API v3) and paste it in Settings > YouTube Data API key.
2. Whether to push these commits to GitHub.
