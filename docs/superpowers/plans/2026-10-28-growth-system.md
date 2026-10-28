# Growth system plan, 28 Oct 2026

Source files (owner's, read in full 28 Oct 2026, copied to `docs/` and **not committed**): `youtube_content_system_prompt.md` (content rules for The Sleeping Library) and `growth_agent_builder_prompt_sonnet.md` (a Growth Agent: collector, diagnoser, fixer, learner, policy watcher, `rules.json`).

Status 28 Oct 2026: approved with all six recommendations and built. Phases 0 to 8 are deployed (module names: `rulesfile.py` not `rules.py`, `growthdata.py`, `diagnose.py`, `secondsources.py` (built, OFF), `actionlog.py`, `policyclass.py`, `drift.py`, `learner.py`, `growthview.py`); phase 9 is the close-out (CLAUDE.md section "Growth system", dashboard Growth panel, Risks card). Still open: the owner enables the Reporting API; a top-up before second sources are switched on and the length minimum is raised. The title test still applies titles to public videos (the owner's 24 Oct switch): logged and reversible, not flipped.

## 1. What the two files ask for

Content prompt: score topics 16/25 (open question, eerie, search demand, source depth, fresh angle); titles 40-60 characters with a curiosity gap and the searchable name first; thumbnails with one subject and 2-4 words; long videos of 8-14 minutes with a cold-open hook, a re-hook every 60-90 s, three labelled theories and a verdict; **two sources beyond Wikipedia and one original element per video**; Shorts of 35-58 s that loop and point to a long video; an SEO package (keyword hook first, curiosity chapters, playlist links, tags, pinned comment); a weekly feedback loop; every number loaded from a versioned `rules.json` that wins over the prompt.

Builder prompt: a TypeScript, Supabase and n8n service that collects metrics (Analytics and Reporting APIs), diagnoses each video 48 h and 7 days after publishing, fixes safely (auto-apply small metadata fixes, ask for titles, thumbnails, deletions and rules), writes a weekly report, watches YouTube's policy pages and the algorithm for drift, and keeps `rules.json` as the single source of truth.

## 2. What the studio already has, and the gaps (checked against the code 28 Oct 2026)

| Spec item | Already in the studio | Gap |
|---|---|---|
| Topic scoring, series | `topicrank` (research and growth signals, source article must exist), `seo.demand`, `duplicates` (one story, one video per format), playlists | No explicit 5-line score; no series as a first-class field |
| Title and thumbnail rules | `packaging.py` (title best 40-62 characters, first 40 characters decide the click, ranked options), `thumbscore`, 3 thumbnails per video | Curiosity-gap check, searchable name in first 3-4 words, banned encyclopedia patterns only partly covered |
| Long-form structure | `scriptgen.doc_script`, `reviewer` (duration 180-900 s, pace 105-175 wpm) | Hook-in-15-s, re-hook gaps of 90 s, three labelled theories, verdict, no outro: not checked. Length range 3-15 min, spec says 8-14. Our last video was 5:40 at 132 wpm |
| Two non-Wikipedia sources, original element | Wikipedia grounding (up to 2 articles), `webcheck` for claims | **Biggest gap.** Every script is Wikipedia only. No second-source step, no "original element" field |
| Shorts | `clipper` (3 per documentary), scripts of 110-135 words, 1 Short a day | 35-58 s check, looping last line, 3-5 per long over the week, "related video" link |
| SEO package | `seo.py`, `packaging.audit`, chapters, tags, CTA, credits | Description order (spec: keyword hook, chapters, links, sources and credits last), pinned comment, translated subtitles, file name |
| Single rules file | Thresholds spread over `packaging.py`, `reviewer.py`, `compliance.RULES`, `governor`, `autopilot.json` | No `rules.json`, no version, no staleness warning |
| Collector | `growth.snapshot` (public Data API numbers), `titletest` (views per day), `safety.ANALYTICS_SCOPE` held by the token (24 Oct) | No retention curve, traffic sources or **CTR** |
| Diagnoser | `titletest.judge`, `recheck` | No per-video diagnosis table, no 48 h and 7 d runs |
| Fixer | `fixer`, `recheck.push_metadata` (apply mode), `guardian` | No before/after log with rollback for every YouTube write; approval flow is the dashboard owner tasks |
| Learner | weekly digest (`newswatch`), `strategy`, `reporter` | Winners and losers not written back to rules |
| Policy watcher | `newswatch.policy_watch` daily 06:10 UTC diff of YouTube rule pages and feeds, `compliance.RULES` with dated sources | Changes do not become `pending_changes`; a high-severity change does not pause auto-publish; no drift detection; Creator Insider and Liaison channels not watched |

## 3. Decisions for the owner

1. **Stack.** The spec says TypeScript, Supabase, n8n. The studio is Python in two Docker containers with state in files, and the n8n connector here fails (404). **Recommendation: build it in Python inside the studio** (no new server, no new bill, same tests, same dashboard). Say if you want the TypeScript service instead.
2. **Writes to YouTube.** The spec auto-applies description, playlist, hashtag and related-video fixes. Our rules say never edit a public video without your word. **Recommendation: auto-apply only to videos not yet public; on public videos, suggest and wait for your approval**, with a before/after log and rollback for every write.
3. **Length and money.** 8-14 minute documentaries cost more (a 6-minute one cost about $1.05 with pictures; 10 minutes is roughly $1.5-1.8). Credit was $1.07 and the daily cap is $3.50. **Recommendation: raise the minimum to 8 minutes only after you top up OpenRouter;** until then keep today's 3-15 range.
4. **Second sources.** Which are acceptable? **Recommendation:** primary or public-domain texts (Wikisource, Internet Archive, museum and archive pages, old newspapers), cited with URL, passage and date in `sources.json`, never quoted beyond a short passage, never behind a paywall or login.
5. **Reporting API.** Real CTR is only available through it (see section 4). **Owner steps:** enable "YouTube Reporting API" in the Google Cloud project, and reconnect YouTube if the token lacks `yt-analytics.readonly`. The job only collects from the day it is created, so this is the first thing to do.
6. **Notifications.** n8n, email and Telegram are replaced by what exists: dashboard owner tasks, the daily report and the one-a-day money message. Say if you want Telegram added.

## 4. Verified facts and what stays unverified

Verified 28 Oct 2026 from Google's own documentation pages (read through a fetch tool, which summarises):
- The **Analytics API** metrics page lists views, watch time, `averageViewPercentage`, `audienceWatchRatio` (retention curve) and `subscribersGained`. It lists **no thumbnail impressions and no CTR**.
- The **Reporting API** has reach reports `channel_reach_basic_a1` and `channel_reach_combined_a1` with `video_thumbnail_impressions` and `video_thumbnail_impressions_ctr`. The report ids in the builder prompt are one version out of date: `channel_basic_a3` and `channel_traffic_source_a3`.
- This corrects the 24 Oct note "impressions and CTR are not in the API": true for the Analytics API, not for the Reporting API.

Unverified, checked before anything depends on it (Phase 2 capability probe, with the page quoted): that a reach job returns data for this channel and how much history; a unique-viewers metric (for the views-per-unique flag); setting a Short's related video, pinning a comment and Test and Compare through the API (the spec assumes all three; I expect some to be Studio-only); the spec's "inauthentic content policy clarified July 2026" (our `compliance.py` has its own dated sources; the spec's claim goes into `rules.json` as unverified until the page is re-read); every channel figure in the spec (CTR, retention, unique viewers), which I cannot see.

## 5. Phases (each: code, tests, an `agenteval` case and a mutation check where an agent changes, a playbook update, a deploy through `studio-deploy`)

0. **Capability probe** (read-only, no spend). Query the Analytics API for retention and traffic sources, create the Reporting job for the two reach reports, record what works. Output: `docs/studio/GROWTH_API_PROBE_2026-10-xx.md` with quoted evidence. Needs decision 5.
1. **`rules.json` and loader** (`rules.py`). Values start equal to today's constants (title 40-62, pace 105-175, duration 180-900, CTR target 4%, retest below 3%, retention at 30 s 40%, Shorts stayed 70%, topic repeat block 30 days, views per unique 3). Policy constraints come from `compliance.RULES`; hard rules (no misleading, disclose synthetic media, no bought engagement, no copying) are constants nothing can override. `pending_changes` apply only on owner approval; a version older than 30 days adds a "rules stale" row to the Risks card. Modules read thresholds from it, one at a time, with a test that no migrated constant is hard-coded.
2. **Collector** (`growthdata.py`). Every 6 hours for videos under 7 days old, daily for older: views, retention at 30 s, average percentage viewed, traffic sources, subscribers gained from the Analytics API, and CTR and impressions from the Reporting reach report. Files under `data/agent/own/`. Every number carries its source and date; a missing metric is stated, never filled in.
3. **Diagnoser** (`diagnose.py`). 48 h and 7 d after publishing, one primary problem per video from `rules.json` thresholds (packaging, broken promise, pacing gap, topic or search, missed long video, inflated views, repetition). Written to the dashboard and to owner tasks; it never writes to YouTube. Mock-API tests for each row of the spec's table.
4. **Generator rules** (playbooks, `scriptgen` prompts, `reviewer` checks). Cold-open hook in 15 s, re-hook gaps over 90 s flagged, three labelled theories, verdict near the end, no outro, curiosity chapter names, description order, Shorts 35-58 s with a looping last line, thumbnail text of 2-4 words that does not repeat the title. Warnings first, blocks only where the rules file says so.
5. **Second sources and the original element.** A research step that finds, reads and cites two non-Wikipedia sources and records an `original_element`, with a reviewer check `sources_beyond_wikipedia`. Cost-capped through `llm.cost_scope`. Needs decision 4.
6. **Fixer and approvals.** Auto-apply (non-public videos only): chapters, description order, playlist, hashtags. Everything else becomes an owner task with Approve and Reject. Every YouTube write gets a before/after record and a rollback command. Depends on decision 2.
7. **Policy watcher upgrade.** A page diff is classified (affects, severity, summary, proposed patch) and written to `rules.pending_changes`; a high-severity change pauses auto-publish and tells you; drift detection (28-day baseline, more than 2 standard deviations for 7 days across several videos) raises an `algorithm_drift` event that only proposes. Creator Insider and Liaison feeds join the watched list. Web text stays data, never instructions. Test by pointing the watcher at a mock page and editing it.
8. **Learner.** A Monday report folded into the weekly digest; winners and losers written to `rules.insights`; a Short with 70% or more stayed queues a long video on that topic within 7 days.
9. **Close-out.** Risks card row "Growth rules", CLAUDE.md and `docs/` updates, full test suite, `studio-deploy`, a plain report with what was and was not verified.

## 6. Guardrails that apply throughout

Our `CLAUDE.md` wins where it disagrees with the spec. Secrets reach the server by `scp` only. No publish, delete or channel-setting change without your word. No re-render at the daily cap, and a copy of a video's folder before any in-place repair (see the 28 Oct incident). Tests run and quoted; claims labelled VERIFIED only with a page to show.

## 7. Risks

Spend: longer videos and a second-source step raise cost per video (decision 3). API limits: the Reporting job can take about 48 hours to produce its first report; quota is cached and backed off. Scope creep: phases 4 and 5 change what the writer produces, so each ships behind a warning-only flag first. Public repo: the two source files hold the channel's own figures, so they stay uncommitted unless you say otherwise.
