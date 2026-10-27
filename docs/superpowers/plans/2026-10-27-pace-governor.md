# Pace governor: Autopilot follows YouTube's inauthentic-content rule

**Goal:** Autopilot reads the same risk the Risks card shows and changes how many videos it makes and schedules, instead of only holding Shorts at "watch".

**Spec:** research below (27 Oct 2026). **Tech:** Python, pytest, existing `risk.py`, `planner.py`, `autopilot.py`, `agenteval.py`.

## What the research says (and does not say)
- YouTube's monetization page (read 27 Oct via a page reader, not a lawyer): "repetitious content" was renamed "inauthentic content" on 15 Jul 2025. Not allowed to earn: content that looks made from a template, feels repetitive after several videos, or is mass-produced; slideshows or AI content on generic templates with little narrative or value. Allowed: shared intros/outros, series where each video has a distinct focus or storyline.
- Review is for the channel as a whole: main theme, most-viewed and newest videos, biggest share of watch time, titles, thumbnails, descriptions, About section.
- Spam policy: no numeric upload limit anywhere. It bans using tools or AI to make high volumes of similar content with minimal changes, and applies to unlisted and private videos too. Warning, then strike (3 in 90 days = termination).
- So there is NO official "safe number". Safety comes from variety and value; volume only matters through sameness. Our numbers below are our own judgement, not YouTube's.

## What the system did wrong (measured on the server, 27 Oct)
1. The Risks card said "14 videos in a 7-day window" but counted 7 days back plus 7 days ahead (a 14-day span). The label lied.
2. The configured pace (1 documentary + 1 Short a day = 14 a week) sat above the card's own "watch at 10", so the card could never be green, and "act at 15" was one video away from freezing the channel.
3. At "watch" Autopilot held back new Shorts, the cheapest format and about 80% of this channel's views, and left the daily documentaries (the templated format) running.
4. Nothing looked at topic concentration (many videos on one theme), which YouTube's reviewers look at.

## Design
`governor.py`, one file, pure functions, no model calls, no cost:
- `window_load(videos, now)`: the busiest true 7-day span by publish time (publish_at, else uploaded_at), held videos ignored. Used by the Risks card too, so card and Autopilot agree.
- `caps(vs, now, base)`: weekly caps per format. Base 3 documentaries and 7 Shorts (10 a week; owner can change `governor.base`). Tighten only: shared structure >= 60% of last 8 -> documentaries -1; any near-identical openings -> both -1; one theme in >= 50% of last 8 -> both -1; repetition at "act" level -> 0 new. Floor 1 unless frozen. Never above the base: raising it is the owner's choice.
- `allowed(videos, fmt, at, caps)`: true if one more video of that format at `at` keeps every 7-day window containing `at` within the cap.
- Hooks: `planner.rows` marks a slot "paused" when not allowed (nothing fills it, so `needs` makes nothing for it); `autopilot.do_schedule` skips slots that are not allowed; `risk.pattern` uses `window_load` and thresholds watch > 10, act > 13.
- `data/governor.json` records level, caps and reasons; one plain activity-feed notice when the caps change.
- Switch: `governor.enabled` in `autopilot.json` (default on). Videos already scheduled or uploaded, reviews, repairs and uploads are never touched.

## Tasks
1. `tests/test_governor.py` first (window_load, caps tighten-only, allowed, theme share), then `governor.py`.
2. Hooks in `planner.py`, `autopilot.py` (DEFAULTS, governed config, do_schedule), `risk.py`; tests in `test_planner.py`, `test_risk.py`.
3. Playbook section in `playbooks/autopilot.md`, `agenteval` case plus mutation check, CLAUDE.md and docs/AUTOPILOT.md.
4. Full suite, `deploy/clean_check.sh`, dry-run deploy, read back on the server.

## Review focus (inputs the spec does not name)
- Empty data folder or fewer than 4 videos: no tightening, base caps.
- A video with no publish time or no format: ignored, never crashes.
- Governor file unreadable or `governor` key missing in an old `autopilot.json`: Autopilot works as before.
- A Short clipped from a documentary shares its theme: counts once per format, not as repetition against its own source.
