# Safe growth: upload pace, policy watch, publish health, anti-template checks

**Goal:** Grow fast without a strike, a demonetisation or a locked account. The owner asked for the right daily pace, an updated YouTube security/policy research agent, and automation that prevents blocks.

## Research (2026-10-20, sources in the chat reply)
- No official posts-per-day number exists. Sources agree: 1 Short a day is a strong steady pace, 2 is the ceiling, above ~3 quality drops. Metricool (800k videos): ~5 Shorts a month already lifted long-form views 46%; 35+ a month lost that lift.
- YouTube "inauthentic content" (renamed 2025-07-15) is judged on the **pattern across recent uploads**, channel-wide. AI voice and faceless are allowed; templated, interchangeable, repetitive output is not. Hashtags: more than 15 and YouTube ignores all of them.
- API (official page, checked today): `videos.insert` costs 1 unit in its own bucket, 100 calls/day. Uploads from unverified projects are **not** forced private any more. "Certain uploads might default to private based on creator account settings", so a scheduled video can still stay private: we must verify it went public.
- OAuth app in **Testing** status: refresh tokens die after 7 days, uploads stop silently. Publishing the consent screen fixes it (owner action).
- Disclosure: realistic AI-made scenes need the altered/synthetic label; AI scripts and voice-over are exempt. We keep `containsSyntheticMedia: true` and the "Narration is AI-generated" line: over-disclosing is the safe side.

## Changes
1. **Pace.** `MAX_UPLOADS_PER_DAY` 5 → 2 (1 Short + 1 documentary). Dashboard limits for `uploads_per_day` and `shorts_per_day` 1 to 2. Shorts publish daily (7 slots), documentaries stay at 3 a week.
2. **`safety.py` (new)**
   - `check(now)`: after a video's publish time, ask YouTube (`videos.list`, 1 unit per 50) whether it is public, processed, not rejected (copyright claim, duplicate, terms) and not region-blocked. Stored in `meta["health"]`. On a problem: turn Autopilot off, post an error to the feed with a desktop notification. An expired login (`RefreshError`) is reported in plain English.
   - `local_audit()`: secret files are mode 600, ignored by git, not tracked, token scopes are only upload + readonly, a refresh token exists. `fix_permissions()` repairs modes. `upload.py` writes the token as 600.
3. **`newswatch.py` (the security/policy research agent)**
   - `policy_watch()` daily: reads 8 official policy and API pages, keeps their sentences, reports added/removed sentences (first run is the baseline). Written to `data/newswatch/policy_log.json`, to the feed, and into the weekly digest as items.
   - Weekly digest also carries the self-audit result; relevance filter learns the policy words (inauthentic, reused, quota, disclosure, strike).
4. **`reviewer.py` anti-template checks**: opening line too like another video (needs a human), title pattern repeated (warn), more than 15 hashtags (block), shouting title (warn).
5. **Worker + CLI**: `run.py health`, `run.py policywatch`, `run.py safety`; worker jobs `health` (hourly) and `policywatch` (daily 06:10 UTC).
6. **Docs/UI text**: dashboard rule text, skill, README say 2 a day.

## Not done on purpose
- Autopilot stays OFF and nothing is pushed or redeployed: the owner decides when.
- No auto-rewrite of rules from policy changes: the agent reports, a human reads (a wrong auto-edit is worse than a late one).
- Cannot be checked from code: OAuth consent screen status (owner sets "In production"), phone verification of the channel.
