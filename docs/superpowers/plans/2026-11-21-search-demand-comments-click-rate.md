# Search demand, comment insights and click rate, free (21 Nov 2026)

Owner's order (21 Nov 2026, after reading the vidIQ MCP repo): build the vidIQ features the studio lacks, free, in this order: 1 search demand, 6 comment insights, 9 click rate. Research first, then build step by step with tests, then test in a browser.

## Research (what is allowed and what already exists)

| Source | Status (checked 21 Nov 2026) | Decision |
|---|---|---|
| YouTube autocomplete `suggestqueries.google.com/complete/search?client=youtube&ds=yt` | already used by `seo.suggest`, `seo.demand` (0 to 1) and `seo.keywords`; the host has no robots.txt (HTTP 404), so no machine-readable rule forbids it; unofficial, may stop | keep, cached 7 days, a pause between calls |
| Google Trends | robots.txt disallows `/explore?` and `/trends/explore?`; the official Google Trends API is an application-only alpha (Google Search Central, 24 Jul 2025); pytrends is archived | not used |
| Wikimedia pageviews `wikimedia.org/api/rest_v1/metrics/pageviews/per-article/...` | official, documented, free; asks for a descriptive User-Agent (Wikimedia API access policy); answered for Codex_Gigas (about 1,150 views a day) | the free "Trends": daily interest in the topic's own source article |
| YouTube Data API `search.list` (100 units) + `videos.list` / `channels.list` (1 unit) | already used by `seo.competitors` (cached 7 days) | proven demand and competition, for a few top topics a day only |
| YouTube Data API `commentThreads.list` (1 unit a page) | Developer Policies III.E.4: authorized data no longer than 30 calendar days, non-authorized data (other channels) only "limited amounts" and "not longer than 30 calendar days"; comment text is under the 30-day rule (derived metrics policy) | store questions only, no author names, everything older than 30 days deleted |
| YouTube Reporting API `channel_reach_basic_a1` | ALREADY enabled and working: 65 reports read, 27 of 30 videos have impressions and click rate (`data/agent/metrics/videos.json`); the diagnoser uses it (rules: target 4%, retest under 3%, at least 200 impressions) | no new collection; add the channel summary and the effect of title changes |

## 1. Search demand (`searchdemand.py`, research agent)
- `subject(topic)`, `autocomplete(subject)`: suggestions that contain the subject's key words (count 0 to 10, the top phrases cleaned with `seo.plain`, never a link or an instruction-like line).
- `pageviews(title)`: Wikipedia daily views, last 30 days and the 30 before, through the studio's existing Wikipedia User-Agent.
- `youtube(core)`: from `seo.competitors` (cached a week): median and top views of the 10 results, how many are recent, how many small channels beat their size.
- `score(parts)`: 0 to 1, weighted over the parts that answered (autocomplete 0.35, Wikipedia 0.35, YouTube 0.30); the studio's own estimate, never called YouTube's number.
- `value(topic)`: what `topicrank.pop_best` adds (replaces `seo.demand`): cache first, cheap parts only, never YouTube quota, never raises.
- `refresh()`: daily inside `trendwatch.run` (a failure never costs the trend digest): every queued topic gets the cheap parts; the best 5 get the YouTube part (at most 500 quota units a day); saved to `data/research/demand/latest.json`.
- `run.py demand [topic]`, dashboard Autopilot > Research "Search demand".

## 6. Comment insights (`commentinsights.py`, research agent)
- Own channel: `commentThreads.list(allThreadsRelatedToChannelId=<own>)`, 2 pages (2 units). Niche: one page of the top video of up to 6 reference channels (6 units).
- Questions found by fixed rules (a question mark or a question word first), cleaned: links, @names and e-mail addresses removed, instruction-like text dropped, 12 to 240 characters. Author names are never read into the file.
- Grouped by shared subject words; optionally 3 video topics from the top groups by one cheap free-model call (data labelled as data, JSON, any failure = no ideas). Ideas are proposals: the owner adds one with the existing Add button.
- 30-day rule: every row carries its fetch date; `run` and `latest` drop anything older than 30 days.
- Daily inside `channelwatch.run`; `run.py comments`; dashboard Autopilot > Research "What viewers ask".

## 9. Click rate (`growthpage.py`)
- `ctr_summary`: impressions-weighted click rate for the last 28 days and the 28 before, for documentaries and Shorts, the best and weakest videos with at least `min_impressions_for_ctr` impressions, against the rules file's target and retest numbers.
- `title_effects`: for each logged title change of a video that has reach data, the click rate 7 days before and after (only with enough impressions on both sides, otherwise "not enough impressions yet"). Read only; nothing changes on YouTube.
- Dashboard Growth > Overview "Click rate".

## Agent rules (agenteval cases with mutation checks)
- Search demand: a network failure is no signal (0, the topic is never dropped); YouTube searches stay within the daily budget; outside text is cleaned.
- Comments: no author name is stored; nothing older than 30 days is kept or shown; outside text is cleaned; the agent never posts or replies.

## Tests
Unit tests with fakes for every source (fakes refuse what the real API refuses), dashboard API tests, a real-Chrome test of the new panels, the full suite; then real read-only runs in the worker and a browser check on a secret-free copy.
